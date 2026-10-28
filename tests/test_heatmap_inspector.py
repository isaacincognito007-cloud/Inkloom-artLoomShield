import io
import os
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.database import init_db, reset_demo_workspace
from backend.heatmap import inspect_visual_heatmap
from backend.main import app, get_brand_vault_bundle

client = TestClient(app)


def setup_function():
    os.environ["LOOMSHIELD_WORKSPACE_MODE"] = "demo"
    init_db()
    reset_demo_workspace()


def test_c5_on_palette_tile_all_cells_pass():
    vault = get_brand_vault_bundle("novapay")
    # #17191C is NovaPay Primary Ink (RGB 23, 25, 28), an approved primary colour
    img = Image.new("RGBA", (200, 200), (23, 25, 28, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    res = inspect_visual_heatmap(
        raw_bytes=buf.getvalue(),
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="on_palette.png",
        grid_size=4,
    )
    assert res["inspect_ok"] is True
    assert res["grid_size"] == 4
    assert res["total_cells"] == 16
    assert res["flagged_cells_count"] == 0
    assert res["palette_state"] == "Passed"
    assert all(c["flagged"] is False and c["status"] == "pass" for c in res["cells"])


def test_c5_one_off_palette_quadrant_flags_exact_cell_and_cites_coordinates():
    vault = get_brand_vault_bundle("novapay")
    # 2x2 grid (4 quadrants): fill entire 200x200 image with approved #17191C (23, 25, 28),
    # then paint bottom-right quadrant (R2C2: x 100..200, y 100..200) bright neon magenta #FF00FF
    img = Image.new("RGBA", (200, 200), (23, 25, 28, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 200, 200], fill=(255, 0, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    res = inspect_visual_heatmap(
        raw_bytes=buf.getvalue(),
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="one_quadrant_off.png",
        grid_size=2,
    )
    assert res["inspect_ok"] is True
    assert res["total_cells"] == 4
    assert res["flagged_cells_count"] == 1
    flagged = [c for c in res["cells"] if c["flagged"]]
    assert len(flagged) == 1
    assert flagged[0]["cell_id"] == "R2C2"
    assert flagged[0]["min_delta_e"] > flagged[0]["threshold_delta_e"]
    assert flagged[0]["pattern"] == "hatch"

    # Also verify full upload audit cites Cell R2C2 in Visual and Logo Consistency findings
    upload_res = client.post(
        "/api/audits/upload",
        data={
            "brand_id": "novapay",
            "document_name": "Quadrant Heatmap Test",
            "grid_size": "2",
            "image_alt_text": "NovaPay settlement dashboard tile with four quadrants.",
        },
        files={"file": ("quadrant.png", buf.getvalue(), "image/png")},
    )
    assert upload_res.status_code == 200
    audit = upload_res.json()
    vis_findings = [f for f in audit["findings"] if f["pillar"] == "Visual and Logo Consistency"]
    assert len(vis_findings) == 1
    assert "Cell R2C2" in vis_findings[0]["flagged_text"]
    assert vis_findings[0]["paragraph_ref"] == "Cell R2C2"


def test_c5_svg_with_low_contrast_text_flagged_with_measured_ratio():
    vault = get_brand_vault_bundle("novapay")
    svg_bytes = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">
      <title>NovaPay Card Graphic</title>
      <rect x="0" y="0" width="400" height="200" fill="#FFFFFF" />
      <text x="40" y="80" fill="#CBD5E1" font-size="16">Low contrast subtitle</text>
      <text x="40" y="130" fill="#0F172A" font-size="16">High contrast headline</text>
    </svg>"""

    res = inspect_visual_heatmap(
        raw_bytes=svg_bytes,
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="contrast_test.svg",
        grid_size=4,
    )
    tc = res["text_contrast"]
    assert tc["measured_count"] == 2
    assert tc["flagged_count"] == 1
    assert tc["state"] == "Findings"
    assert tc["disclosure"] == "Contrast measured for 2 text elements; text inside raster images is not detected."

    failed_el = next(e for e in tc["elements"] if not e["passed"])
    assert failed_el["contrast_ratio"] < 4.5
    assert "Low contrast subtitle" in failed_el["text"]


def test_c5_svg_logo_too_close_to_edge_fails_with_measured_px_and_no_logo_not_checked():
    vault = get_brand_vault_bundle("novapay")
    # Logo placed at x=2, y=3 (only 2px from left edge, below required 16px / 0.25x ratio)
    crowded_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200" width="300" height="200">
      <title>Crowded Logo Lockup</title>
      <rect x="0" y="0" width="300" height="200" fill="#FFFFFF" />
      <rect id="logo" data-loomshield-logo="true" x="2" y="3" width="80" height="40" fill="#0F172A" />
    </svg>"""

    res_crowded = inspect_visual_heatmap(
        raw_bytes=crowded_svg,
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="crowded_logo.svg",
    )
    cs = res_crowded["clear_space"]
    assert cs["state"] == "Findings"
    assert cs["checked"] is True
    assert cs["passed"] is False
    assert cs["min_distance_px"] == 2.0
    assert cs["measured_ratio"] == 0.05  # 2px / 40px height

    # No logo marked -> Not Checked with plain reason
    no_logo_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200" width="300" height="200">
      <title>Plain Graphic Without Logo Marker</title>
      <rect x="0" y="0" width="300" height="200" fill="#0F172A" />
    </svg>"""
    res_nologo = inspect_visual_heatmap(
        raw_bytes=no_logo_svg,
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="no_logo.svg",
    )
    assert res_nologo["clear_space"]["state"] == "Not Checked"
    assert res_nologo["clear_space"]["checked"] is False
    assert "No logo location was specified" in res_nologo["clear_space"]["reason"]


def test_c5_oversized_image_downscaled_and_svg_script_sanitised_and_shape_stable():
    vault = get_brand_vault_bundle("novapay")
    # Oversized 1600x1200 image -> downscaled to at most 1024px on longest side
    big_img = Image.new("RGBA", (1600, 1200), (15, 23, 42, 255))
    buf = io.BytesIO()
    big_img.save(buf, format="PNG")

    res_big = inspect_visual_heatmap(
        raw_bytes=buf.getvalue(),
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="oversized.png",
        grid_size=4,
    )
    assert res_big["downscaled"] is True
    assert res_big["original_width"] == 1600
    assert res_big["original_height"] == 1200
    assert res_big["analyzed_width"] == 1024
    assert res_big["analyzed_height"] == 768

    # SVG with <script> tag and onload attribute -> sanitised
    malicious_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" onload="alert(1)">
      <title>Malicious SVG</title>
      <script>alert('xss')</script>
      <rect x="10" y="10" width="180" height="180" fill="#0F172A" onclick="steal()" />
    </svg>"""
    res_svg = inspect_visual_heatmap(
        raw_bytes=malicious_svg,
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename="malicious.svg",
        grid_size=4,
    )
    assert res_svg["svg_sanitized"] is True
    assert "<script" not in (res_svg["sanitized_svg"] or "").lower()
    assert "onload" not in (res_svg["sanitized_svg"] or "").lower()
    assert "onclick" not in (res_svg["sanitized_svg"] or "").lower()

    # Verify stable response keys across raster and SVG
    expected_top_keys = {
        "inspect_ok",
        "format",
        "original_width",
        "original_height",
        "analyzed_width",
        "analyzed_height",
        "downscaled",
        "grid_size",
        "total_cells",
        "flagged_cells_count",
        "palette_state",
        "cells",
        "text_contrast",
        "clear_space",
        "svg_sanitized",
        "sanitized_actions",
        "sanitized_svg",
    }
    assert expected_top_keys.issubset(set(res_big.keys()))
    assert expected_top_keys.issubset(set(res_svg.keys()))
