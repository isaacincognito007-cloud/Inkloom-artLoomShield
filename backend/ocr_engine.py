"""
On-Device Quantized OCR & Bitmap Text Contrast Engine (Option A).

Provides 100% local, zero-key, zero-cloud optical character recognition (OCR)
using lightweight ONNX Runtime (RapidOCR) and pixel-level WCAG 2.1 AA luminance
contrast evaluation for raster images (PNG, JPEG) and scanned PDFs.
"""

import io
import os
import time
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger("loomshield.ocr_engine")

_OCR_INSTANCE = None
_OCR_LOCK = threading.Lock()
_OCR_FAILED = False


def get_ocr_engine():
    """Lazily load the RapidOCR ONNX model instance (thread-safe singleton)."""
    global _OCR_INSTANCE, _OCR_FAILED
    if _OCR_INSTANCE is None and not _OCR_FAILED:
        with _OCR_LOCK:
            if _OCR_INSTANCE is None and not _OCR_FAILED:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                    _OCR_INSTANCE = RapidOCR()
                    logger.info("RapidOCR ONNX local engine initialized successfully.")
                except Exception as exc:
                    _OCR_FAILED = True
                    logger.warning(f"Could not load RapidOCR local engine: {exc}")
                    return None
    return _OCR_INSTANCE


def is_ocr_available() -> bool:
    """Return True if local ONNX OCR is available on this device."""
    return get_ocr_engine() is not None


def _srgb_channel_to_linear(val: float) -> float:
    """Convert an sRGB 0..255 channel value to relative linear luminance."""
    c = val / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: Union[Tuple[int, int, int], np.ndarray]) -> float:
    """Calculate WCAG 2.1 relative luminance for an (R, G, B) tuple."""
    r_lin = _srgb_channel_to_linear(float(rgb[0]))
    g_lin = _srgb_channel_to_linear(float(rgb[1]))
    b_lin = _srgb_channel_to_linear(float(rgb[2]))
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _wcag_contrast_ratio(lum1: float, lum2: float) -> float:
    """Calculate WCAG 2.1 contrast ratio between two relative luminance values."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def rgb_to_hex(rgb: Union[Tuple[int, int, int], np.ndarray]) -> str:
    """Format RGB components as uppercase #RRGGBB."""
    r = int(np.clip(rgb[0], 0, 255))
    g = int(np.clip(rgb[1], 0, 255))
    b = int(np.clip(rgb[2], 0, 255))
    return f"#{r:02X}{g:02X}{b:02X}"


def estimate_patch_colors(
    patch: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Estimate background and text foreground colors from an image crop patch.
    
    1. Border pixels of the bounding box provide an estimate of background color.
    2. Core text pixels are located by measuring Euclidean distance from background
       and taking the top 10% furthest pixels (central glyph stroke core).
    3. Returns (fg_rgb, bg_rgb, confidence_metric).
    """
    if patch.ndim != 3 or patch.shape[2] < 3:
        return np.array([0, 0, 0]), np.array([255, 255, 255]), 0.0

    # Ensure 3-channel RGB
    arr = patch[:, :, :3]
    h, w, _ = arr.shape
    if h < 2 or w < 2:
        val = np.median(arr, axis=(0, 1))
        return val, val, 0.0

    # Sample perimeter border
    top = arr[0, :]
    bot = arr[-1, :]
    left = arr[:, 0]
    right = arr[:, -1]
    border_pixels = np.concatenate([top, bot, left, right], axis=0)
    bg_est = np.median(border_pixels, axis=0)

    # Compute Euclidean distance from background for all patch pixels
    diff = np.linalg.norm(arr.astype(float) - bg_est.astype(float), axis=2)
    
    # Use top 10% furthest pixels to represent core glyph stroke colors
    threshold = float(np.percentile(diff, 90))
    if threshold > 12.0:
        fg_mask = diff >= threshold
        fg_est = np.median(arr[fg_mask], axis=0)
        confidence = float(min(1.0, threshold / 100.0))
    else:
        # Patch is essentially solid / uniform
        fg_est = bg_est
        confidence = 0.0

    return fg_est, bg_est, confidence


def extract_raster_text_and_contrast(
    image_input: Union[Image.Image, bytes, np.ndarray],
    min_contrast_normal: float = 4.5,
    min_contrast_large: float = 3.0,
    grid_size: int = 4,
) -> Dict[str, Any]:
    """
    Perform on-device ONNX OCR on a raster image and calculate pixel-level WCAG contrast
    for every detected text element.
    """
    t0 = time.perf_counter()

    # Normalize image to numpy RGB
    if isinstance(image_input, bytes):
        pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
        np_img = np.array(pil_img)
    elif isinstance(image_input, Image.Image):
        pil_img = image_input.convert("RGB")
        np_img = np.array(pil_img)
    elif isinstance(image_input, np.ndarray):
        np_img = image_input[:, :, :3] if image_input.shape[2] > 3 else image_input
        pil_img = Image.fromarray(np_img)
    else:
        raise ValueError("Unsupported image input type for OCR.")

    engine = get_ocr_engine()
    if engine is None:
        return {
            "ocr_available": False,
            "ocr_engine": "None",
            "extracted_text": "",
            "elements": [],
            "measured_count": 0,
            "flagged_count": 0,
            "execution_time_ms": 0.0,
        }

    try:
        results, _ = engine(np_img)
    except Exception as exc:
        logger.error(f"OCR inference failure: {exc}")
        results = None

    if not results:
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "ocr_available": True,
            "ocr_engine": "ONNX Quantized PaddleOCR (RapidOCR)",
            "extracted_text": "",
            "elements": [],
            "measured_count": 0,
            "flagged_count": 0,
            "execution_time_ms": elapsed_ms,
        }

    img_h, img_w, _ = np_img.shape
    text_elements: List[Dict[str, Any]] = []
    text_lines: List[str] = []
    flagged_count = 0
    measured_count = 0

    for idx, item in enumerate(results, start=1):
        poly, text, conf = item
        text_str = str(text).strip()
        if not text_str:
            continue
        text_lines.append(text_str)

        poly_np = np.array(poly)
        x_min = float(np.min(poly_np[:, 0]))
        y_min = float(np.min(poly_np[:, 1]))
        x_max = float(np.max(poly_np[:, 0]))
        y_max = float(np.max(poly_np[:, 1]))

        box_w = max(1.0, x_max - x_min)
        box_h = max(1.0, y_max - y_min)

        # Expand patch slightly by 2 pixels for reliable border background estimation
        pad = 2
        y0_p = max(0, int(y_min) - pad)
        y1_p = min(img_h, int(y_max) + pad)
        x0_p = max(0, int(x_min) - pad)
        x1_p = min(img_w, int(x_max) + pad)

        patch = np_img[y0_p:y1_p, x0_p:x1_p]
        fg_rgb, bg_rgb, _ = estimate_patch_colors(patch)

        fg_hex = rgb_to_hex(fg_rgb)
        bg_hex = rgb_to_hex(bg_rgb)

        lum_fg = _relative_luminance(fg_rgb)
        lum_bg = _relative_luminance(bg_rgb)
        contrast_ratio = _wcag_contrast_ratio(lum_fg, lum_bg)

        # Large text rule: height >= 24px requires 3.0:1; normal text requires 4.5:1
        is_large = bool(box_h >= 24.0)
        required_ratio = float(min_contrast_large if is_large else min_contrast_normal)

        passed = bool(contrast_ratio >= required_ratio)
        if not passed:
            flagged_count += 1
        measured_count += 1

        # Calculate grid cell ID (e.g. R1C2) based on center point
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        cell_r = min(grid_size, max(1, int((cy / max(1.0, img_h)) * grid_size) + 1))
        cell_c = min(grid_size, max(1, int((cx / max(1.0, img_w)) * grid_size) + 1))
        cell_id = f"R{cell_r}C{cell_c}"

        text_elements.append({
            "id": f"ocr_text_{idx}",
            "text": text_str,
            "confidence": round(float(conf), 3),
            "bbox": [round(x_min, 1), round(y_min, 1), round(x_max, 1), round(y_max, 1)],
            "polygon": [[round(pt[0], 1), round(pt[1], 1)] for pt in poly],
            "width": round(box_w, 1),
            "height": round(box_h, 1),
            "is_large_text": is_large,
            "fg_hex": fg_hex,
            "bg_hex": bg_hex,
            "contrast_ratio": contrast_ratio,
            "min_required": required_ratio,
            "required_ratio": required_ratio,
            "passed": passed,
            "flagged": not passed,
            "cell_id": cell_id,
            "detection_source": "ONNX OCR",
        })

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ocr_available": True,
        "ocr_engine": "ONNX Quantized PaddleOCR (RapidOCR)",
        "extracted_text": "\n".join(text_lines),
        "elements": text_elements,
        "measured_count": measured_count,
        "flagged_count": flagged_count,
        "execution_time_ms": elapsed_ms,
    }


def extract_text_from_scanned_pdf(
    raw_bytes: bytes,
    max_pages: int = 100,
) -> Dict[str, Any]:
    """
    Extract text from a scanned or image-only PDF using PyMuPDF page rendering and local OCR.
    """
    import fitz

    t0 = time.perf_counter()
    engine = get_ocr_engine()
    if engine is None:
        return {
            "success": False,
            "error": "Local OCR engine is not available.",
            "extracted_text": "",
            "pages": [],
        }

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to open PDF document: {exc}",
            "extracted_text": "",
            "pages": [],
        }

    total_pages = min(len(doc), max_pages)
    page_texts: List[str] = []
    page_spans: List[Dict[str, Any]] = []
    current_offset = 0

    for page_idx in range(total_pages):
        page = doc[page_idx]
        # Render page to 150 DPI pixmap for crisp character recognition
        pix = page.get_pixmap(dpi=150)
        page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        try:
            results, _ = engine(np.array(page_img))
            lines = [str(r[1]).strip() for r in results if r and str(r[1]).strip()] if results else []
            page_text = "\n".join(lines)
        except Exception as exc:
            logger.warning(f"OCR failed on page {page_idx + 1}: {exc}")
            page_text = ""

        if page_idx > 0:
            page_texts.append("\n\n")
            current_offset += 2

        start_idx = current_offset
        page_texts.append(page_text)
        current_offset += len(page_text)
        end_idx = current_offset

        page_spans.append({
            "page": page_idx + 1,
            "start": start_idx,
            "end": end_idx,
            "line_count": len(lines) if results else 0,
        })

    combined_text = "".join(page_texts)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "success": bool(combined_text.strip()),
        "extracted_text": combined_text,
        "page_count": total_pages,
        "page_spans": page_spans,
        "execution_time_ms": elapsed_ms,
        "ocr_engine": "ONNX Quantized PaddleOCR (RapidOCR)",
    }
