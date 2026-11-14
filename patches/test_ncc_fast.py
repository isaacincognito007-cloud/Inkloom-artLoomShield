import numpy as np
from PIL import Image
import time
from scipy.signal import fftconvolve

def match_template_ncc_fast(search_gray: np.ndarray, template_gray: np.ndarray, scales=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0), threshold=0.80):
    sh, sw = search_gray.shape
    th, tw = template_gray.shape

    # Precompute integral images once for search_gray
    s_img = search_gray.astype(np.float32)
    # Integral images (padded with 0 on top and left)
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
        
        tpl_pil = Image.fromarray(template_gray.astype(np.uint8)).resize((target_w, target_h), Image.Resampling.BILINEAR)
        tpl = np.array(tpl_pil, dtype=np.float32)
        tpl_norm = tpl - np.mean(tpl)
        tpl_denom = np.sqrt(np.sum(tpl_norm ** 2))
        if tpl_denom < 1e-5:
            continue
        tpl_norm = (tpl_norm / tpl_denom).astype(np.float32)

        # Single FFT convolution
        corr = fftconvolve(s_img, tpl_norm[::-1, ::-1], mode='valid')

        # Fast local mean and variance from integral images
        # Window corners: y to y+target_h, x to x+target_w
        # Mode valid has shape (sh - target_h + 1, sw - target_w + 1)
        h_out, w_out = corr.shape
        y_idx = np.arange(h_out)
        x_idx = np.arange(w_out)
        
        # Sub-boxes from integral image
        y0, y1 = 0, h_out
        x0, x1 = 0, w_out
        
        # S = I(y+H, x+W) - I(y, x+W) - I(y+H, x) + I(y, x)
        S_sum = (int_s[target_h:target_h+h_out, target_w:target_w+w_out]
                 - int_s[0:h_out, target_w:target_w+w_out]
                 - int_s[target_h:target_h+h_out, 0:w_out]
                 + int_s[0:h_out, 0:w_out])
                 
        S_sq = (int_sq[target_h:target_h+h_out, target_w:target_w+w_out]
                - int_sq[0:h_out, target_w:target_w+w_out]
                - int_sq[target_h:target_h+h_out, 0:w_out]
                + int_sq[0:h_out, 0:w_out])
                
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

template = np.zeros((40, 80), dtype=np.uint8)
template[10:30, 20:60] = 200

search = np.ones((400, 600), dtype=np.uint8) * 50
search[100:140, 200:280] = template

t0 = time.perf_counter()
bbox, score, scale = match_template_ncc_fast(search, template)
dt = time.perf_counter() - t0
print(f"Fast NCC Match result: score={score:.4f}, scale={scale}, bbox={bbox}, elapsed={dt*1000:.2f}ms")
assert score > 0.99
assert bbox["x"] == 200 and bbox["y"] == 100
print("Fast NCC test PASSED!")
