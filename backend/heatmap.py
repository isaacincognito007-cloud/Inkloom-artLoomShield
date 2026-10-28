"""
4x4 Clear-Space & Contrast Heatmap Inspector (Round 3 Part C).
Reuses and extends the Tier 1 Visual & Accessibility calculations in backend/engine.py:
- C1: Splits uploaded raster (PNG/JPG) or SVG into an N x N grid (default 4, allowed 2..8) after
      downscaling to at most 1024 px on the longest side. Per cell: dominant colour, minimum CIE Delta-E
      to the nearest approved Brand Vault palette colour, flagged when above threshold.
- C2: Measures WCAG 2.1 contrast only for known text (SVG <text> elements or user-marked regions).
      No OCR. Always states: "Contrast measured for N text elements; text inside raster images is not detected."
- C3: Measures logo clear space from (a) SVG element with data-loomshield-logo or id/class "logo",
      (b) user-drawn rectangle, or (c) alpha bounding box of a PNG marked as "logo-only".
      Measures distance in px and as a multiple of logo height against the Brand Vault rule.
      Reports "Not Checked" with the reason when no logo location is specified.
"""

import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

from backend.engine import (
    delta_e_cie76,
    find_closest_brand_color,
    hex_to_rgb,
    is_valid_hex,
    rgb_to_hex,
    wcag_contrast_ratio,
)

MAX_HEATMAP_DIMENSION = 1024

_NAMED_COLORS_HEX = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#FF0000",
    "green": "#008000",
    "lime": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#C0C0C0",
    "navy": "#000080",
    "orange": "#FFA500",
}


def normalize_color_to_hex(raw_color: Optional[str], default: Optional[str] = None) -> Optional[str]:
    """Normalize a hex or named CSS/SVG color string to uppercase 6-digit #RRGGBB."""
    if not raw_color or not isinstance(raw_color, str):
        return default
    s = raw_color.strip().lower()
    if s in ("none", "transparent", "inherit", "currentcolor"):
        return default
    if s in _NAMED_COLORS_HEX:
        return _NAMED_COLORS_HEX[s]
    if is_valid_hex(s):
        return rgb_to_hex(hex_to_rgb(s))
    m_rgb = re.match(r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", s)
    if m_rgb:
        return rgb_to_hex((int(m_rgb.group(1)), int(m_rgb.group(2)), int(m_rgb.group(3))))
    return default


def _extract_style_prop(el, prop_name: str) -> Optional[str]:
    """Extract a colour or numeric property from an SVG element's attribute or inline style."""
    if el is None:
        return None
    direct = el.get(prop_name)
    if direct is not None and str(direct).strip():
        return str(direct).strip()
    style_str = str(el.get("style") or "")
    if style_str:
        m = re.search(r"(?:^|;)\s*" + re.escape(prop_name) + r"\s*:\s*([^;]+)", style_str, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _parse_svg_length(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    s = str(val).strip()
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else default


def sanitize_svg_markup(raw_svg: str) -> Tuple[str, bool, List[str]]:
    """Strip executable <script> tags, inline on* event handlers, and javascript: URIs from SVG."""
    soup = BeautifulSoup(raw_svg, "html.parser")
    sanitized_actions: List[str] = []

    for script_tag in soup.find_all(["script", "iframe", "object", "embed"]):
        script_tag.decompose()
        sanitized_actions.append(f"Removed <{script_tag.name}> element")

    for tag in soup.find_all(True):
        attrs_to_remove = []
        for attr_name, attr_val in list(tag.attrs.items()):
            low_name = str(attr_name).lower()
            val_str = " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val or "")
            if low_name.startswith("on"):
                attrs_to_remove.append(attr_name)
                sanitized_actions.append(f"Removed inline event attribute '{attr_name}'")
            elif "javascript:" in val_str.lower():
                attrs_to_remove.append(attr_name)
                sanitized_actions.append(f"Removed javascript: URI in '{attr_name}'")
        for attr_name in attrs_to_remove:
            del tag.attrs[attr_name]

    return str(soup), len(sanitized_actions) > 0, sanitized_actions


def _svg_element_bbox(el, default_w: float, default_h: float) -> Optional[Tuple[float, float, float, float]]:
    """Compute approximate (x, y, width, height) bounding box for an SVG shape element."""
    name = (el.name or "").lower()
    if name == "rect" or name == "image" or name == "use" or name == "svg":
        x = _parse_svg_length(el.get("x"), 0.0)
        y = _parse_svg_length(el.get("y"), 0.0)
        w = _parse_svg_length(el.get("width"), default_w if name == "svg" else 0.0)
        h = _parse_svg_length(el.get("height"), default_h if name == "svg" else 0.0)
        if w > 0 and h > 0:
            return (x, y, w, h)
    elif name == "circle":
        cx = _parse_svg_length(el.get("cx"), 0.0)
        cy = _parse_svg_length(el.get("cy"), 0.0)
        r = _parse_svg_length(el.get("r"), 0.0)
        if r > 0:
            return (cx - r, cy - r, 2.0 * r, 2.0 * r)
    elif name == "ellipse":
        cx = _parse_svg_length(el.get("cx"), 0.0)
        cy = _parse_svg_length(el.get("cy"), 0.0)
        rx = _parse_svg_length(el.get("rx"), 0.0)
        ry = _parse_svg_length(el.get("ry"), 0.0)
        if rx > 0 and ry > 0:
            return (cx - rx, cy - ry, 2.0 * rx, 2.0 * ry)
    elif name in ("polygon", "polyline", "path"):
        raw_pts = str(el.get("points") or el.get("d") or "")
        nums = [float(x) for x in re.findall(r"[+-]?\d+(?:\.\d+)?", raw_pts)]
        if len(nums) >= 4:
            xs = nums[0::2]
            ys = nums[1::2]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            if max_x > min_x and max_y > min_y:
                return (min_x, min_y, max_x - min_x, max_y - min_y)
    elif name == "text":
        x = _parse_svg_length(el.get("x"), 0.0)
        y = _parse_svg_length(el.get("y"), 16.0)
        font_sz = _parse_svg_length(_extract_style_prop(el, "font-size"), 16.0)
        txt = el.get_text(" ", strip=True)
        w = max(font_sz, len(txt) * font_sz * 0.55)
        h = max(8.0, font_sz)
        return (x, max(0.0, y - h), w, h)
    elif name == "g":
        child_boxes = []
        for child in el.find_all(["rect", "circle", "ellipse", "polygon", "polyline", "path", "text", "image"]):
            cb = _svg_element_bbox(child, default_w, default_h)
            if cb:
                child_boxes.append(cb)
        if child_boxes:
            min_x = min(b[0] for b in child_boxes)
            min_y = min(b[1] for b in child_boxes)
            max_x = max(b[0] + b[2] for b in child_boxes)
            max_y = max(b[1] + b[3] for b in child_boxes)
            return (min_x, min_y, max_x - min_x, max_y - min_y)
        # Fallback if <g> itself carries x, y, width, height attributes
        x = _parse_svg_length(el.get("x"), 0.0)
        y = _parse_svg_length(el.get("y"), 0.0)
        w = _parse_svg_length(el.get("width"), 0.0)
        h = _parse_svg_length(el.get("height"), 0.0)
        if w > 0 and h > 0:
            return (x, y, w, h)
    return None


def _is_logo_element(el) -> bool:
    if el is None or not hasattr(el, "attrs"):
        return False
    if el.has_attr("data-loomshield-logo"):
        val = str(el.get("data-loomshield-logo") or "true").strip().lower()
        return val not in ("false", "0", "no")
    el_id = str(el.get("id") or "").strip().lower()
    if el_id == "logo" or "logo" in el_id.split("-") or "logo" in el_id.split("_") or el_id.startswith("logo"):
        return True
    cls_attr = el.get("class")
    if isinstance(cls_attr, list):
        classes = [str(c).strip().lower() for c in cls_attr]
    else:
        classes = [c.strip().lower() for c in str(cls_attr or "").split() if c.strip()]
    return any(c == "logo" or "logo" in c.split("-") or "logo" in c.split("_") for c in classes)


def _parse_svg_for_heatmap(raw_svg: str) -> Dict[str, Any]:
    """Sanitize SVG, render shapes to a Pillow RGBA image, and extract text & logo geometry."""
    sanitized_svg, was_sanitized, sanitized_actions = sanitize_svg_markup(raw_svg)
    soup = BeautifulSoup(sanitized_svg, "html.parser")
    svg_root = soup.find("svg")
    if not svg_root:
        raise ValueError("Uploaded file does not contain a root <svg> element.")

    # Determine canvas width and height from viewBox or width/height attributes
    vb = svg_root.get("viewbox") or svg_root.get("viewBox")
    width, height = 400, 300
    if vb:
        parts = [p for p in re.split(r"[\s,]+", str(vb).strip()) if p]
        if len(parts) == 4:
            try:
                width = max(1, int(round(float(parts[2]))))
                height = max(1, int(round(float(parts[3]))))
            except ValueError:
                pass
    w_attr = _parse_svg_length(svg_root.get("width"), 0.0)
    h_attr = _parse_svg_length(svg_root.get("height"), 0.0)
    if w_attr > 0 and h_attr > 0 and not vb:
        width = max(1, int(round(w_attr)))
        height = max(1, int(round(h_attr)))

    # Cap initial SVG rasterization canvas to 2048x2048 for memory safety, then downscale step handles >1024
    render_w = min(2048, width)
    render_h = min(2048, height)
    sx = render_w / float(width)
    sy = render_h / float(height)

    root_bg = normalize_color_to_hex(
        _extract_style_prop(svg_root, "background-color")
        or _extract_style_prop(svg_root, "background")
        or _extract_style_prop(svg_root, "fill"),
        default="#FFFFFF",
    )
    img = Image.new("RGBA", (render_w, render_h), hex_to_rgb(root_bg) + (255,))
    draw = ImageDraw.Draw(img)

    bg_rects: List[Tuple[float, float, float, float, str]] = []
    logo_box: Optional[Dict[str, Any]] = None
    other_boxes: List[Tuple[float, float, float, float]] = []

    # Paint vector shapes in document order so grid cells reflect SVG layout colours
    for el in svg_root.find_all(["rect", "circle", "ellipse", "polygon", "g", "path", "text"]):
        if _is_logo_element(el) and logo_box is None:
            lb = _svg_element_bbox(el, float(width), float(height))
            if lb:
                logo_box = {
                    "x": lb[0],
                    "y": lb[1],
                    "width": lb[2],
                    "height": lb[3],
                    "source": "svg_attribute",
                }

        name = (el.name or "").lower()
        if name == "g":
            continue

        fill_hex = normalize_color_to_hex(_extract_style_prop(el, "fill"), default=None)
        bbox = _svg_element_bbox(el, float(width), float(height))
        if not bbox:
            continue
        bx, by, bw, bh = bbox

        # Check if this is a full-canvas background rect
        is_full_bg = (
            name == "rect"
            and bx <= 1.0
            and by <= 1.0
            and bw >= width * 0.9
            and bh >= height * 0.9
        )
        if name == "rect" and fill_hex:
            bg_rects.append((bx, by, bw, bh, fill_hex))

        if not _is_logo_element(el) and not _is_logo_element(el.parent) and not is_full_bg:
            other_boxes.append(bbox)

        if fill_hex and name in ("rect", "circle", "ellipse"):
            rgb_tuple = hex_to_rgb(fill_hex) + (255,)
            rx0 = int(round(bx * sx))
            ry0 = int(round(by * sy))
            rx1 = int(round((bx + bw) * sx))
            ry1 = int(round((by + bh) * sy))
            if rx1 > rx0 and ry1 > ry0:
                if name == "rect":
                    draw.rectangle([rx0, ry0, rx1 - 1, ry1 - 1], fill=rgb_tuple)
                else:
                    draw.ellipse([rx0, ry0, rx1 - 1, ry1 - 1], fill=rgb_tuple)

    # Extract <text> elements and determine foreground vs background contrast
    text_elements: List[Dict[str, Any]] = []
    for idx, t_el in enumerate(svg_root.find_all("text"), start=1):
        txt_str = t_el.get_text(" ", strip=True)
        if not txt_str:
            continue
        fg_hex = normalize_color_to_hex(_extract_style_prop(t_el, "fill"), default="#000000")
        tx = _parse_svg_length(t_el.get("x"), 0.0)
        ty = _parse_svg_length(t_el.get("y"), 16.0)
        tbbox = _svg_element_bbox(t_el, float(width), float(height)) or (tx, max(0.0, ty - 16.0), 60.0, 16.0)

        # Find topmost rect containing (tx, ty)
        effective_bg = root_bg
        for rx, ry, rw, rh, rfill in bg_rects:
            if rx <= tx <= (rx + rw) and ry <= ty <= (ry + rh):
                effective_bg = rfill

        text_elements.append({
            "id": t_el.get("id") or f"svg-text-{idx}",
            "text": txt_str,
            "fg_hex": fg_hex,
            "bg_hex": effective_bg,
            "x": round(tbbox[0], 2),
            "y": round(tbbox[1], 2),
            "width": round(tbbox[2], 2),
            "height": round(tbbox[3], 2),
            "source": "svg_text",
        })

    return {
        "rgba_image": img,
        "original_width": width,
        "original_height": height,
        "sanitized_svg": sanitized_svg,
        "svg_sanitized": was_sanitized,
        "sanitized_actions": sanitized_actions,
        "text_elements": text_elements,
        "logo_box": logo_box,
        "other_boxes": other_boxes,
    }


def _dominant_cell_hex(cell_rgba: np.ndarray) -> Tuple[Optional[str], float]:
    """Compute dominant hex colour of an RGBA cell array without quantization shift on solid colours."""
    alpha = cell_rgba[:, :, 3]
    opaque_mask = alpha >= 32
    total_px = cell_rgba.shape[0] * cell_rgba.shape[1]
    if total_px == 0 or not np.any(opaque_mask):
        return None, 0.0

    rgb_pixels = cell_rgba[:, :, :3][opaque_mask]
    opaque_ratio = round(float(rgb_pixels.shape[0]) * 100.0 / float(total_px), 1)

    # Bin into 8-step buckets to find the dominant colour cluster, then take exact median RGB inside that cluster
    bins = rgb_pixels // 8
    unique_bins, inverse_idx, counts = np.unique(
        bins, axis=0, return_inverse=True, return_counts=True
    )
    best_bin_idx = int(np.argmax(counts))
    cluster_pixels = rgb_pixels[inverse_idx == best_bin_idx]
    median_rgb = np.median(cluster_pixels, axis=0)
    rgb_tuple = (
        int(round(float(median_rgb[0]))),
        int(round(float(median_rgb[1]))),
        int(round(float(median_rgb[2]))),
    )
    return rgb_to_hex(rgb_tuple), opaque_ratio


def inspect_visual_heatmap(
    raw_bytes: bytes,
    brand_colors: Optional[List[Dict[str, Any]]] = None,
    brand: Optional[Dict[str, Any]] = None,
    filename: str = "asset.png",
    grid_size: int = 4,
    logo_rect: Optional[Dict[str, float]] = None,
    logo_only: bool = False,
    text_regions: Optional[List[Dict[str, Any]]] = None,
    default_bg_color: str = "",
) -> Dict[str, Any]:
    """Run N x N Palette CIE Delta-E, Known-Text WCAG Contrast, and Logo Clear-Space Heatmap analysis."""
    # Allow callers passing (raw_bytes, filename, brand, brand_colors) positionally as well
    if isinstance(brand_colors, str):
        filename = brand_colors
        brand_colors = []
    brand = brand or {}
    brand_colors = brand_colors or []
    n_grid = max(2, min(8, int(grid_size or 4)))
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in (filename or "") else ".png"

    is_svg = (ext == ".svg")
    svg_meta: Dict[str, Any] = {}

    if is_svg:
        try:
            decoded_svg = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded_svg = raw_bytes.decode("utf-8", errors="replace")
        svg_meta = _parse_svg_for_heatmap(decoded_svg)
        rgba_img = svg_meta["rgba_image"]
        orig_w = int(svg_meta["original_width"])
        orig_h = int(svg_meta["original_height"])
    else:
        try:
            rgba_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            orig_w, orig_h = rgba_img.size
        except Exception as exc:
            return {
                "inspect_ok": False,
                "error": f"Image could not be decoded ({str(exc)}). Visual colour and heatmap checks were not completed.",
            }

    # C1: Downscale to at most 1024 px on longest side first
    downscaled = False
    if max(orig_w, orig_h) > MAX_HEATMAP_DIMENSION:
        scale = float(MAX_HEATMAP_DIMENSION) / float(max(orig_w, orig_h))
        analyzed_w = max(1, int(round(orig_w * scale)))
        analyzed_h = max(1, int(round(orig_h * scale)))
        rgba_img = rgba_img.resize((analyzed_w, analyzed_h), Image.Resampling.LANCZOS)
        downscaled = True
    else:
        scale = 1.0
        analyzed_w, analyzed_h = rgba_img.size

    arr = np.array(rgba_img)

    # C1: N x N Grid analysis
    cells: List[Dict[str, Any]] = []
    flagged_cells_count = 0
    for r_idx in range(n_grid):
        y0 = int(round(r_idx * analyzed_h / float(n_grid)))
        y1 = int(round((r_idx + 1) * analyzed_h / float(n_grid)))
        for c_idx in range(n_grid):
            x0 = int(round(c_idx * analyzed_w / float(n_grid)))
            x1 = int(round((c_idx + 1) * analyzed_w / float(n_grid)))

            cell_slice = arr[y0:y1, x0:x1]
            dom_hex, opaque_pct = _dominant_cell_hex(cell_slice)
            coord_label = f"R{r_idx + 1}C{c_idx + 1}"

            if dom_hex is None:
                cells.append({
                    "row": r_idx,
                    "col": c_idx,
                    "cell_id": coord_label,
                    "x": x0,
                    "y": y0,
                    "width": max(1, x1 - x0),
                    "height": max(1, y1 - y0),
                    "dominant_hex": None,
                    "opaque_pct": 0.0,
                    "closest_brand_color": "Transparent",
                    "closest_brand_hex": "",
                    "min_delta_e": 0.0,
                    "threshold_delta_e": 14.0,
                    "flagged": False,
                    "status": "transparent",
                    "pattern": "dots",
                })
                continue

            closest = find_closest_brand_color(dom_hex, brand_colors)
            if closest:
                min_de = float(closest["delta_e"])
                thresh_de = float(closest["max_delta_e"])
                is_flagged = bool(min_de > thresh_de)
                c_name = str(closest["name"])
                c_hex = str(closest["hex_code"])
            else:
                min_de = 0.0
                thresh_de = 14.0
                is_flagged = False
                c_name = "Unconfigured"
                c_hex = dom_hex

            if is_flagged:
                flagged_cells_count += 1

            cells.append({
                "row": r_idx,
                "col": c_idx,
                "cell_id": coord_label,
                "x": x0,
                "y": y0,
                "width": max(1, x1 - x0),
                "height": max(1, y1 - y0),
                "dominant_hex": dom_hex,
                "opaque_pct": opaque_pct,
                "closest_brand_color": c_name,
                "closest_brand_hex": c_hex,
                "min_delta_e": min_de,
                "delta_e": min_de,
                "threshold_delta_e": thresh_de,
                "max_delta_e": thresh_de,
                "flagged": is_flagged,
                "status": "fail" if is_flagged else "pass",
                "pattern": "hatch" if is_flagged else "solid",
            })

    # C2: Text contrast (only for SVG <text> elements or user-marked regions; no OCR)
    min_contrast_req = float(brand.get("min_contrast_normal", 4.5))
    raw_text_items: List[Dict[str, Any]] = []
    if is_svg:
        raw_text_items.extend(svg_meta.get("text_elements", []))
    for idx, reg in enumerate(text_regions or [], start=1):
        if not isinstance(reg, dict):
            continue
        fg_h = normalize_color_to_hex(reg.get("fg_hex"), default=None)
        bg_h = normalize_color_to_hex(reg.get("bg_hex") or default_bg_color, default="#FFFFFF")
        rx = float(reg.get("x", 0.0))
        ry = float(reg.get("y", 0.0))
        rw = float(reg.get("width", 40.0))
        rh = float(reg.get("height", 20.0))
        if not fg_h:
            # Sample darkest/lightest pixels in the user-marked region
            sx0 = max(0, min(analyzed_w - 1, int(round(rx))))
            sy0 = max(0, min(analyzed_h - 1, int(round(ry))))
            sx1 = max(sx0 + 1, min(analyzed_w, int(round(rx + rw))))
            sy1 = max(sy0 + 1, min(analyzed_h, int(round(ry + rh))))
            sub = arr[sy0:sy1, sx0:sx1, :3].reshape(-1, 3)
            if sub.shape[0] > 0:
                lums = 0.2126 * sub[:, 0] + 0.7152 * sub[:, 1] + 0.0722 * sub[:, 2]
                dark_rgb = tuple(int(v) for v in sub[int(np.argmin(lums))])
                light_rgb = tuple(int(v) for v in sub[int(np.argmax(lums))])
                fg_h = rgb_to_hex(dark_rgb)
                bg_h = rgb_to_hex(light_rgb)
            else:
                fg_h = "#000000"
        raw_text_items.append({
            "id": reg.get("id") or f"user-text-{idx}",
            "text": str(reg.get("label") or reg.get("text") or f"User region #{idx}"),
            "fg_hex": fg_h,
            "bg_hex": bg_h,
            "x": round(rx, 2),
            "y": round(ry, 2),
            "width": round(rw, 2),
            "height": round(rh, 2),
            "source": "user_region",
        })

    contrast_items: List[Dict[str, Any]] = []
    flagged_contrast_count = 0
    for item in raw_text_items:
        fg_h = item["fg_hex"]
        bg_h = item["bg_hex"]
        if default_bg_color and is_valid_hex(default_bg_color) and item.get("source") == "svg_text" and bg_h == "#FFFFFF":
            bg_h = normalize_color_to_hex(default_bg_color, default="#FFFFFF")
        ratio = wcag_contrast_ratio(fg_h, bg_h)
        passed = bool(ratio >= min_contrast_req)
        if not passed:
            flagged_contrast_count += 1
        tc_x = float(item.get("x", 0.0)) + float(item.get("width", 0.0)) / 2.0
        tc_y = float(item.get("y", 0.0)) + float(item.get("height", 0.0)) / 2.0
        tc_c = max(1, min(n_grid, int(tc_x * n_grid / max(1.0, float(orig_w if is_svg else analyzed_w))) + 1))
        tc_r = max(1, min(n_grid, int(tc_y * n_grid / max(1.0, float(orig_h if is_svg else analyzed_h))) + 1))
        contrast_items.append({
            **item,
            "cell_id": item.get("cell_id") or f"R{tc_r}C{tc_c}",
            "bg_hex": bg_h,
            "contrast_ratio": ratio,
            "min_required": min_contrast_req,
            "required_ratio": min_contrast_req,
            "passed": passed,
            "flagged": not passed,
            "status": "pass" if passed else "fail",
        })

    contrast_disclosure = (
        f"Contrast measured for {len(contrast_items)} text elements; text inside raster images is not detected."
    )

    # C3: Logo Clear Space
    required_ratio = float(brand.get("min_clear_space_ratio", 0.25))
    required_px = float(brand.get("min_clear_space_px", 16.0))

    resolved_logo: Optional[Dict[str, Any]] = None
    canvas_for_logo_w = float(orig_w if is_svg else analyzed_w)
    canvas_for_logo_h = float(orig_h if is_svg else analyzed_h)

    if isinstance(logo_rect, dict) and float(logo_rect.get("width", 0)) > 0 and float(logo_rect.get("height", 0)) > 0:
        resolved_logo = {
            "x": float(logo_rect.get("x", 0.0)),
            "y": float(logo_rect.get("y", 0.0)),
            "width": float(logo_rect["width"]),
            "height": float(logo_rect["height"]),
            "source": "user_drawn_rect",
        }
        canvas_for_logo_w = float(analyzed_w)
        canvas_for_logo_h = float(analyzed_h)
    elif is_svg and svg_meta.get("logo_box"):
        resolved_logo = svg_meta["logo_box"]
        canvas_for_logo_w = float(orig_w)
        canvas_for_logo_h = float(orig_h)
    elif logo_only and not is_svg:
        alpha_ch = arr[:, :, 3]
        ys, xs = np.where(alpha_ch >= 32)
        if ys.size > 0 and xs.size > 0:
            lx0, lx1 = float(xs.min()), float(xs.max() + 1)
            ly0, ly1 = float(ys.min()), float(ys.max() + 1)
            resolved_logo = {
                "x": lx0,
                "y": ly0,
                "width": max(1.0, lx1 - lx0),
                "height": max(1.0, ly1 - ly0),
                "source": "png_alpha_bbox",
            }
            canvas_for_logo_w = float(analyzed_w)
            canvas_for_logo_h = float(analyzed_h)

    if resolved_logo is None:
        clear_space = {
            "state": "Not Checked",
            "status": "Not Checked",
            "checked": False,
            "passed": None,
            "logo_box": None,
            "edge_distances_px": None,
            "nearest_content_px": None,
            "min_distance_px": None,
            "logo_height_px": None,
            "measured_ratio": None,
            "required_ratio": required_ratio,
            "required_px": required_px,
            "reason": (
                "No logo location was specified. Mark an SVG element with data-loomshield-logo (or id/class 'logo'), "
                "draw a logo rectangle in the Heatmap Inspector, or mark a transparent PNG as logo-only."
            ),
        }
    else:
        lx = float(resolved_logo["x"])
        ly = float(resolved_logo["y"])
        lw = max(1.0, float(resolved_logo["width"]))
        lh = max(1.0, float(resolved_logo["height"]))

        dist_left = max(0.0, lx)
        dist_top = max(0.0, ly)
        dist_right = max(0.0, canvas_for_logo_w - (lx + lw))
        dist_bottom = max(0.0, canvas_for_logo_h - (ly + lh))

        nearest_other: Optional[float] = None
        if is_svg and svg_meta.get("other_boxes"):
            gaps = []
            for ox, oy, ow, oh in svg_meta["other_boxes"]:
                dx = max(0.0, ox - (lx + lw), lx - (ox + ow))
                dy = max(0.0, oy - (ly + lh), ly - (oy + oh))
                gaps.append(round(math.hypot(dx, dy), 2))
            if gaps:
                nearest_other = min(gaps)

        candidates = [dist_left, dist_top, dist_right, dist_bottom]
        if nearest_other is not None:
            candidates.append(nearest_other)
        min_dist_px = round(min(candidates), 2)
        measured_ratio = round(min_dist_px / lh, 3)
        cs_passed = bool(min_dist_px >= required_px and measured_ratio >= required_ratio)

        lg_c = max(1, min(n_grid, int((lx + lw / 2.0) * n_grid / max(1.0, canvas_for_logo_w)) + 1))
        lg_r = max(1, min(n_grid, int((ly + lh / 2.0) * n_grid / max(1.0, canvas_for_logo_h)) + 1))
        logo_cell_ref = f"Cell R{lg_r}C{lg_c}"
        nearest_obs = "sibling element" if (nearest_other is not None and nearest_other == min_dist_px) else "canvas edge"

        clear_space = {
            "state": "Passed" if cs_passed else "Findings",
            "status": "Passed" if cs_passed else "Findings",
            "checked": True,
            "passed": cs_passed,
            "logo_cell_ref": logo_cell_ref,
            "nearest_obstacle": nearest_obs,
            "logo_box": {
                "x": round(lx, 2),
                "y": round(ly, 2),
                "width": round(lw, 2),
                "height": round(lh, 2),
                "source": resolved_logo["source"],
            },
            "edge_distances_px": {
                "left": round(dist_left, 2),
                "top": round(dist_top, 2),
                "right": round(dist_right, 2),
                "bottom": round(dist_bottom, 2),
            },
            "nearest_content_px": nearest_other,
            "min_distance_px": min_dist_px,
            "min_clear_space_px": min_dist_px,
            "logo_height_px": round(lh, 2),
            "measured_ratio": measured_ratio,
            "required_ratio": required_ratio,
            "required_px": required_px,
            "required_min_px": required_px,
            "reason": (
                f"Logo clear space passed: minimum clearance is {min_dist_px} px ({measured_ratio}x logo height), "
                f"meeting the required {required_px} px and {required_ratio}x logo height."
                if cs_passed
                else (
                    f"Logo clear-space violation: minimum clearance is {min_dist_px} px ({measured_ratio}x logo height), "
                    f"which is below the required {required_px} px / {required_ratio}x logo height."
                )
            ),
        }

    return {
        "inspect_ok": True,
        "format": "svg" if is_svg else ext.lstrip("."),
        "original_width": orig_w,
        "original_height": orig_h,
        "analyzed_width": analyzed_w,
        "analyzed_height": analyzed_h,
        "downscaled": downscaled,
        "grid_size": n_grid,
        "total_cells": len(cells),
        "flagged_cells_count": flagged_cells_count,
        "palette_state": "Findings" if flagged_cells_count > 0 else "Passed",
        "cells": cells,
        "text_contrast": {
            "measured_count": len(contrast_items),
            "flagged_count": flagged_contrast_count,
            "state": (
                "Not Checked"
                if len(contrast_items) == 0
                else ("Findings" if flagged_contrast_count > 0 else "Passed")
            ),
            "disclosure": contrast_disclosure,
            "elements": contrast_items,
        },
        "clear_space": clear_space,
        "svg_sanitized": bool(svg_meta.get("svg_sanitized", False)),
        "sanitized_actions": svg_meta.get("sanitized_actions", []),
        "sanitized_svg": svg_meta.get("sanitized_svg") if is_svg else None,
    }
