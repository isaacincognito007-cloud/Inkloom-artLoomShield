import io
import os

import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.database import init_db, reset_demo_workspace
from backend.heatmap import inspect_visual_heatmap
from backend.main import app, get_brand_vault_bundle

client = TestClient(app)


@pytest.fixture(autouse=True)
def demo_workspace(monkeypatch):
    # F11: scoped via monkeypatch so demo mode never leaks into other test modules.
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    init_db()
    reset_demo_workspace()
    yield


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


# ============================================================================
# DAY 3 HARDENING: F1, F2, F3, F7, F8
# ============================================================================

import asyncio
import time

from fastapi import HTTPException

import backend.engine as engine_mod
import backend.heatmap as heatmap_mod
import backend.main as main_mod
from backend.engine import MAX_IMAGE_PIXELS, ImageTooLargeError, probe_and_decode_raster_image
from backend.heatmap import sanitize_svg_markup


def _solid_png_bytes(width, height, mode="1", color=1):
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    img.close()
    return buf.getvalue()


def test_f1_9000x9000_png_rejected_quickly_before_decode_and_decoded_once_for_both_analyzers(monkeypatch):
    assert MAX_IMAGE_PIXELS == 12_000_000
    assert Image.MAX_IMAGE_PIXELS == 12_000_000

    huge_png = _solid_png_bytes(9000, 9000)
    assert len(huge_png) < 200 * 1024

    # Direct probe: rejected from header size, no RGBA decode.
    t0 = time.perf_counter()
    try:
        probe_and_decode_raster_image(huge_png)
        raised = False
    except ImageTooLargeError:
        raised = True
    probe_s = time.perf_counter() - t0
    assert raised is True
    assert probe_s < 1.0

    # Heatmap analyzer reports too_large (400) without decoding.
    vault = get_brand_vault_bundle("novapay")
    hm = inspect_visual_heatmap(raw_bytes=huge_png, brand_colors=vault["colors"], brand=vault["brand"], filename="huge.png")
    assert hm["inspect_ok"] is False
    assert hm["too_large"] is True
    assert hm["status_code"] == 400

    # Upload route: 400 with a plain message, quickly.
    t1 = time.perf_counter()
    res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "Huge PNG"},
        files={"file": ("huge.png", huge_png, "image/png")},
    )
    upload_s = time.perf_counter() - t1
    assert res.status_code == 400
    assert "25 megapixel" in res.json()["detail"]
    assert upload_s < 2.0

    # Decode once and share: the upload route decodes exactly once; neither analyzer re-decodes.
    calls = {"main": 0, "engine": 0, "heatmap": 0}
    real_probe = probe_and_decode_raster_image

    def _counter(key):
        def _wrapped(raw):
            calls[key] += 1
            return real_probe(raw)
        return _wrapped

    monkeypatch.setattr(main_mod, "probe_and_decode_raster_image", _counter("main"))
    monkeypatch.setattr(engine_mod, "probe_and_decode_raster_image", _counter("engine"))
    monkeypatch.setattr(heatmap_mod, "probe_and_decode_raster_image", _counter("heatmap"))
    small = _solid_png_bytes(200, 200, mode="RGBA", color=(23, 25, 28, 255))
    ok = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "Small PNG", "image_alt_text": "Solid ink tile."},
        files={"file": ("small.png", small, "image/png")},
    )
    assert ok.status_code == 200
    assert calls == {"main": 1, "engine": 0, "heatmap": 0}


def test_f1_4000x4000_image_under_limit_is_accepted():
    # G2: 12 MP (4000x3000) is accepted at the new 12 megapixel limit and downscaled.
    png = _solid_png_bytes(4000, 3000, mode="RGB", color=(23, 25, 28))
    rgba = probe_and_decode_raster_image(png)
    assert rgba.size == (4000, 3000)
    vault = get_brand_vault_bundle("novapay")
    hm = inspect_visual_heatmap(
        raw_bytes=png, brand_colors=vault["colors"], brand=vault["brand"], filename="big.png", decoded_image=rgba
    )
    assert hm["inspect_ok"] is True
    assert hm["downscaled"] is True
    assert hm["original_width"] == 4000


class _CountingUpload:
    """Minimal async UploadFile stand-in that records how many bytes were actually read."""

    def __init__(self, total_bytes):
        self.remaining = total_bytes
        self.bytes_read = 0

    async def read(self, size=-1):
        n = self.remaining if size is None or size < 0 else min(size, self.remaining)
        self.remaining -= n
        self.bytes_read += n
        return b"\x00" * n


def test_f2_chunked_upload_aborts_at_5mb_plus_1_byte_on_6mb_body():
    six_mb = 6 * 1024 * 1024
    limit = 5 * 1024 * 1024

    # Handler-level chunked reader stops at exactly 5 MB + 1 byte.
    fake = _CountingUpload(six_mb)
    try:
        asyncio.run(main_mod._read_upload_in_chunks(fake))
        raised = None
    except HTTPException as exc:
        raised = exc
    assert raised is not None and raised.status_code == 400
    assert fake.bytes_read == limit + 1
    assert fake.remaining == six_mb - (limit + 1)

    # Exactly 5 MB is accepted.
    exact = _CountingUpload(limit)
    data = asyncio.run(main_mod._read_upload_in_chunks(exact))
    assert len(data) == limit

    # Route level: a 6 MB body is rejected with 400.
    res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "Six MB"},
        files={"file": ("big.txt", b"a" * six_mb, "text/plain")},
    )
    assert res.status_code == 400
    assert "5 MB" in res.json()["detail"]


def test_f3_standalone_heatmap_inspect_removed_and_audit_heatmap_requires_run_audits_and_rate_limit(monkeypatch):
    png = _solid_png_bytes(200, 200, mode="RGBA", color=(23, 25, 28, 255))
    removed = client.post("/api/heatmap/inspect", files={"file": ("a.png", png, "image/png")})
    assert removed.status_code in (404, 405)
    assert all(getattr(r, "path", "") != "/api/heatmap/inspect" for r in main_mod.app.routes)

    up = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "Heatmap Perm", "image_alt_text": "Solid ink tile."},
        files={"file": ("perm.png", png, "image/png")},
    )
    assert up.status_code == 200
    audit_id = up.json()["id"]

    first = client.post(f"/api/audits/{audit_id}/heatmap", json={"grid_size": 2})
    assert first.status_code == 200

    # Without run_audits -> 403.
    real_has = main_mod.has_permission
    monkeypatch.setattr(main_mod, "has_permission", lambda role, perm: False if perm == "run_audits" else real_has(role, perm))
    denied = client.post(f"/api/audits/{audit_id}/heatmap", json={"grid_size": 2})
    assert denied.status_code == 403
    monkeypatch.setattr(main_mod, "has_permission", real_has)

    # Audit rate limiter applies (30 requests / 60 s per client IP).
    statuses = []
    for _ in range(35):
        statuses.append(client.post(f"/api/audits/{audit_id}/heatmap", json={"grid_size": 2}).status_code)
        if statuses[-1] == 429:
            break
    assert statuses[-1] == 429
    assert set(statuses[:-1]) == {200}


def test_f7_svg_parent_transform_logo_distance_inherited_g_fill_currentcolor_empty_palette_and_small_magenta_square():
    vault = get_brand_vault_bundle("novapay")

    # (a) Logo inside a translated group: true box is x=42, y=33 -> min edge distance 33 px.
    translated = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200" width="300" height="200">
      <rect x="0" y="0" width="300" height="200" fill="#FFFFFF" />
      <g transform="translate(40, 30)">
        <rect data-loomshield-logo="true" x="2" y="3" width="80" height="40" fill="#0F172A" />
      </g>
    </svg>"""
    cs = inspect_visual_heatmap(raw_bytes=translated, brand_colors=vault["colors"], brand=vault["brand"], filename="t.svg")["clear_space"]
    assert cs["checked"] is True
    assert cs["min_distance_px"] == 33.0
    assert cs["passed"] is True

    # (b) Text colour inherited from parent <g fill>, and currentColor reported as Not measured (never black).
    inherited = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">
      <rect x="0" y="0" width="400" height="200" fill="#FFFFFF" />
      <g fill="#CBD5E1"><text x="40" y="80" font-size="16">Inherited light grey</text></g>
      <text x="40" y="140" fill="currentColor" font-size="16">Current colour text</text>
    </svg>"""
    tc = inspect_visual_heatmap(raw_bytes=inherited, brand_colors=vault["colors"], brand=vault["brand"], filename="i.svg")["text_contrast"]
    inh = next(e for e in tc["elements"] if "Inherited" in e["text"])
    assert inh["fg_hex"].upper() == "#CBD5E1"
    assert inh["contrast_ratio"] < 4.5
    assert inh["passed"] is False
    cur = next(e for e in tc["elements"] if "Current colour" in e["text"])
    assert cur["status"] == "Not measured"
    assert cur["fg_hex"] != "#000000"
    assert cur["contrast_ratio"] is None
    assert cur["passed"] is None

    # (c) Empty palette -> Not Checked, nothing flagged.
    png = _solid_png_bytes(200, 200, mode="RGBA", color=(255, 0, 255, 255))
    empty = inspect_visual_heatmap(raw_bytes=png, brand_colors=[], brand=vault["brand"], filename="e.png", grid_size=2)
    assert empty["palette_state"] == "Not Checked"
    assert empty["flagged_cells_count"] == 0

    # (d) A small magenta square covering 4% of R1C1 is flagged; a 1% square in R2C2 is below the 2% limit.
    img = Image.new("RGBA", (200, 200), (23, 25, 28, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 29, 29], fill=(255, 0, 255, 255))      # 20x20 = 400 px of 10,000 = 4%
    draw.rectangle([150, 150, 159, 159], fill=(255, 0, 255, 255))  # 10x10 = 100 px of 10,000 = 1%
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    res = inspect_visual_heatmap(raw_bytes=buf.getvalue(), brand_colors=vault["colors"], brand=vault["brand"], filename="m.png", grid_size=2)
    assert res["off_palette_min_cell_coverage_pct"] == 2.0
    by_id = {c["cell_id"]: c for c in res["cells"]}
    assert by_id["R1C1"]["flagged"] is True
    assert by_id["R1C1"]["cell_dominant_hex"].upper() == "#17191C"
    assert by_id["R1C1"]["flagged_hex"].upper() == "#FF00FF"
    assert by_id["R1C1"]["flagged_coverage_pct"] == 4.0
    assert by_id["R2C2"]["flagged"] is False
    assert res["flagged_cells_count"] == 1


def _sanitize(svg_text):
    cleaned, changed, actions = sanitize_svg_markup(svg_text)
    return cleaned, changed, actions


def test_f8_svg_sanitizer_removes_foreign_object():
    cleaned, changed, actions = _sanitize(
        '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject width="10" height="10">'
        '<div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject><rect width="5" height="5"/></svg>'
    )
    assert changed is True
    assert "foreignobject" not in cleaned.lower()
    assert "<rect" in cleaned


def test_f8_svg_sanitizer_removes_disallowed_href_and_xlink_href():
    cleaned, changed, _ = _sanitize(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<a href="https://evil.example/x"><rect width="5" height="5"/></a>'
        '<image xlink:href="http://evil.example/p.png" width="5" height="5"/>'
        '<image href="data:image/png;base64,AAAA" width="5" height="5"/>'
        '<a href="#local"><rect width="1" height="1"/></a></svg>'
    )
    low = cleaned.lower()
    assert changed is True
    assert "evil.example" not in low
    assert "data:image/png;base64,aaaa" in low
    assert 'href="#local"' in low


def test_f8_svg_sanitizer_removes_external_url_in_styles():
    cleaned, changed, _ = _sanitize(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<style>rect { fill: url(https://evil.example/a.svg#g); }</style>'
        '<rect width="5" height="5" style="fill: url(http://evil.example/b.svg#g)"/>'
        '<rect width="5" height="5" style="filter: url(//evil.example/c.svg#f)"/>'
        '<rect width="5" height="5" style="fill: url(#localGrad)"/></svg>'
    )
    low = cleaned.lower()
    assert changed is True
    assert "evil.example" not in low
    assert "url(#localgrad)" in low


def test_f8_svg_sanitizer_removes_css_import_rule():
    cleaned, changed, _ = _sanitize(
        '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url("https://evil.example/x.css"); '
        'rect { fill: #0F172A; }</style><rect width="5" height="5"/></svg>'
    )
    low = cleaned.lower()
    assert changed is True
    assert "@import" not in low
    assert "evil.example" not in low
    assert "#0f172a" in low


def test_f8_svg_sanitizer_removes_use_with_external_target():
    cleaned, changed, _ = _sanitize(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<defs><rect id="r" width="5" height="5"/></defs>'
        '<use xlink:href="https://evil.example/sprite.svg#icon"/>'
        '<use href="sprite.svg#icon"/>'
        '<use href="#r"/></svg>'
    )
    low = cleaned.lower()
    assert changed is True
    assert "evil.example" not in low
    assert "sprite.svg" not in low
    assert low.count("<use") == 1
    assert 'href="#r"' in low
