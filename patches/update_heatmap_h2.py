with open("backend/heatmap.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add imports if not present
if "import base64" not in text:
    text = text.replace("import io\n", "import base64\nimport io\n")

if "from scipy.signal import fftconvolve" not in text:
    text = text.replace("import numpy as np\n", "import numpy as np\ntry:\n    from scipy.signal import fftconvolve\nexcept ImportError:\n    fftconvolve = None\n")

# Add match_template_ncc_fast function before inspect_visual_heatmap
ncc_func = '''def match_template_ncc_fast(
    search_gray: np.ndarray,
    template_gray: np.ndarray,
    scales: Tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    threshold: float = 0.80,
) -> Tuple[Optional[Dict[str, float]], float, float]:
    """H2: Multi-scale Normalized Cross-Correlation (NumPy/SciPy, grayscale, scales 0.5-2.0, threshold 0.80)."""
    if fftconvolve is None:
        return None, -1.0, 1.0
    sh, sw = search_gray.shape
    th, tw = template_gray.shape

    s_img = search_gray.astype(np.float32)
    int_s = np.zeros((sh + 1, sw + 1), dtype=np.float64)
    int_sq = np.zeros((sh + 1, sw + 1), dtype=np.float64)

    int_s[1:, 1:] = np.cumsum(np.cumsum(s_img, axis=0, dtype=np.float64), axis=1, dtype=np.float64)
    int_sq[1:, 1:] = np.cumsum(np.cumsum(s_img ** 2, axis=0, dtype=np.float64), axis=1, dtype=np.float64)

    best_score = -1.0
    best_bbox = None
    best_scale = 1.0

    for scale in scales:
        target_w = int(round(tw * scale))
        target_h = int(round(th * scale))
        if target_w < 8 or target_h < 8 or target_w >= sw or target_h >= sh:
            continue

        tpl_pil = Image.fromarray(template_gray.astype(np.uint8)).resize(
            (target_w, target_h), Image.Resampling.BILINEAR
        )
        tpl = np.array(tpl_pil, dtype=np.float32)
        tpl_norm = tpl - np.mean(tpl)
        tpl_denom = np.sqrt(np.sum(tpl_norm ** 2))
        if tpl_denom < 1e-5:
            continue
        tpl_norm = (tpl_norm / tpl_denom).astype(np.float32)

        corr = fftconvolve(s_img, tpl_norm[::-1, ::-1], mode="valid")

        h_out, w_out = corr.shape
        S_sum = (
            int_s[target_h:target_h + h_out, target_w:target_w + w_out]
            - int_s[0:h_out, target_w:target_w + w_out]
            - int_s[target_h:target_h + h_out, 0:w_out]
            + int_s[0:h_out, 0:w_out]
        )
        S_sq = (
            int_sq[target_h:target_h + h_out, target_w:target_w + w_out]
            - int_sq[0:h_out, target_w:target_w + w_out]
            - int_sq[target_h:target_h + h_out, 0:w_out]
            + int_sq[0:h_out, 0:w_out]
        )

        n_pix = float(target_w * target_h)
        var = S_sq - (S_sum ** 2) / n_pix
        std = np.sqrt(np.maximum(var, 1e-5, dtype=np.float64)).astype(np.float32)

        ncc = corr / std
        max_flat_idx = np.argmax(ncc)
        max_idx = np.unravel_index(max_flat_idx, ncc.shape)
        scale_best = float(ncc[max_idx])

        if scale_best > best_score:
            best_score = scale_best
            best_scale = scale
            best_bbox = {
                "x": float(max_idx[1]),
                "y": float(max_idx[0]),
                "width": float(target_w),
                "height": float(target_h),
            }

    if best_score >= threshold and best_bbox is not None:
        return best_bbox, best_score, best_scale
    return None, best_score, best_scale


'''

if "def match_template_ncc_fast" not in text:
    target_pos = "def inspect_visual_heatmap("
    assert target_pos in text
    text = text.replace(target_pos, ncc_func + target_pos)

# Now update the logo resolution block in inspect_visual_heatmap
target_logo_block = '''    if isinstance(logo_rect, dict) and float(logo_rect.get("width", 0)) > 0 and float(logo_rect.get("height", 0)) > 0:
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
        }'''

replacement_logo_block = '''    template_match_attempted = False
    template_match_score = -1.0

    # H2: Logo precedence: 1) user-drawn box, 2) SVG marker, 3) template match, 4) logo-only PNG alpha box
    if isinstance(logo_rect, dict) and float(logo_rect.get("width", 0)) > 0 and float(logo_rect.get("height", 0)) > 0:
        resolved_logo = {
            "x": float(logo_rect.get("x", 0.0)),
            "y": float(logo_rect.get("y", 0.0)),
            "width": float(logo_rect["width"]),
            "height": float(logo_rect["height"]),
            "source": "user_drawn_rect",
            "located_method": "User-drawn box",
        }
        canvas_for_logo_w = float(analyzed_w)
        canvas_for_logo_h = float(analyzed_h)
    elif is_svg and svg_meta.get("logo_box"):
        resolved_logo = dict(svg_meta["logo_box"])
        resolved_logo["located_method"] = "SVG marker"
        resolved_logo["source"] = "svg_marker"
        canvas_for_logo_w = float(orig_w)
        canvas_for_logo_h = float(orig_h)
    else:
        # Check template match if approved logo asset is configured in Brand Vault
        approved_logo_b64 = str(brand.get("approved_logo_b64") or "").strip()
        if approved_logo_b64 and not is_svg and arr is not None:
            try:
                raw_logo_data = base64.b64decode(approved_logo_b64.split(",")[-1])
                tpl_img = Image.open(io.BytesIO(raw_logo_data)).convert("L")
                template_gray = np.array(tpl_img, dtype=np.float32)
                search_gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
                t_bbox, t_score, t_scale = match_template_ncc_fast(search_gray, template_gray, threshold=0.80)
                template_match_attempted = True
                template_match_score = t_score
                if t_bbox is not None:
                    resolved_logo = {
                        **t_bbox,
                        "source": "template_match",
                        "located_method": f"Template match (NCC score: {t_score:.2f})",
                        "score": round(t_score, 4),
                        "scale": t_scale,
                    }
                    canvas_for_logo_w = float(analyzed_w)
                    canvas_for_logo_h = float(analyzed_h)
            except Exception:
                pass

        # 4) logo-only PNG alpha box fallback
        if resolved_logo is None and logo_only and not is_svg and arr is not None:
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
                    "located_method": "Logo-only PNG alpha box",
                }
                canvas_for_logo_w = float(analyzed_w)
                canvas_for_logo_h = float(analyzed_h)

    if resolved_logo is None:
        if template_match_attempted:
            no_logo_reason = "Not Checked: approved logo not found"
        else:
            no_logo_reason = (
                "No logo location was specified. Upload an approved brand logo in the Brand Vault, "
                "mark an SVG element with data-loomshield-logo (or id/class 'logo'), "
                "draw a logo rectangle in the Heatmap Inspector, or mark a transparent PNG as logo-only."
            )
        clear_space = {
            "state": "Not Checked",
            "status": "Not Checked",
            "checked": False,
            "passed": None,
            "located_method": "None",
            "logo_box": None,
            "edge_distances_px": None,
            "nearest_content_px": None,
            "min_distance_px": None,
            "logo_height_px": None,
            "measured_ratio": None,
            "required_ratio": required_ratio,
            "required_px": required_px,
            "reason": no_logo_reason,
        }'''

assert target_logo_block in text, "target_logo_block not found in heatmap.py"
text = text.replace(target_logo_block, replacement_logo_block)

# In clear_space dict when logo is found, ensure located_method is populated
cs_loc_target = '''            "logo_box": {
                "x": round(lx, 2),
                "y": round(ly, 2),
                "width": round(lw, 2),
                "height": round(lh, 2),
                "source": resolved_logo["source"],
            },'''

cs_loc_replacement = '''            "located_method": resolved_logo.get("located_method") or resolved_logo.get("source"),
            "logo_box": {
                "x": round(lx, 2),
                "y": round(ly, 2),
                "width": round(lw, 2),
                "height": round(lh, 2),
                "source": resolved_logo["source"],
                "located_method": resolved_logo.get("located_method") or resolved_logo["source"],
            },'''

assert cs_loc_target in text, "cs_loc_target not found in heatmap.py"
text = text.replace(cs_loc_target, cs_loc_replacement)

with open("backend/heatmap.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated backend/heatmap.py successfully with fast NCC and logo precedence")
