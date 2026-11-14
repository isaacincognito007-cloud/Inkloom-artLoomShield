import numpy as np
from PIL import Image
import time

def match_template_ncc(search_gray: np.ndarray, template_gray: np.ndarray, scales=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0), threshold=0.80):
    """
    Multi-scale Normalized Cross-Correlation in NumPy.
    search_gray: 2D float32 array
    template_gray: 2D float32 array
    returns: (bbox_dict, best_score, best_scale) or None
    """
    sh, sw = search_gray.shape
    th, tw = template_gray.shape
    
    best_score = -1.0
    best_bbox = None
    best_scale = 1.0

    # Ensure search_gray is float32
    s_img = search_gray.astype(np.float32)

    for scale in scales:
        target_w = int(round(tw * scale))
        target_h = int(round(th * scale))
        if target_w < 8 or target_h < 8 or target_w >= sw or target_h >= sh:
            continue
        
        # Resize template
        tpl_pil = Image.fromarray(template_gray.astype(np.uint8)).resize((target_w, target_h), Image.Resampling.BILINEAR)
        tpl = np.array(tpl_pil, dtype=np.float32)
        
        tpl_mean = np.mean(tpl)
        tpl_norm = tpl - tpl_mean
        tpl_denom = np.sqrt(np.sum(tpl_norm ** 2))
        if tpl_denom < 1e-5:
            continue
            
        tpl_norm = tpl_norm / tpl_denom
        
        # Fast sliding window NCC or via scipy.signal.correlate2d
        # Let's test scipy.signal.fftconvolve or correlate
        try:
            from scipy.signal import fftconvolve
            # Cross correlation of s_img with flipped tpl_norm
            corr = fftconvolve(s_img, tpl_norm[::-1, ::-1], mode='valid')
            
            # Local window sum and sum of squares for s_img
            ones = np.ones((target_h, target_w), dtype=np.float32)
            s_sum = fftconvolve(s_img, ones, mode='valid')
            s_sq_sum = fftconvolve(s_img ** 2, ones, mode='valid')
            
            n_pix = float(target_w * target_h)
            s_mean = s_sum / n_pix
            s_var = (s_sq_sum - (s_sum ** 2) / n_pix)
            s_std = np.sqrt(np.maximum(s_var, 1e-5))
            
            # NCC = (corr - s_mean * sum(tpl_norm)) / s_std = corr / s_std (since sum(tpl_norm) == 0!)
            ncc = corr / s_std
            
            max_idx = np.unravel_index(np.argmax(ncc), ncc.shape)
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
        except Exception as e:
            print("fftconvolve error:", e)
            
    if best_score >= threshold and best_bbox is not None:
        return best_bbox, best_score, best_scale
    return None, best_score, best_scale

# Test with synthetic image
template = np.zeros((40, 80), dtype=np.uint8)
template[10:30, 20:60] = 200

search = np.ones((400, 600), dtype=np.uint8) * 50
search[100:140, 200:280] = template

t0 = time.perf_counter()
bbox, score, scale = match_template_ncc(search.astype(np.float32), template.astype(np.float32))
dt = time.perf_counter() - t0
print(f"Match result: score={score:.4f}, scale={scale}, bbox={bbox}, elapsed={dt*1000:.2f}ms")
assert score > 0.99, f"Score {score} too low"
assert bbox["x"] == 200 and bbox["y"] == 100, f"Incorrect bbox: {bbox}"
print("Synthetic NCC test passed!")
