with open("tests/test_heatmap_inspector.py", "r", encoding="utf-8") as f:
    text = f.read()

new_tests = '''

def test_h2_vault_approved_logo_upload_delete_and_clear_space_api():
    """H2(a & c): Brand Administrator uploads approved logo (max 300 KB) and updates clear space."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
        init_db()
        reset_demo_workspace()
        client = TestClient(app)

        # 1. Non-admin (Content Creator) -> 403 Forbidden
        small_png = b"\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01\\x08\\x06\\x00\\x00\\x00\\x1f\\x15c4\\x00\\x00\\x00\\nIDATx\\x9cc`\\x00\\x00\\x00\\x02\\x00\\x01H\\xaf\\xa4q\\x00\\x00\\x00\\x00IEND\\xaeB`\\x82"
        res_403 = client.post(
            "/api/vault/novapay/logo",
            files={"file": ("logo.png", small_png, "image/png")},
            headers={"X-Test-Role": "Content Creator"},
        )
        assert res_403.status_code == 403

        # 2. Oversized file (> 300 KB) -> 400
        big_bytes = b"\\x89PNG\\r\\n\\x1a\\n" + b"X" * (310 * 1024)
        res_big = client.post(
            "/api/vault/novapay/logo",
            files={"file": ("big_logo.png", big_bytes, "image/png")},
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert res_big.status_code == 400
        assert "exceeds" in res_big.text or "limit" in res_big.text

        # 3. Invalid format (.txt) -> 400
        res_bad_fmt = client.post(
            "/api/vault/novapay/logo",
            files={"file": ("notes.txt", b"just text", "text/plain")},
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert res_bad_fmt.status_code == 400
        assert "Only PNG and SVG" in res_bad_fmt.text

        # 4. Valid logo upload as Brand Administrator -> 200, vault updated
        tpl_path = Path(__file__).resolve().parent / "fixtures" / "banners" / "approved_logo_template.png"
        assert tpl_path.exists(), "approved_logo_template.png must exist"
        tpl_bytes = tpl_path.read_bytes()

        res_ok = client.post(
            "/api/vault/novapay/logo",
            files={"file": ("novapay_logo.png", tpl_bytes, "image/png")},
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert res_ok.status_code == 200
        v_data = res_ok.json()["vault"]["brand"]
        assert v_data["approved_logo_b64"].startswith("data:image/png;base64,")
        assert v_data["approved_logo_filename"] == "novapay_logo.png"

        # 5. Clear space ratio and fallback px editable via API
        res_cs = client.put(
            "/api/vault/novapay/clear-space",
            json={"min_clear_space_ratio": 0.5, "min_clear_space_px": 24},
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert res_cs.status_code == 200
        v_cs = res_cs.json()["vault"]["brand"]
        assert v_cs["min_clear_space_ratio"] == 0.5
        assert v_cs["min_clear_space_px"] == 24

        # 6. Delete logo -> clears stored logo
        res_del = client.delete(
            "/api/vault/novapay/logo",
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert res_del.status_code == 200
        v_after_del = res_del.json()["vault"]["brand"]
        assert v_after_del["approved_logo_b64"] == ""


def test_h2_heatmap_fixture_suite_against_expected_json():
    """H2(d): Run every fixture in tests/fixtures/banners/ against expected.json."""
    from backend.heatmap import inspect_visual_heatmap
    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "banners"
    expected_path = fixtures_dir / "expected.json"
    assert expected_path.exists(), "expected.json must exist"

    with open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    assert len(expected) >= 12, f"Expected at least 12 banner fixtures, found {len(expected)}"

    tpl_path = fixtures_dir / "approved_logo_template.png"
    assert tpl_path.exists()
    tpl_b64 = f"data:image/png;base64,{base64.b64encode(tpl_path.read_bytes()).decode('ascii')}"

    brand = {
        "id": "novapay",
        "name": "NovaPay Enterprise",
        "min_clear_space_ratio": 0.25,
        "min_clear_space_px": 16.0,
        "approved_logo_b64": tpl_b64,
        "approved_logo_format": "image/png",
    }

    colors = [
        {"id": "CLR-01", "name": "Dark Slate", "hex_code": "#17191C", "usage_role": "Primary text and logo", "max_delta_e": 14.0},
        {"id": "CLR-02", "name": "Navy Blue", "hex_code": "#0B2545", "usage_role": "Headlines and cards", "max_delta_e": 14.0},
        {"id": "CLR-03", "name": "Medium Blue", "hex_code": "#134074", "usage_role": "Accents and links", "max_delta_e": 14.0},
        {"id": "CLR-04", "name": "Off White", "hex_code": "#EEF4F8", "usage_role": "Surface and cards", "max_delta_e": 14.0},
        {"id": "CLR-05", "name": "Pure White", "hex_code": "#FFFFFF", "usage_role": "Canvas background", "max_delta_e": 14.0},
    ]

    for fname, exp in expected.items():
        fpath = fixtures_dir / fname
        assert fpath.exists(), f"Fixture file {fname} not found"
        raw_bytes = fpath.read_bytes()

        hm = inspect_visual_heatmap(raw_bytes, colors, brand=brand, filename=fname, grid_size=2)
        assert isinstance(hm, dict)
        assert "cells" in hm
        assert "text_contrast" in hm
        assert "clear_space" in hm

        # Template match positive check
        if exp.get("template_match") is True:
            cs = hm["clear_space"]
            assert cs["located_method"].startswith("Template match")
            assert cs["logo_box"]["source"] == "template_match"
            assert cs["logo_box"]["score"] >= 0.80

        # Template match negative check
        if exp.get("template_match") is False:
            cs = hm["clear_space"]
            assert cs["state"] == "Not Checked"
            assert "Not Checked: approved logo not found" in cs["reason"]

        # Transformed logo group check
        if "transformed" in fname:
            cs = hm["clear_space"]
            assert cs["logo_box"] is not None
            assert cs["logo_box"]["source"] == "svg_marker"

        # Low contrast text check
        if "low_contrast" in fname:
            assert hm["text_contrast"]["state"] == "Findings"
            assert hm["text_contrast"]["measured_count"] >= 1
'''

assert "def test_h2_vault_approved_logo_upload_delete_and_clear_space_api" not in text
text = text + new_tests

with open("tests/test_heatmap_inspector.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Added test_h2 to tests/test_heatmap_inspector.py successfully")
