"""
4x4 Clear-Space & Contrast Heatmap Inspector (Round 3 Part C & Day 3 Hardening F1, F7, F8).
Reuses and extends the Tier 1 Visual & Accessibility calculations in backend/engine.py:
- C1 / F1 / F7: Splits uploaded raster (PNG/JPG) or SVG into an N x N grid (default 4, allowed 2..8) after
      probing header dimensions (rejecting >25 MP before pixel decode) and downscaling to at most 1024 px on
      the longest side. Per cell: dominant colour, any off-palette colour cluster covering >=2% of the cell,
      and minimum CIE Delta-E to the nearest approved Brand Vault palette colour. When a brand has no palette
      colours configured, palette_state is "Not Checked".
- C2 / F7: Measures WCAG 2.1 contrast only for known text (SVG <text> elements or user-marked regions),
      composing parent transforms and resolving inherited fill/style from ancestors. Reports currentColor or
      unresolvable fills as "Not measured", never as black. No OCR.
- C3 / F7: Measures logo clear space from (a) SVG element with data-loomshield-logo or id/class "logo"
      (with composed ancestor transforms), (b) user-drawn rectangle, or (c) alpha bounding box of a PNG
      marked as "logo-only".
- F8: Sanitizes SVG markup against script/iframe/object/embed/foreignObject, inline on* handlers,
      javascript: URIs, non-local href/xlink:href (allowing only #fragment and data:image/), external
      url(http...) in styles, @import rules, and <use> elements with external targets.
"""

import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

from backend.engine import (
    MAX_IMAGE_PIXELS,
    ImageTooLargeError,
    delta_e_cie76,
    find_closest_brand_color,
    hex_to_rgb,
    is_valid_hex,
    probe_and_decode_raster_image,
    rgb_to_hex,
    wcag_contrast_ratio,
)

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
MAX_HEATMAP_DIMENSION = 1024
OFF_PALETTE_CELL_MIN_PCT = 2.0

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
    """Normalize a hex, rgb(), or named CSS/SVG color string to uppercase 6-digit #RRGGBB."""
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
        r = max(0, min(255, int(m_rgb.group(1))))
        g = max(0, min(255, int(m_rgb.group(2))))
        b = max(0, min(255, int(m_rgb.group(3))))
        return rgb_to_hex((r, g, b))
    return default


def _extract_style_prop(el, prop_name: str) -> Optional[str]:
    """Extract a colour or numeric property from an SVG element's inline style or attribute."""
    if el is None or not hasattr(el, "get"):
        return None
    # Inline style takes precedence over presentation attribute in SVG/CSS
    style_str = str(el.get("style") or "")
    if style_str:
        m = re.search(r"(?:^|;)\s*" + re.escape(prop_name) + r"\s*:\s*([^;]+)", style_str, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    direct = el.get(prop_name)
    if direct is not None and str(direct).strip():
        return str(direct).strip()
    return None


def _resolve_inherited_fill(el, default_if_unset: Optional[str] = None) -> Tuple[Optional[str], str]:
    """
    F7(b): Walk element and its ancestors up to <svg> to resolve inherited fill/style.
    Returns (resolved_hex_or_not_measured, status_note).
    Reports currentColor or unresolvable fills as 'Not measured', never as black (#000000).
    """
    curr = el
    while curr is not None and getattr(curr, "name", None) not in (None, "[document]"):
        raw_fill = _extract_style_prop(curr, "fill")
        if raw_fill is not None:
            s = raw_fill.strip().lower()
            if s == "inherit":
                curr = getattr(curr, "parent", None)
                continue
            if s in ("none", "transparent"):
                return None, "transparent"
            if s == "currentcolor":
                return "Not measured", "currentColor fill cannot be resolved without external DOM stylesheet context"
            hex_c = normalize_color_to_hex(s, default=None)
            if hex_c:
                return hex_c, "resolved"
            return "Not measured", f"Unresolvable fill value '{raw_fill}'"
        if str(getattr(curr, "name", "")).lower() == "svg":
            break
        curr = getattr(curr, "parent", None)
    if default_if_unset is not None:
        return default_if_unset, "unset"
    return "Not measured", "No explicit fill attribute or inherited ancestor fill specified"


def _parse_svg_length(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    s = str(val).strip()
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else default


# ============================================================================
# F7(a): 2D AFFINE TRANSFORM COMPOSITION FOR SVG ELEMENTS
# ============================================================================

AffineMatrix = Tuple[float, float, float, float, float, float]  # (a, b, c, d, e, f)
_IDENTITY_MATRIX: AffineMatrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _multiply_affine(m1: AffineMatrix, m2: AffineMatrix) -> AffineMatrix:
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _parse_svg_transform_attr(transform_str: Optional[str]) -> AffineMatrix:
    """Parse an SVG transform='translate(...) scale(...) rotate(...) matrix(...)' string into a 2D affine matrix."""
    if not transform_str or not str(transform_str).strip():
        return _IDENTITY_MATRIX
    m = _IDENTITY_MATRIX
    for op, args_str in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", str(transform_str)):
        nums = [float(x) for x in re.findall(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", args_str)]
        if not nums:
            continue
        op_low = op.lower()
        if op_low == "translate":
            tx = nums[0]
            ty = nums[1] if len(nums) > 1 else 0.0
            m = _multiply_affine(m, (1.0, 0.0, 0.0, 1.0, tx, ty))
        elif op_low == "scale":
            sx = nums[0]
            sy = nums[1] if len(nums) > 1 else sx
            m = _multiply_affine(m, (sx, 0.0, 0.0, sy, 0.0, 0.0))
        elif op_low == "rotate":
            ang = math.radians(nums[0])
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                m = _multiply_affine(m, (1.0, 0.0, 0.0, 1.0, cx, cy))
                m = _multiply_affine(m, (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0))
                m = _multiply_affine(m, (1.0, 0.0, 0.0, 1.0, -cx, -cy))
            else:
                m = _multiply_affine(m, (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0))
        elif op_low == "matrix" and len(nums) >= 6:
            m = _multiply_affine(m, (nums[0], nums[1], nums[2], nums[3], nums[4], nums[5]))
    return m


def _composed_element_matrix(el) -> AffineMatrix:
    """Compose transforms from outermost SVG ancestor down to `el`."""
    chain = []
    curr = el
    while curr is not None and getattr(curr, "name", None) not in (None, "[document]"):
        chain.append(curr)
        if str(getattr(curr, "name", "")).lower() == "svg":
            break
        curr = getattr(curr, "parent", None)
    mat = _IDENTITY_MATRIX
    for node in reversed(chain):
        t_attr = node.get("transform") if hasattr(node, "get") else None
        if t_attr:
            mat = _multiply_affine(mat, _parse_svg_transform_attr(str(t_attr)))
    return mat


def _apply_matrix_to_bbox(
    bbox: Tuple[float, float, float, float],
    mat: AffineMatrix,
) -> Tuple[float, float, float, float]:
    if mat == _IDENTITY_MATRIX:
        return bbox
    x, y, w, h = bbox
    corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    a, b, c, d, e, f = mat
    txs = [a * px + c * py + e for px, py in corners]
    tys = [b * px + d * py + f for px, py in corners]
    min_x, max_x = min(txs), max(txs)
    min_y, max_y = min(tys), max(tys)
    return (min_x, min_y, max(0.0, max_x - min_x), max(0.0, max_y - min_y))


# ============================================================================
# F8: SVG SANITIZER
# ============================================================================

def sanitize_svg_markup(raw_svg: str) -> Tuple[str, bool, List[str]]:
    """
    F8: Sanitize SVG markup:
    - Removes <script>, <iframe>, <object>, <embed>, and <foreignObject> elements.
    - Removes <use> elements whose href/xlink:href does not start with '#'.
    - Removes any href/xlink:href attribute not starting with '#' or 'data:image/'.
    - Removes inline on* event handlers and javascript: URIs.
    - Removes @import rules and external url(http.../https...///...) references in <style> elements and style attributes.
    """
    soup = BeautifulSoup(raw_svg, "html.parser")
    sanitized_actions: List[str] = []

    for tag in list(soup.find_all(True)):
        tname = str(tag.name or "").lower()
        if tname in ("script", "iframe", "object", "embed", "foreignobject"):
            orig_name = tag.name
            tag.decompose()
            sanitized_actions.append(f"Removed <{orig_name}> element")

    # Sanitize <style> elements for @import and external url(...)
    for style_tag in list(soup.find_all("style")):
        css_text = style_tag.string if style_tag.string is not None else style_tag.get_text()
        if not css_text:
            continue
        new_css = css_text
        if re.search(r"@import\b", new_css, re.IGNORECASE):
            new_css = re.sub(r"@import\s+[^;]+;?", "", new_css, flags=re.IGNORECASE)
            sanitized_actions.append("Removed @import rule from <style> element")
        if re.search(r"url\s*\(\s*['\"]?\s*(?:https?:|//|javascript:|data:(?!image/))", new_css, re.IGNORECASE):
            new_css = re.sub(
                r"url\s*\(\s*['\"]?\s*(?:https?:|//|javascript:|data:(?!image/))[^)]*\)",
                "none",
                new_css,
                flags=re.IGNORECASE,
            )
            sanitized_actions.append("Removed external url() reference from <style> element")
        if new_css != css_text:
            style_tag.string = new_css

    for tag in list(soup.find_all(True)):
        if tag.attrs is None:
            continue
        tname = str(tag.name or "").lower()

        # Check <use> elements for external targets
        if tname == "use":
            use_href = None
            for k, v in list(tag.attrs.items()):
                if str(k).lower() in ("href", "xlink:href"):
                    use_href = " ".join(v) if isinstance(v, list) else str(v or "")
                    break
            if use_href is not None and not use_href.strip().startswith("#"):
                tag.decompose()
                sanitized_actions.append(f"Removed <use> element with external target '{use_href.strip()}'")
                continue

        attrs_to_remove = []
        attrs_to_update: Dict[str, str] = {}
        for attr_name, attr_val in list(tag.attrs.items()):
            low_name = str(attr_name).lower()
            val_str = " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val or "")
            val_strip = val_str.strip()
            val_low = val_strip.lower()

            if low_name.startswith("on"):
                attrs_to_remove.append(attr_name)
                sanitized_actions.append(f"Removed inline event attribute '{attr_name}'")
            elif "javascript:" in val_low:
                attrs_to_remove.append(attr_name)
                sanitized_actions.append(f"Removed javascript: URI in '{attr_name}'")
            elif low_name in ("href", "xlink:href") or low_name.endswith(":href"):
                if not (val_strip.startswith("#") or val_low.startswith("data:image/")):
                    attrs_to_remove.append(attr_name)
                    sanitized_actions.append(f"Removed external or disallowed '{attr_name}'='{val_strip}'")
            elif low_name == "style":
                clean_style = val_str
                if re.search(r"@import\b", clean_style, re.IGNORECASE):
                    clean_style = re.sub(r"@import\s+[^;]+;?", "", clean_style, flags=re.IGNORECASE)
                    sanitized_actions.append("Removed @import from inline style attribute")
                if re.search(r"url\s*\(\s*['\"]?\s*(?:https?:|//|javascript:|data:(?!image/))", clean_style, re.IGNORECASE):
                    clean_style = re.sub(
                        r"url\s*\(\s*['\"]?\s*(?:https?:|//|javascript:|data:(?!image/))[^)]*\)",
                        "none",
                        clean_style,
                        flags=re.IGNORECASE,
                    )
                    sanitized_actions.append("Removed external url() from inline style attribute")
                if clean_style != val_str:
                    attrs_to_update[attr_name] = clean_style

        for attr_name in attrs_to_remove:
            del tag.attrs[attr_name]
        for attr_name, new_val in attrs_to_update.items():
            tag.attrs[attr_name] = new_val

    return str(soup), len(sanitized_actions) > 0, sanitized_actions


def _svg_local_bbox(el, default_w: float, default_h: float) -> Optional[Tuple[float, float, float, float]]:
    """Compute untransformed local (x, y, width, height) bounding box for a single SVG shape/text element."""
    name = (el.name or "").lower()
    if name in ("rect", "image", "use", "svg"):
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
    return None


def _svg_element_bbox(el, default_w: float, default_h: float) -> Optional[Tuple[float, float, float, float]]:
    """
    F7(a): Compute world-space (x, y, width, height) bounding box for an SVG element,
    composing all ancestor and element 2D affine transforms.
    """
    name = (el.name or "").lower()
    if name == "g":
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
        x = _parse_svg_length(el.get("x"), 0.0)
        y = _parse_svg_length(el.get("y"), 0.0)
        w = _parse_svg_length(el.get("width"), 0.0)
        h = _parse_svg_length(el.get("height"), 0.0)
        if w > 0 and h > 0:
            return _apply_matrix_to_bbox((x, y, w, h), _composed_element_matrix(el))
        return None

    local_box = _svg_local_bbox(el, default_w, default_h)
    if local_box is None:
        return None
    mat = _composed_element_matrix(el)
    return _apply_matrix_to_bbox(local_box, mat)


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


def _has_logo_ancestor(el) -> bool:
    curr = el
    while curr is not None and getattr(curr, "name", None) not in (None, "[document]"):
        if _is_logo_element(curr):
            return True
        if str(getattr(curr, "name", "")).lower() == "svg":
            break
        curr = getattr(curr, "parent", None)
    return False


def _parse_svg_for_heatmap(raw_svg: str) -> Dict[str, Any]:
    """Sanitize SVG, render shapes to a Pillow RGBA image, and extract text & logo geometry with transforms."""
    sanitized_svg, was_sanitized, sanitized_actions = sanitize_svg_markup(raw_svg)
    soup = BeautifulSoup(sanitized_svg, "html.parser")
    svg_root = soup.find("svg")
    if not svg_root:
        raise ValueError("Uploaded file does not contain a root <svg> element.")

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

    render_w = min(2048, width)
    render_h = min(2048, height)
    sx = render_w / float(width)
    sy = render_h / float(height)

    root_bg = normalize_color_to_hex(
        _extract_style_prop(svg_root, "background-color")
        or _extract_style_prop(svg_root, "background"),
        default="#FFFFFF",
    )
    img = Image.new("RGBA", (render_w, render_h), hex_to_rgb(root_bg) + (255,))
    draw = ImageDraw.Draw(img)

    bg_rects: List[Tuple[float, float, float, float, str]] = []
    logo_box: Optional[Dict[str, Any]] = None
    other_boxes: List[Tuple[float, float, float, float]] = []

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

        resolved_fill, _ = _resolve_inherited_fill(el, default_if_unset=None)
        fill_hex = resolved_fill if (resolved_fill and resolved_fill != "Not measured") else None
        bbox = _svg_element_bbox(el, float(width), float(height))
        if not bbox:
            continue
        bx, by, bw, bh = bbox

        is_full_bg = (
            name == "rect"
            and bx <= 1.0
            and by <= 1.0
            and bw >= width * 0.9
            and bh >= height * 0.9
        )
        if name == "rect" and fill_hex:
            bg_rects.append((bx, by, bw, bh, fill_hex))

        if not _has_logo_ancestor(el) and not is_full_bg:
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

    # F7(a) & F7(b): Extract <text> elements with composed transforms and ancestor-inherited fill
    text_elements: List[Dict[str, Any]] = []
    for idx, t_el in enumerate(svg_root.find_all("text"), start=1):
        txt_str = t_el.get_text(" ", strip=True)
        if not txt_str:
            continue
        fg_resolved, fg_note = _resolve_inherited_fill(t_el, default_if_unset=None)
        fg_hex = fg_resolved if fg_resolved else "Not measured"

        tbbox = _svg_element_bbox(t_el, float(width), float(height))
        if not tbbox:
            tx = _parse_svg_length(t_el.get("x"), 0.0)
            ty = _parse_svg_length(t_el.get("y"), 16.0)
            tbbox = _apply_matrix_to_bbox((tx, max(0.0, ty - 16.0), 60.0, 16.0), _composed_element_matrix(t_el))

        cx_pt = tbbox[0] + tbbox[2] / 2.0
        cy_pt = tbbox[1] + tbbox[3] / 2.0
        effective_bg = root_bg
        for rx, ry, rw, rh, rfill in bg_rects:
            if (rx <= cx_pt <= (rx + rw) and ry <= cy_pt <= (ry + rh)) or (
                rx <= tbbox[0] <= (rx + rw) and ry <= (tbbox[1] + tbbox[3]) <= (ry + rh)
            ):
                effective_bg = rfill

        text_elements.append({
            "id": t_el.get("id") or f"svg-text-{idx}",
            "text": txt_str,
            "fg_hex": fg_hex,
            "fg_resolution_note": fg_note,
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


def _analyze_cell_colours(
    cell_rgba: np.ndarray,
    brand_colors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    F7(c) & F7(d): Compute dominant cell colour AND check any colour cluster covering >=2% of the cell
    against the Brand Vault palette.
    """
    alpha = cell_rgba[:, :, 3]
    opaque_mask = alpha >= 32
    total_px = cell_rgba.shape[0] * cell_rgba.shape[1]
    if total_px == 0 or not np.any(opaque_mask):
        return {
            "dominant_hex": None,
            "opaque_pct": 0.0,
            "off_palette_clusters": [],
        }

    rgb_pixels = cell_rgba[:, :, :3][opaque_mask]
    opaque_ratio = round(float(rgb_pixels.shape[0]) * 100.0 / float(total_px), 1)

    bins = rgb_pixels // 8
    unique_bins, inverse_idx, counts = np.unique(
        bins, axis=0, return_inverse=True, return_counts=True
    )
    order = np.argsort(-counts)
    best_bin_idx = int(order[0])
    dom_pixels = rgb_pixels[inverse_idx == best_bin_idx]
    dom_med = np.median(dom_pixels, axis=0)
    dom_hex = rgb_to_hex((
        int(round(float(dom_med[0]))),
        int(round(float(dom_med[1]))),
        int(round(float(dom_med[2]))),
    ))

    off_palette_clusters: List[Dict[str, Any]] = []
    if brand_colors:
        for b_idx in order:
            cnt = int(counts[b_idx])
            cov_pct = round(float(cnt) * 100.0 / float(total_px), 2)
            if cov_pct < OFF_PALETTE_CELL_MIN_PCT:
                break
            c_pixels = rgb_pixels[inverse_idx == int(b_idx)]
            c_med = np.median(c_pixels, axis=0)
            c_hex = rgb_to_hex((
                int(round(float(c_med[0]))),
                int(round(float(c_med[1]))),
                int(round(float(c_med[2]))),
            ))
            closest = find_closest_brand_color(c_hex, brand_colors)
            if closest and float(closest["delta_e"]) > float(closest["max_delta_e"]):
                off_palette_clusters.append({
                    "hex": c_hex,
                    "coverage_pct": cov_pct,
                    "closest_brand_color": str(closest["name"]),
                    "closest_brand_hex": str(closest["hex_code"]),
                    "delta_e": float(closest["delta_e"]),
                    "max_delta_e": float(closest["max_delta_e"]),
                })

    return {
        "dominant_hex": dom_hex,
        "opaque_pct": opaque_ratio,
        "off_palette_clusters": off_palette_clusters,
    }


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
    decoded_image: Optional[Image.Image] = None,
) -> Dict[str, Any]:
    """Run N x N Palette CIE Delta-E, Known-Text WCAG Contrast, and Logo Clear-Space Heatmap analysis."""
    if isinstance(brand_colors, str):
        filename = brand_colors
        brand_colors = []
    brand = brand or {}
    brand_colors = list(brand_colors or [])
    has_palette = len(brand_colors) > 0
    n_grid = max(2, min(8, int(grid_size or 4)))
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in (filename or "") else ".png"

    is_svg = (ext == ".svg")
    svg_meta: Dict[str, Any] = {}

    if is_svg:
        try:
            decoded_svg = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded_svg = raw_bytes.decode("utf-8", errors="replace")
        try:
            svg_meta = _parse_svg_for_heatmap(decoded_svg)
            rgba_img = svg_meta["rgba_image"]
            orig_w = int(svg_meta["original_width"])
            orig_h = int(svg_meta["original_height"])
        except Exception as exc:
            return {
                "inspect_ok": False,
                "error": f"SVG could not be parsed ({str(exc)}).",
            }
    else:
        try:
            if decoded_image is not None:
                orig_w, orig_h = decoded_image.size
                if int(orig_w) * int(orig_h) > MAX_IMAGE_PIXELS:
                    raise ImageTooLargeError(
                        f"Image resolution {orig_w}x{orig_h} ({int(orig_w) * int(orig_h):,} pixels) exceeds the 12 megapixel limit (reduced from previous 25 megapixel limit)."
                    )
                rgba_img = decoded_image
            else:
                rgba_img = probe_and_decode_raster_image(raw_bytes)
                orig_w, orig_h = rgba_img.size
        except ImageTooLargeError as exc:
            return {
                "inspect_ok": False,
                "too_large": True,
                "status_code": 400,
                "error": str(exc),
            }
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
        analyzed_w, analyzed_h = rgba_img.size

    arr = np.array(rgba_img)

    # C1 & F7(c)/(d): N x N Grid analysis
    cells: List[Dict[str, Any]] = []
    flagged_cells_count = 0
    for r_idx in range(n_grid):
        y0 = int(round(r_idx * analyzed_h / float(n_grid)))
        y1 = int(round((r_idx + 1) * analyzed_h / float(n_grid)))
        for c_idx in range(n_grid):
            x0 = int(round(c_idx * analyzed_w / float(n_grid)))
            x1 = int(round((c_idx + 1) * analyzed_w / float(n_grid)))

            cell_slice = arr[y0:y1, x0:x1]
            cell_info = _analyze_cell_colours(cell_slice, brand_colors)
            dom_hex = cell_info["dominant_hex"]
            opaque_pct = cell_info["opaque_pct"]
            off_clusters = cell_info["off_palette_clusters"]
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
                    "closest_brand_color": "Transparent" if has_palette else "Not Checked",
                    "closest_brand_hex": "",
                    "min_delta_e": 0.0,
                    "threshold_delta_e": 14.0,
                    "flagged": False,
                    "status": "transparent" if has_palette else "not_checked",
                    "pattern": "dots",
                    "off_palette_clusters": [],
                })
                continue

            if not has_palette:
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
                    "closest_brand_color": "Not Checked (no brand palette)",
                    "closest_brand_hex": "",
                    "min_delta_e": None,
                    "delta_e": None,
                    "threshold_delta_e": None,
                    "max_delta_e": None,
                    "flagged": False,
                    "status": "not_checked",
                    "pattern": "solid",
                    "off_palette_clusters": [],
                })
                continue

            closest = find_closest_brand_color(dom_hex, brand_colors)
            min_de = float(closest["delta_e"])
            thresh_de = float(closest["max_delta_e"])
            dom_flagged = bool(min_de > thresh_de)
            c_name = str(closest["name"])
            c_hex = str(closest["hex_code"])

            # F7(d): Also flag cell if any secondary colour cluster covering >=2% of the cell is off-palette
            is_flagged = dom_flagged or (len(off_clusters) > 0)
            flagged_swatch = None
            if not dom_flagged and off_clusters:
                flagged_swatch = max(off_clusters, key=lambda item: float(item["delta_e"]))
                min_de = float(flagged_swatch["delta_e"])
                thresh_de = float(flagged_swatch["max_delta_e"])
                c_name = str(flagged_swatch["closest_brand_color"])
                c_hex = str(flagged_swatch["closest_brand_hex"])

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
                "dominant_hex": flagged_swatch["hex"] if flagged_swatch else dom_hex,
                "cell_dominant_hex": dom_hex,
                "flagged_hex": flagged_swatch["hex"] if flagged_swatch else (dom_hex if is_flagged else None),
                "flagged_coverage_pct": flagged_swatch["coverage_pct"] if flagged_swatch else (opaque_pct if is_flagged else 0.0),
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
                "off_palette_clusters": off_clusters,
            })

    # C2 & F7(b): Text contrast (only for SVG <text> elements or user-marked regions; no OCR)
    min_contrast_req = float(brand.get("min_contrast_normal", 4.5))
    raw_text_items: List[Dict[str, Any]] = []
    if is_svg:
        raw_text_items.extend(svg_meta.get("text_elements", []))
    for idx, reg in enumerate(text_regions or [], start=1):
        if not isinstance(reg, dict):
            continue
        raw_fg = reg.get("fg_hex")
        if isinstance(raw_fg, str) and raw_fg.strip().lower() == "currentcolor":
            fg_h = "Not measured"
        else:
            fg_h = normalize_color_to_hex(raw_fg, default=None)
        bg_h = normalize_color_to_hex(reg.get("bg_hex") or default_bg_color, default="#FFFFFF")
        rx = float(reg.get("x", 0.0))
        ry = float(reg.get("y", 0.0))
        rw = float(reg.get("width", 40.0))
        rh = float(reg.get("height", 20.0))
        if not fg_h:
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
                fg_h = "Not measured"
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
    measured_contrast_count = 0
    for item in raw_text_items:
        fg_h = item["fg_hex"]
        bg_h = item["bg_hex"]
        if default_bg_color and is_valid_hex(default_bg_color) and item.get("source") == "svg_text" and bg_h == "#FFFFFF":
            bg_h = normalize_color_to_hex(default_bg_color, default="#FFFFFF")

        tc_x = float(item.get("x", 0.0)) + float(item.get("width", 0.0)) / 2.0
        tc_y = float(item.get("y", 0.0)) + float(item.get("height", 0.0)) / 2.0
        tc_c = max(1, min(n_grid, int(tc_x * n_grid / max(1.0, float(orig_w if is_svg else analyzed_w))) + 1))
        tc_r = max(1, min(n_grid, int(tc_y * n_grid / max(1.0, float(orig_h if is_svg else analyzed_h))) + 1))

        if not fg_h or fg_h == "Not measured" or not is_valid_hex(fg_h) or not bg_h or not is_valid_hex(bg_h):
            contrast_items.append({
                **item,
                "fg_hex": "Not measured",
                "bg_hex": bg_h,
                "cell_id": item.get("cell_id") or f"R{tc_r}C{tc_c}",
                "contrast_ratio": None,
                "min_required": min_contrast_req,
                "required_ratio": min_contrast_req,
                "passed": None,
                "flagged": False,
                "status": "Not measured",
            })
            continue

        measured_contrast_count += 1
        ratio = wcag_contrast_ratio(fg_h, bg_h)
        passed = bool(ratio >= min_contrast_req)
        if not passed:
            flagged_contrast_count += 1
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
        f"Contrast measured for {measured_contrast_count} text elements; text inside raster images is not detected."
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

    palette_state = (
        "Not Checked"
        if not has_palette
        else ("Findings" if flagged_cells_count > 0 else "Passed")
    )

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
        "palette_state": palette_state,
        "off_palette_min_cell_coverage_pct": OFF_PALETTE_CELL_MIN_PCT,
        "cells": cells,
        "text_contrast": {
            "measured_count": measured_contrast_count,
            "total_elements_count": len(contrast_items),
            "flagged_count": flagged_contrast_count,
            "state": (
                "Not Checked"
                if measured_contrast_count == 0
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
