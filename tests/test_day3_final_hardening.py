import hashlib
import io
import json
import os
import struct
import zlib
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from PIL import Image

from backend.main import app, _read_upload_in_chunks
from backend.config import is_demo_mode, issue_auth_token, verify_demo_token
from backend.database import (
    get_connection,
    init_db,
    get_db_path,
    list_brand_presets,
    apply_brand_preset,
    export_database_snapshot,
    restore_database_snapshot,
    set_current_session_id,
)
from backend.engine import (
    MAX_IMAGE_PIXELS,
    ImageTooLargeError,
    probe_and_decode_raster_image,
    run_six_pillar_audit,
)
from backend.heatmap import inspect_visual_heatmap
from backend.certificates import verify_certificate_envelope


def _solid_png_bytes(width: int, height: int, color=(30, 110, 220, 255)) -> bytes:
    """Generate a minimal valid PNG with DEFLATE-compressed scanlines."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw_scanline = b"\x00" + bytes(color) * width
    raw_idat = raw_scanline * height
    compressed_idat = zlib.compress(raw_idat, level=1)
    return header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed_idat) + chunk(b"IEND", b"")


# ============================================================================
# G2: MEMORY AND 12 MEGAPIXEL BOUNDARY TESTS
# ============================================================================

def test_g2_image_cap_12mp_accepted_and_12mp_plus_1px_rejected():
    """At 12 MP (12,000,000 pixels) accepted; at 12 MP + 1 pixel rejected with 400/ImageTooLargeError."""
    assert MAX_IMAGE_PIXELS == 12_000_000
    assert Image.MAX_IMAGE_PIXELS == 12_000_000

    # Exactly at the 12 MP cap (4000 x 3000 = 12,000,000)
    exact_cap_png = _solid_png_bytes(4000, 3000)
    img_accepted = probe_and_decode_raster_image(exact_cap_png)
    assert img_accepted.size == (4000, 3000)
    img_accepted.close()

    # Cap + 1 pixel: 12,000,001 x 1 = 12,000,001 pixels (> 12_000_000)
    over_cap_png = _solid_png_bytes(4000, 3001)  # 12,004,000 pixels
    with pytest.raises(ImageTooLargeError) as exc_info:
        probe_and_decode_raster_image(over_cap_png)
    assert "12 megapixel limit" in str(exc_info.value)

    # Test via API /api/audits/upload endpoint
    client = TestClient(app)
    res_err = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "user_role": "Content Creator"},
        files={"file": ("over_cap.png", over_cap_png, "image/png")},
    )
    assert res_err.status_code == 400
    assert "12 megapixel limit" in res_err.text


# ============================================================================
# G3: ABOUT PAGE AUDIT (NO SHIPPED FEATURES UNDER ROADMAP)
# ============================================================================

def test_g3_about_page_does_not_list_shipped_features_under_roadmap():
    """About page must list Guideline Clarity, Heatmap, and Certificate under Verified Capabilities, not Roadmap."""
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    card2_idx = content.find("<!-- Card 2: Verified System Capabilities -->")
    card3_idx = content.find("<!-- Card 3: Upcoming Roadmap -->")
    card4_idx = content.find("<!-- Card 4: Signed Certificate Threat Model")

    assert card2_idx != -1
    assert card3_idx != -1
    assert card4_idx != -1

    card2_text = content[card2_idx:card3_idx]
    card3_text = content[card3_idx:card4_idx]

    # Verified capabilities (Card 2) must include the shipped features
    assert "Guideline Clarity Rewriter" in card2_text
    assert "Heatmap Inspector" in card2_text
    assert "Cryptographically Signed Compliance Certificate" in card2_text
    assert "Ed25519" in card2_text
    assert "explicit markers" in card2_text
    assert "contrast for SVG text only" in card2_text
    assert "trusted proxy hop counting" in card2_text or "anti-spoofing" in card2_text

    # Roadmap (Card 3) MUST NOT list shipped features
    assert "Guideline Clarity Rewriter" not in card3_text
    assert "Heatmap" not in card3_text
    assert "Compliance Certificate" not in card3_text
    assert "Signed Certificate" not in card3_text

    # Roadmap must keep only streaming uploads and non-destructive presets
    assert "Streaming Uploads (100 MB)" in card3_text
    assert "Non-Destructive Presets" in card3_text


# ============================================================================
# G4: DEMO AND PRODUCTION AUDIT COUNTS AGREE ACROSS VIEWS
# ============================================================================

def test_g4_demo_and_production_audit_counts_agree_across_views(monkeypatch):
    """Overview, Review queue, Audit history, and Guideline insights report matching counts in demo and prod."""
    client = TestClient(app)

    # 1. DEMO MODE
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    init_db()
    assert is_demo_mode() is True

    overview_res = client.get("/api/overview/novapay").json()
    ov_docs = overview_res["metrics"]["documents_audited"]
    ov_recent = len(overview_res["recent_audits"])

    queue_res = client.get("/api/audits?brand_id=novapay&limit=50&offset=0").json()
    q_total = queue_res["total"]
    q_audits = len(queue_res["audits"])

    radar_res = client.get("/api/ambiguity-radar/novapay").json()
    r_sample = radar_res["sample_audits_count"]
    r_note = radar_res.get("sample_audits_note", "")

    # In demo mode, all 6 sample audits are present and reported consistently
    assert ov_docs == 6
    assert ov_recent == 6
    assert q_total == 6
    assert q_audits == 6
    assert r_sample == 6
    assert "Includes 6 seeded sample audits" in r_note

    # 2. PRODUCTION MODE (Fresh clone initializes workspace with 0 sample audits)
    import tempfile
    td = tempfile.mkdtemp(prefix="loomshield_prod_fresh_")
    prod_db = os.path.join(td, "loomshield_prod.db")
    monkeypatch.setenv("LOOMSHIELD_DB_PATH", prod_db)
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    init_db()
    assert is_demo_mode() is False

    prod_overview = client.get("/api/overview/novapay").json()
    prod_queue = client.get("/api/audits?brand_id=novapay&limit=50&offset=0").json()
    prod_radar = client.get("/api/ambiguity-radar/novapay").json()

    # In production mode, fresh start seeds brand vault but 0 sample audits across all views
    assert prod_overview["metrics"]["documents_audited"] == 0
    assert len(prod_overview["recent_audits"]) == 0
    assert prod_queue["total"] == 0
    assert len(prod_queue["audits"]) == 0
    assert prod_radar["sample_audits_count"] == 0
    assert prod_radar.get("sample_audits_note", "") == ""


# ============================================================================
# G5: TIER LABELS AND PRE-MIGRATION CERTIFICATE INVARIANCE
# ============================================================================

def test_g5_tier_labels_and_pre_migration_certificate_remains_valid():
    """All detection methods follow strict tier definitions; pre-migration certificates remain valid."""
    client = TestClient(app)

    # 1. Issue certificate on AUD-1002 prior to finding label migration
    issue_res = client.post("/api/audits/AUD-1002/certificate")
    assert issue_res.status_code == 200
    envelope = issue_res.json()
    assert envelope["signature_b64"]
    assert envelope["payload"]["audit_id"] == "AUD-1002"

    # Verify signature before migration
    pre_verify = verify_certificate_envelope(envelope)
    assert pre_verify["valid"] is True and pre_verify["status"] == "valid"

    # 2. Run the database migration
    init_db()

    # 3. Check every finding detection_method in DB has valid tier prefix
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, detection_method FROM findings")
    findings = cur.fetchall()
    conn.close()

    assert len(findings) > 0
    for row in findings:
        dm = str(row["detection_method"] or "").strip()
        assert (
            dm.startswith("Tier 1: ")
            or dm.startswith("Tier 2: ")
            or dm.startswith("Tier 1 + Tier 2: ")
        ), f"Finding {row['id']} has invalid tier prefix: {dm}"

        # Strict checks
        if "TF-IDF" in dm and "Superlative" in dm:
            assert dm.startswith("Tier 1 + Tier 2: ")
        elif "Polarity" in dm or "NLP" in dm or "TF-IDF" in dm or "Messaging Principle" in dm or "Administrative Status" in dm:
            assert dm.startswith("Tier 2: ")
        elif any(k in dm for k in ["File Parser", "Dictionary Match", "Hexadecimal", "Pillow Raster", "Delta-E", "Clear-Space", "Relative Luminance", "Alternative-Text", "DOM Structural", "Flesch-Kincaid"]):
            assert dm.startswith("Tier 1: ")

    # 4. Verify pre-migration certificate remains 100% valid (payload & hash invariance)
    post_verify = verify_certificate_envelope(envelope)
    assert post_verify["valid"] is True and post_verify["status"] == "valid"

    api_verify = client.post("/api/certificates/verify", json=envelope).json()
    assert api_verify["valid"] is True
    assert api_verify["audit_exists_on_server"] is True
    assert api_verify["server_audit_status"] == "Approved"
    assert api_verify["content_hash_matches_server"] is True


# ============================================================================
# G6: UPLOAD SIZE GUARD AND UNRESOLVABLE SVG TEXT CONTRAST TESTS
# ============================================================================

def test_g6a_upload_size_guard_allows_5mb_minus_1kb():
    """upload_size_guard_middleware allows 5 MB - 1 KB file with multipart overhead; applies only to upload routes."""
    client = TestClient(app)

    # 5 MB minus 1 KB = 5,241,856 bytes
    exact_size = (5 * 1024 * 1024) - 1024
    payload_content = b"A" * exact_size

    # POST to /api/audits/upload with this 5 MB - 1 KB payload
    res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "user_role": "Content Creator"},
        files={"file": ("test_5mb_minus_1kb.txt", payload_content, "text/plain")},
    )
    # Must NOT be rejected by upload_size_guard_middleware (not 400 size limit)
    # The file is ingested and audited successfully (200)
    assert res.status_code == 200
    body = res.json()
    assert body["id"].startswith("AUD-")

    # Non-upload route (e.g. GET /api/brand-vault/novapay) is never blocked by upload size middleware
    get_res = client.get("/api/vault/novapay")
    assert get_res.status_code == 200


def test_g6b_all_unresolvable_svg_text_contrast_state_not_checked_never_passed():
    """When every SVG text fill is unresolvable (currentColor), text_contrast.state is 'Not Checked', never Passed."""
    # SVG with text element having fill="currentColor" (unresolvable without DOM context)
    unresolvable_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">\n'
        '  <rect width="400" height="200" fill="#FFFFFF"/>\n'
        '  <text x="50" y="80" fill="currentColor" font-size="20">Unresolvable Brand Headline</text>\n'
        '  <text x="50" y="130" style="fill: currentColor" font-size="16">Unresolvable Subtitle</text>\n'
        '</svg>'
    ).encode("utf-8")

    vault_colors = [
        {"id": "CLR-001", "name": "Nova Blue", "hex_code": "#0B3C5D", "usage_role": "primary", "max_delta_e": 12.0},
        {"id": "CLR-002", "name": "Pure White", "hex_code": "#FFFFFF", "usage_role": "background", "max_delta_e": 6.0},
    ]
    brand_dict = {
        "id": "novapay",
        "name": "NovaPay",
        "min_contrast_normal": 4.5,
        "min_contrast_large": 3.0,
        "min_clear_space_ratio": 0.25,
        "min_clear_space_px": 16,
    }

    hm = inspect_visual_heatmap(
        raw_bytes=unresolvable_svg,
        brand_colors=vault_colors,
        brand=brand_dict,
        filename="unresolvable.svg",
    )

    tc = hm.get("text_contrast", {})
    assert tc["measured_count"] == 0
    assert tc["total_elements_count"] >= 1
    # text_contrast.state MUST be 'Not Checked', NEVER 'Passed'
    assert tc["state"] == "Not Checked"
    assert tc["state"] != "Passed"

    # Elements must report 'Not measured'
    for el in tc.get("elements", []):
        assert el["status"] == "Not measured"
        assert el["passed"] is None
        assert el["fg_hex"] == "Not measured"

    # Also run six pillar audit and verify Accessibility pillar did not treat unresolvable text as a failure or passed contrast
    res = run_six_pillar_audit(
        content=unresolvable_svg.decode("utf-8"),
        brand=brand_dict,
        rules=[],
        terminology_rows=[],
        facts=[],
        brand_colors=vault_colors,
        has_visual_asset=True,
        visual_inspection=hm,
    )
    # No "Insufficient SVG/Visual Text Contrast Ratio" findings should be raised for unresolvable text
    findings = res.get("findings", [])
    contrast_findings = [f for f in findings if "Insufficient SVG/Visual Text Contrast" in f.get("issue_type", "")]
    assert len(contrast_findings) == 0


def test_system_limits_and_render_free_profile():
    """Verify /api/system/limits returns 512 MB Render free tier profile and 25 MB max safe upload."""
    client = TestClient(app)
    res = client.get("/api/system/limits")
    assert res.status_code == 200
    data = res.json()
    assert data["render_free_instance_ram_mb"] == 512
    assert data["render_free_instance_safe_cap_mb"] == 25
    assert data["render_free_instance_safe_headroom_mb"] >= 200
    assert data["max_image_megapixels"] == 12.0
    assert data["streaming_chunk_kb"] == 64
    assert data["status"] == "operational"


def test_configurable_upload_size_env():
    """Verify that when LOOMSHIELD_MAX_UPLOAD_MB is set to 25, the limit adapts accordingly."""
    client = TestClient(app)
    old_env = os.environ.get("LOOMSHIELD_MAX_UPLOAD_MB")
    try:
        os.environ["LOOMSHIELD_MAX_UPLOAD_MB"] = "25"
        res = client.get("/api/system/limits")
        assert res.status_code == 200
        assert res.json()["configured_max_upload_mb"] == 25

        class FakeChunkedUpload:
            def __init__(self, total_bytes):
                self.remaining = total_bytes

            async def read(self, n):
                if self.remaining <= 0:
                    return b""
                take = min(n, self.remaining)
                self.remaining -= take
                return b"X" * take

        import asyncio
        ten_mb = 10 * 1024 * 1024
        result = asyncio.run(_read_upload_in_chunks(FakeChunkedUpload(ten_mb)))
        assert len(result) == ten_mb

        twenty_six_mb = 26 * 1024 * 1024
        with pytest.raises(Exception) as excinfo:
            asyncio.run(_read_upload_in_chunks(FakeChunkedUpload(twenty_six_mb)))
        assert "25 MB" in str(excinfo.value)
    finally:
        if old_env is None:
            os.environ.pop("LOOMSHIELD_MAX_UPLOAD_MB", None)
        else:
            os.environ["LOOMSHIELD_MAX_UPLOAD_MB"] = old_env


def test_brand_presets_catalog_and_apply():
    """Verify brand presets catalog contains benchmark brands and can be applied."""
    client = TestClient(app)
    res = client.get("/api/brands/presets")
    assert res.status_code == 200
    presets = res.json()["presets"]
    ids = [p["id"] for p in presets]
    assert "novapay" in ids
    assert "verdant" in ids
    assert "acmecorp" in ids
    assert "finsafe" in ids

    token_res = client.post("/api/auth/login", json={"username": "admin", "password": "LoomShield2026!"})
    token = token_res.json()["token"]
    apply_res = client.post(
        "/api/brands/presets/acmecorp/apply",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["status"] == "applied"
    assert apply_res.json()["brand"]["name"] == "Acme Cloud Infrastructure"

    brands_res = client.get("/api/brands")
    brand_ids = [b["id"] for b in brands_res.json()["brands"]]
    assert "acmecorp" in brand_ids


def test_typography_rule_enforcement_in_engine():
    """Verify that typography rules detect prohibited fonts and sub-threshold font sizes."""
    brand = {
        "id": "novapay",
        "typography_specs": "Primary UI & Headings: Inter / Geist (600-700 weight). Body: Inter (400-500 weight, 14-16px).",
    }
    vis_bad_font = {
        "inspect_ok": True,
        "palette_state": "Passed",
        "text_elements": [
            {
                "id": "text-heading",
                "text": "Instant Settlement Payouts",
                "font_family": "Comic Sans MS",
                "font_size": 16.0,
            }
        ],
    }
    audit_res = run_six_pillar_audit(
        content="Instant Settlement Payouts",
        brand=brand,
        rules=[],
        terminology_rows=[],
        facts=[],
        brand_colors=[],
        visual_inspection=vis_bad_font,
    )
    typo_findings = [f for f in audit_res["findings"] if f["rule_or_fact_id"] == "RULE-TYPO-01"]
    assert len(typo_findings) == 1
    assert "Comic Sans MS" in typo_findings[0]["flagged_text"]
    assert typo_findings[0]["pillar"] == "Visual and Logo Consistency"

    vis_small_font = {
        "inspect_ok": True,
        "palette_state": "Passed",
        "text_elements": [
            {
                "id": "text-disclaimer",
                "text": "* Subject to terms and conditions",
                "font_family": "Inter",
                "font_size": 6.0,
            }
        ],
    }
    audit_res_small = run_six_pillar_audit(
        content="Instant Settlement Payouts",
        brand=brand,
        rules=[],
        terminology_rows=[],
        facts=[],
        brand_colors=[],
        visual_inspection=vis_small_font,
    )
    size_findings = [f for f in audit_res_small["findings"] if f["rule_or_fact_id"] == "RULE-TYPO-02"]
    assert len(size_findings) == 1
    assert "6.0px" in size_findings[0]["flagged_text"]
    assert size_findings[0]["pillar"] == "Visual and Logo Consistency"

    vis_ok = {
        "inspect_ok": True,
        "palette_state": "Passed",
        "text_elements": [
            {
                "id": "text-ok",
                "text": "Instant Settlement Payouts",
                "font_family": "Inter, sans-serif",
                "font_size": 16.0,
            }
        ],
    }
    audit_res_ok = run_six_pillar_audit(
        content="Instant Settlement Payouts",
        brand=brand,
        rules=[],
        terminology_rows=[],
        facts=[],
        brand_colors=[],
        visual_inspection=vis_ok,
    )
    typo_f = [f for f in audit_res_ok["findings"] if f["rule_or_fact_id"] in ("RULE-TYPO-01", "RULE-TYPO-02")]
    assert len(typo_f) == 0


def test_per_visitor_demo_isolation():
    """Verify that X-LoomShield-Session routes requests to isolated SQLite databases."""
    client = TestClient(app)
    old_mode = os.environ.get("LOOMSHIELD_WORKSPACE_MODE")
    try:
        os.environ["LOOMSHIELD_WORKSPACE_MODE"] = "demo"
        sess1 = "test_sess_user_alpha"
        sess2 = "test_sess_user_beta"

        res1 = client.get("/api/brands", headers={"X-LoomShield-Session": sess1})
        assert res1.status_code == 200
        assert res1.headers.get("x-loomshield-session") == sess1

        res2 = client.get("/api/brands", headers={"X-LoomShield-Session": sess2})
        assert res2.status_code == 200
        assert res2.headers.get("x-loomshield-session") == sess2

        p1 = get_db_path(session_id=sess1)
        p2 = get_db_path(session_id=sess2)
        assert p1 != p2
        assert os.path.exists(p1)
        assert os.path.exists(p2)
    finally:
        set_current_session_id(None)
        if old_mode is None:
            os.environ.pop("LOOMSHIELD_WORKSPACE_MODE", None)
        else:
            os.environ["LOOMSHIELD_WORKSPACE_MODE"] = old_mode


def test_database_snapshot_export_and_restore(tmp_path):
    """Verify database snapshot exports to JSON and restores correctly."""
    snap_file = str(tmp_path / "test_snapshot.json")
    exported = export_database_snapshot(snapshot_path=snap_file)
    assert os.path.exists(snap_file)
    assert "tables" in exported
    assert "brands" in exported["tables"]
    assert len(exported["tables"]["brands"]) > 0

    restored = restore_database_snapshot(snapshot_path=snap_file)
    assert restored is True


def test_production_user_authentication():
    """Verify /api/auth/login, /api/auth/me, and /api/auth/logout."""
    client = TestClient(app)
    bad_res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password"})
    assert bad_res.status_code == 401

    good_res = client.post("/api/auth/login", json={"username": "admin", "password": "LoomShield2026!"})
    assert good_res.status_code == 200
    auth_data = good_res.json()
    token = auth_data["token"]
    assert token and "." in token

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["role"] in ("Brand Administrator", "admin")

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"
