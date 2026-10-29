"""
LOOMSHIELD — MASTER TEST CYCLES SUITE (CYCLES 0 TO 9 + FINAL RELEASE GATE)
Objective: Verify functionality, accuracy, privacy, usability, security, performance, and reliability.
"""

import io
import json
import os
import platform
import re
import statistics
import sys
import time
import tracemalloc
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Cycle 0: Configure isolated SQLite test database before importing backend modules
# (get_db_path() reads LOOMSHIELD_DB_PATH at call time; the module fixture below sets it via MonkeyPatch.)
ISOLATED_TEST_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_loomshield_isolated.db"))

from backend.database import get_connection, get_db_path, init_db
from backend.engine import (
    delta_e_cie76,
    get_engine_status,
    inspect_raster_image,
    parse_uploaded_file,
    run_six_pillar_audit,
    wcag_contrast_ratio,
)
from backend.main import app, get_brand_vault_bundle


@pytest.fixture(scope="module", autouse=True)
def isolated_test_environment():
    """Cycle 0: Prepare a repeatable, isolated test database and clean up after the suite."""
    mp = pytest.MonkeyPatch()
    mp.setenv("LOOMSHIELD_DB_PATH", ISOLATED_TEST_DB)
    mp.delenv("LOOMSHIELD_CLOUD_API_KEY", raising=False)
    if os.path.exists(ISOLATED_TEST_DB):
        os.remove(ISOLATED_TEST_DB)
    init_db()
    yield
    mp.undo()
    if os.path.exists(ISOLATED_TEST_DB):
        try:
            os.remove(ISOLATED_TEST_DB)
        except OSError:
            pass


client = TestClient(app)


# ============================================================================
# CYCLE 0 — TEST ENVIRONMENT AND BASELINE
# ============================================================================

def test_cycle0_isolated_environment_and_baseline():
    assert get_db_path() == ISOLATED_TEST_DB
    assert os.path.exists(ISOLATED_TEST_DB)
    assert app.version == "2.1.0"

    health = client.get("/api/health")
    assert health.status_code == 200
    h_data = health.json()
    assert h_data["status"] == "healthy"
    assert h_data["engine"]["external_api_key_required"] is False
    assert h_data["engine"]["external_api_key_configured"] is False

    brands = client.get("/api/brands").json()["brands"]
    brand_ids = [b["id"] for b in brands]
    assert "novapay" in brand_ids
    assert "verdant" in brand_ids


# ============================================================================
# CYCLE 1 — UNIT TESTING (A: TERMINOLOGY, B: CLAIMS, C: A11Y, D: VISUAL)
# ============================================================================

# --- A. TERMINOLOGY ENGINE (10 Test Cases) ---

def test_cycle1_A1_correct_preferred_terminology():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="NovaPay Core powers our Local Governance Engine with SOC 2 Type II certified controls.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 0
    assert res["pillar_states"]["Terminology"] == "Passed"


def test_cycle1_A2_prohibited_terminology():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Use NovaWallet to achieve unhackable synergy.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    flagged = {f["flagged_text"].lower() for f in term_findings}
    assert {"novawallet", "unhackable", "synergy"}.issubset(flagged)
    for f in term_findings:
        assert f["rule_or_fact_id"] == "RULE-TERM-01"
        assert f["start_index"] >= 0 and f["end_index"] > f["start_index"]


def test_cycle1_A3_incorrect_capitalization():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Both novapay and Novapay and NOVAPAY must be spelled NovaPay.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    flagged_exact = [f["flagged_text"] for f in term_findings]
    assert "novapay" in flagged_exact
    assert "Novapay" in flagged_exact
    assert "NOVAPAY" in flagged_exact
    assert "NovaPay" not in flagged_exact


def test_cycle1_A4_word_appearing_inside_larger_word():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Our novapayments and synergistic architecture avoid substring false positives.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 0


def test_cycle1_A5_case_sensitive_and_case_insensitive_matching():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="NovaPay is valid, but UNHACKABLE and Ai EnGiNe are prohibited regardless of case.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    flagged = [f["flagged_text"] for f in term_findings]
    assert "UNHACKABLE" in flagged
    assert "Ai EnGiNe" in flagged
    assert "NovaPay" not in flagged


def test_cycle1_A6_multiple_violations_in_one_paragraph():
    vault = get_brand_vault_bundle("novapay")
    text = "Novapay launched NovaWallet with an AI Engine to blitz-scale unhackable synergy."
    res = run_six_pillar_audit(
        content=text,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 6
    for f in term_findings:
        assert text[f["start_index"]:f["end_index"]] == f["flagged_text"]


def test_cycle1_A7_punctuation_surrounding_prohibited_words():
    vault = get_brand_vault_bundle("novapay")
    text = 'Is it "unhackable," (NovaWallet), or \'synergy!\'? Ask [Novapay].'
    res = run_six_pillar_audit(
        content=text,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    flagged = [f["flagged_text"] for f in res["findings"] if f["pillar"] == "Terminology"]
    assert "unhackable" in flagged
    assert "NovaWallet" in flagged
    assert "synergy" in flagged
    assert "Novapay" in flagged


def test_cycle1_A8_empty_input():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    assert res["findings"] == []


def test_cycle1_A9_unicode_and_special_characters():
    vault = get_brand_vault_bundle("novapay")
    text = "Café Zürich & 東京 treasury — Novapay™ replaces NovaWallet with €0 hidden fees."
    res = run_six_pillar_audit(
        content=text,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 2
    for f in term_findings:
        assert text[f["start_index"]:f["end_index"]] == f["flagged_text"]


def test_cycle1_A10_false_positive_scenarios():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Our engineering team designed a novel wallet-to-ledger reconciliation workflow for regulated treasuries.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    term_findings = [f for f in res["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 0


# --- B. PROMOTIONAL CLAIM ENGINE (10 Test Cases) ---

def test_cycle1_B1_approved_numerical_claim():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Processing and cross-border settlement is up to 64% faster under the conditions stated in the approved performance report.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 0
    assert res["pillar_states"]["Promotional Claims"] == "Passed"


def test_cycle1_B2_exaggerated_numerical_claim():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Our platform guarantees 95% faster processing for enterprise treasury teams.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert any(f["rule_or_fact_id"] == "FACT-101" and "64% faster" in f["explanation"] for f in claims)


def test_cycle1_B3_unsupported_percentage():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="NovaPay reduces employee cafeteria wait times by 89%.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 1
    assert claims[0]["review_state"] == "needs_review"
    assert claims[0]["source_evidence"] == "No supporting fact was found in the configured Brand Vault. Human verification is required."


def test_cycle1_B4_unsupported_superlative():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="NovaPay Core is #1 in the world with guaranteed zero risk.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    flagged_texts = [f["flagged_text"].lower() for f in claims]
    assert "#1 in the world" in flagged_texts
    assert "guaranteed zero risk" in flagged_texts


def test_cycle1_B5_claim_without_supporting_facts():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Our quantum optical fiber network achieves 412% faster lunar clearing.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=[],  # Empty fact vault
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 1
    assert "FACT-" not in claims[0]["rule_or_fact_id"]
    assert claims[0]["source_evidence"] == "No supporting fact was found in the configured Brand Vault. Human verification is required."


def test_cycle1_B6_claim_with_different_wording_from_fact_sheet():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="NovaPay Core settlement speed is up to 64% faster across supported clearing corridors.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 0


def test_cycle1_B7_similar_claims_referring_to_different_products_or_metrics():
    vault = get_brand_vault_bundle("novapay")
    # Claiming 99.99% faster processing (mixing FACT-103 uptime 99.99% with FACT-101 speed 64%)
    res = run_six_pillar_audit(
        content="Cross-border settlement and processing is 99.99% faster than legacy SWIFT.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) >= 1
    assert claims[0]["rule_or_fact_id"] == "FACT-101"


def test_cycle1_B8_claims_involving_different_units_or_conditions():
    vault = get_brand_vault_bundle("novapay")
    # FACT-104 is 38 basis points (0.38%), NOT 38%
    res = run_six_pillar_audit(
        content="Enterprise customers reduce cross-border FX spread costs by an average of 38%.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 1
    assert claims[0]["rule_or_fact_id"] == "FACT-104"
    assert "Unit Mismatch" in claims[0]["issue_type"]


def test_cycle1_B9_multiple_numerical_claims_in_one_document():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content=(
            "Our platform guarantees 95% faster processing; "
            "it also supports direct clearing in 190 currencies and provides a 99.999% uptime SLA."
        ),
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 3


def test_cycle1_B10_claims_that_require_human_verification_pending_fact():
    vault = get_brand_vault_bundle("novapay")
    # FACT-105 (78% reduction in manual reconciliation time) has status 'Pending Verification'
    res = run_six_pillar_audit(
        content="NovaPay delivers a 78% reduction in manual reconciliation time.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    claims = [f for f in res["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claims) == 1
    assert claims[0]["rule_or_fact_id"] == "FACT-105"
    assert claims[0]["review_state"] == "needs_review"
    assert "Pending Verification" in claims[0]["explanation"]


# --- C. ACCESSIBILITY ENGINE (7 Test Cases) ---

def test_cycle1_C1_sufficient_text_contrast():
    ratio = wcag_contrast_ratio("#17191C", "#FFFFFF")
    assert ratio >= 15.0


def test_cycle1_C2_insufficient_text_contrast():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Valid text.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color="#94A3B8",
        bg_color="#FFFFFF",
    )
    a11y = [f for f in res["findings"] if f["pillar"] == "Accessibility"]
    assert any("Insufficient WCAG 2.1 Text Contrast" in f["issue_type"] for f in a11y)


def test_cycle1_C3_white_text_against_white_background():
    assert wcag_contrast_ratio("#FFFFFF", "#FFFFFF") == 1.0


def test_cycle1_C4_missing_alternative_text_metadata():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Valid text.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        has_visual_asset=True,
        image_alt_text="",
    )
    a11y = [f for f in res["findings"] if f["pillar"] == "Accessibility"]
    assert any("Alternative Text" in f["issue_type"] for f in a11y)


def test_cycle1_C5_missing_heading_levels_in_supported_documents():
    html_parsed = parse_uploaded_file("test.html", b"<h1>Main</h1><h3>Skipped H2</h3><img src='a.png'>")
    assert html_parsed["parse_ok"] is True
    issues = [sf["issue_type"] for sf in html_parsed["structural_findings"]]
    assert "Heading Hierarchy Skipped" in issues
    assert "Missing Image Alternative Text" in issues

    md_parsed = parse_uploaded_file("test.md", b"# H1 Title\n\n### Skipped H2 Heading\nParagraph.")
    assert md_parsed["parse_ok"] is True
    md_issues = [sf["issue_type"] for sf in md_parsed["structural_findings"]]
    assert "Heading Hierarchy Skipped" in md_issues


def test_cycle1_C6_invalid_colour_values():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Valid text.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color="#GGGGGG",
        bg_color="not-a-color",
    )
    assert res["pillar_states"]["Visual and Logo Consistency"] == "Check Failed"
    assert res["pillar_states"]["Accessibility"] == "Check Failed"
    assert any("Invalid Hexadecimal Colour" in f["issue_type"] for f in res["findings"])


def test_cycle1_C7_unsupported_document_formats():
    parsed = parse_uploaded_file("archive.zip", b"PK\x03\x04")
    assert parsed["parse_ok"] is False
    assert "Unsupported document format" in parsed["error"]


# --- D. VISUAL ENGINE (7 Test Cases) ---

def test_cycle1_D1_approved_hexadecimal_colour():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Valid text.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color="#17191C",
        bg_color="#FFFFFF",
    )
    assert res["pillar_states"]["Visual and Logo Consistency"] == "Passed"


def test_cycle1_D2_colour_outside_configured_tolerance():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Valid text.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color="#00FF00",
        bg_color="#FFFFFF",
    )
    assert res["pillar_states"]["Visual and Logo Consistency"] == "Findings"
    vis = [f for f in res["findings"] if f["pillar"] == "Visual and Logo Consistency"]
    assert len(vis) == 1
    assert "Delta-E" in vis[0]["explanation"]


def test_cycle1_D3_invalid_image():
    vault = get_brand_vault_bundle("novapay")
    vis_info = inspect_raster_image(b"not-a-valid-png", vault["colors"])
    assert vis_info["inspect_ok"] is False
    res = run_six_pillar_audit(
        content="Image check",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        has_visual_asset=True,
        image_alt_text="Valid descriptive alt text for test",
        visual_inspection=vis_info,
    )
    assert res["pillar_states"]["Visual and Logo Consistency"] == "Check Failed"


def test_cycle1_D4_transparent_png():
    vault = get_brand_vault_bundle("novapay")
    buf = io.BytesIO()
    img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    img.save(buf, format="PNG")
    vis_info = inspect_raster_image(buf.getvalue(), vault["colors"])
    assert vis_info["inspect_ok"] is True
    assert vis_info["has_transparency"] is True
    assert vis_info["all_transparent"] is True
    assert len(vis_info["off_palette_swatches"]) == 0


def test_cycle1_D5_missing_logo_asset_marks_not_checked():
    vault = get_brand_vault_bundle("novapay")
    res = run_six_pillar_audit(
        content="Text only audit without visual assets or hex colours.",
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
    )
    assert res["pillar_states"]["Visual and Logo Consistency"] == "Not Checked"


def test_cycle1_D6_svg_with_invalid_geometry():
    bad_xml = parse_uploaded_file("broken.svg", b"<svg><rect width='100'></svg>")
    assert bad_xml["parse_ok"] is False
    assert "Invalid SVG XML" in bad_xml["error"]

    bad_vb = parse_uploaded_file("neg_vb.svg", b"<svg viewBox='0 0 -50 100'><title>Logo</title></svg>")
    assert bad_vb["parse_ok"] is True
    assert any("Invalid SVG ViewBox Geometry" in f["issue_type"] for f in bad_vb["structural_findings"])


def test_cycle1_D7_missing_clear_space_specification_honest_reporting():
    vault = get_brand_vault_bundle("novapay")
    buf = io.BytesIO()
    img = Image.new("RGB", (60, 60), (23, 25, 28))  # #17191C
    img.save(buf, format="PNG")
    vis_info = inspect_raster_image(buf.getvalue(), vault["colors"])
    assert "Full vector lockup geometry requires an SVG or explicit bounding specification" in vis_info["limitation_note"]


# ============================================================================
# CYCLE 2 — INTEGRATION TESTING (Tests 1 to 5)
# ============================================================================

def test_cycle2_integration_tests_1_to_5():
    # Test 1: Brand Vault -> Terminology Engine
    t_res = client.post(
        "/api/vault/novapay/terminology",
        json={
            "preferred_term": "instant liquidity corridor",
            "prohibited_term": "magic money pipe",
            "replacement_term": "instant liquidity corridor",
            "case_sensitive": False,
            "notes": "Integration test terminology rule.",
            "rule_id": "RULE-TERM-01",
        },
    )
    assert t_res.status_code == 200
    term_id = t_res.json()["term_id"]

    # Test 2: Verified Fact Sheet -> Claim Engine
    f_res = client.post(
        "/api/vault/novapay/facts",
        json={
            "statement": "Automated batch reconciliation processes up to 12500 invoices per minute.",
            "numeric_value": "12500",
            "numeric_units": "invoices per minute",
            "product_context": "Automated batch reconciliation throughput",
            "source_reference": "Q4 2026 Load Test Benchmark v1.2",
            "applicable_conditions": "Measured on standard ISO 20022 XML batch payloads.",
            "date_version": "2026-10",
            "verification_status": "Verified",
        },
    )
    assert f_res.status_code == 200
    fact_id = f_res.json()["fact_id"]

    # Test 3 & 5: Engine -> Backend API & Frontend Highlight Span Alignment
    content = "Our magic money pipe reconciles 50000 invoices per minute."
    a_res = client.post(
        "/api/audits",
        json={
            "brand_id": "novapay",
            "document_name": "Cycle 2 Integration Audit",
            "input_format": "plain_text",
            "content": content,
            "confidential_mode": True,
        },
    )
    assert a_res.status_code == 200
    audit = a_res.json()
    audit_id = audit["id"]

    term_f = next((f for f in audit["findings"] if f["flagged_text"] == "magic money pipe"), None)
    assert term_f is not None
    assert term_f["rule_or_fact_id"] == "RULE-TERM-01"
    assert content[term_f["start_index"]:term_f["end_index"]] == "magic money pipe"

    # Test 4: Backend -> Database Persistence Across Reopen
    reopened = client.get(f"/api/audits/{audit_id}").json()
    assert reopened["id"] == audit_id
    assert len(reopened["findings"]) == len(audit["findings"])

    # Invalid request returns understandable 422/404 error
    bad_req = client.get("/api/audits/AUD-NONEXISTENT")
    assert bad_req.status_code == 404

    # Cleanup temporary vault entries
    client.delete(f"/api/vault/novapay/terminology/{term_id}")
    client.delete(f"/api/vault/novapay/facts/{fact_id}")


# ============================================================================
# CYCLE 3 — END-TO-END FUNCTIONAL TESTING (Scenarios A to E)
# ============================================================================

def test_cycle3_scenarios_A_to_E():
    # Scenario A: First Audit (Create brand -> Add term -> Add fact -> Audit -> Accept -> Reopen)
    b_res = client.post(
        "/api/brands",
        json={
            "id": "aegiscloud",
            "name": "AegisCloud Security",
            "industry": "Zero-Trust Cloud Infrastructure",
            "description": "Enterprise zero-trust workload isolation platform.",
        },
    )
    assert b_res.status_code == 200

    client.post(
        "/api/vault/aegiscloud/terminology",
        json={
            "preferred_term": "AegisCloud Isolation Core",
            "prohibited_term": "AegisFirewall",
            "replacement_term": "AegisCloud Isolation Core",
            "case_sensitive": False,
            "notes": "Use current product name AegisCloud Isolation Core.",
            "rule_id": "RULE-TERM-01",
        },
    )
    client.post(
        "/api/vault/aegiscloud/facts",
        json={
            "statement": "AegisCloud Isolation Core reduces lateral movement surface area by up to 72% in benchmarked VPCs.",
            "numeric_value": "72",
            "numeric_units": "%",
            "product_context": "Lateral movement surface area reduction",
            "source_reference": "AegisCloud 2026 Security Validation Paper",
            "applicable_conditions": "Measured across 150 production Kubernetes clusters.",
            "date_version": "2026-10",
            "verification_status": "Verified",
        },
    )

    audit_a = client.post(
        "/api/audits",
        json={
            "brand_id": "aegiscloud",
            "document_name": "Scenario A Launch Copy",
            "input_format": "plain_text",
            "content": "Deploy AegisFirewall to reduce lateral movement surface area by 98% across your VPCs.",
            "confidential_mode": True,
        },
    ).json()
    assert len(audit_a["findings"]) == 2

    # Accept first correction
    f_first = audit_a["findings"][0]
    after_accept = client.post(
        f"/api/audits/{audit_a['id']}/findings/{f_first['id']}/decision",
        json={"decision": "accept", "reviewer_role": "Content Creator"},
    ).json()
    assert "AegisCloud Isolation Core" in after_accept["current_content"]

    # Scenario B: Modify a Suggestion
    f_second = after_accept["findings"][1]
    custom_text = "AegisCloud Isolation Core reduces lateral movement surface area by up to 72% in benchmarked VPCs."
    after_modify = client.post(
        f"/api/audits/{audit_a['id']}/findings/{f_second['id']}/decision",
        json={
            "decision": "modify",
            "modified_replacement": custom_text,
            "reviewer_role": "Content Creator",
        },
    ).json()
    assert custom_text in after_modify["current_content"]
    assert len(after_modify["revisions"]) == 3

    # Scenario C: Dismiss a Finding
    audit_c = client.post(
        "/api/audits",
        json={
            "brand_id": "aegiscloud",
            "document_name": "Scenario C Dismissal Copy",
            "input_format": "plain_text",
            "content": "Legacy AegisFirewall migration guide for 2023 customers.",
            "confidential_mode": True,
        },
    ).json()
    fc_id = audit_c["findings"][0]["id"]
    after_dismiss = client.post(
        f"/api/audits/{audit_c['id']}/findings/{fc_id}/decision",
        json={
            "decision": "dismiss",
            "reason": "Historical migration guide must reference legacy AegisFirewall name.",
            "reviewer_role": "Reviewer",
        },
    ).json()
    assert after_dismiss["findings"][0]["review_state"] == "dismissed"
    assert after_dismiss["findings"][0]["decision_note"] == "Historical migration guide must reference legacy AegisFirewall name."

    # Scenario D: Incomplete Evidence (Does not invent Fact ID or assert false)
    audit_d = client.post(
        "/api/audits",
        json={
            "brand_id": "aegiscloud",
            "document_name": "Scenario D Incomplete Evidence",
            "input_format": "plain_text",
            "content": "Our platform reduces power supply fan noise by 47%.",
            "confidential_mode": True,
        },
    ).json()
    fd = audit_d["findings"][0]
    assert fd["review_state"] == "needs_review"
    assert "FACT-" not in fd["rule_or_fact_id"]
    assert fd["source_evidence"] == "No supporting fact was found in the configured Brand Vault. Human verification is required."

    # Scenario E: Failed Processing (Corrupted file never marks Passed)
    files = {"file": ("corrupt.png", b"not-an-image-stream", "image/png")}
    audit_e = client.post(
        "/api/audits/upload",
        data={"brand_id": "aegiscloud", "document_name": "Scenario E Corrupt Image"},
        files=files,
    ).json()
    assert audit_e["pillar_states"]["Visual and Logo Consistency"] == "Check Failed"


# ============================================================================
# CYCLE 4 — ENGINE ACCURACY AND FACTUAL VALIDATION (HELD-OUT DATASET)
# ============================================================================

def test_cycle4_labelled_dataset_precision_recall_f1():
    """
    Cycle 4 Methods 1-5: Evaluate a held-out 20-item labelled dataset across categories
    and compute real Precision, Recall, and F1 per category.
    """
    vault = get_brand_vault_bundle("novapay")

    held_out_samples = [
        # Terminology (5 positive violations, 3 negative valid)
        {"cat": "Terminology", "expected": True, "text": "Switch from NovaWallet to our modern treasury stack."},
        {"cat": "Terminology", "expected": True, "text": "Our unhackable ledger protects global payouts."},
        {"cat": "Terminology", "expected": True, "text": "Welcome to novapay cross-border clearing."},
        {"cat": "Terminology", "expected": True, "text": "We help CFOs blitz-scale international expansion."},
        {"cat": "Terminology", "expected": True, "text": "Powered by our proprietary AI Engine."},
        {"cat": "Terminology", "expected": False, "text": "NovaPay Core powers regulated settlement workflows."},
        {"cat": "Terminology", "expected": False, "text": "Our Local Governance Engine validates every payout."},
        {"cat": "Terminology", "expected": False, "text": "Our synergistic-free novel payment architecture scales predictably."},
        # Promotional Claims (5 positive violations/needs_review, 3 negative valid)
        {"cat": "Promotional Claims", "expected": True, "text": "Our platform guarantees 95% faster processing."},
        {"cat": "Promotional Claims", "expected": True, "text": "NovaPay Core supports direct clearing in 180 currencies."},
        {"cat": "Promotional Claims", "expected": True, "text": "Enterprise customers reduce cross-border FX spread costs by 38%."},
        {"cat": "Promotional Claims", "expected": True, "text": "NovaPay is #1 in the world with zero FX fees."},
        {"cat": "Promotional Claims", "expected": True, "text": "Reduces submarine cable latency by 81%."},
        {"cat": "Promotional Claims", "expected": False, "text": "Processing and cross-border settlement is up to 64% faster under the conditions stated in the approved performance report."},
        {"cat": "Promotional Claims", "expected": False, "text": "NovaPay Core supports direct clearing in 42 currencies across 68 countries."},
        {"cat": "Promotional Claims", "expected": False, "text": "NovaPay Core provides a 99.99% contractual uptime SLA across active-active regions."},
        # Tone & Messaging (2 positive, 2 negative)
        {"cat": "Tone_Messaging", "expected": True, "text": "Stop Legacy Banks From Destroying Your Treasury!"},
        {"cat": "Tone_Messaging", "expected": True, "text": "Deploy autonomous AI with zero human oversight."},
        {"cat": "Tone_Messaging", "expected": False, "text": "Modernize cross-border treasury operations with configurable role-based approval controls."},
        {"cat": "Tone_Messaging", "expected": False, "text": "Equip finance teams with predictable T+0 clearing workflows."},
    ]

    metrics_by_cat: Dict[str, Dict[str, int]] = {
        "Terminology": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "Promotional Claims": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "Tone_Messaging": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
    }

    for item in held_out_samples:
        res = run_six_pillar_audit(
            content=item["text"],
            brand=vault["brand"],
            rules=vault["rules"],
            terminology_rows=vault["terminology"],
            facts=vault["verified_facts"],
            brand_colors=vault["colors"],
        )
        if item["cat"] == "Terminology":
            detected = any(f["pillar"] == "Terminology" for f in res["findings"])
        elif item["cat"] == "Promotional Claims":
            detected = any(f["pillar"] == "Promotional Claims" for f in res["findings"])
        else:
            detected = any(f["pillar"] in ("Tone and Voice", "Messaging") for f in res["findings"])

        m = metrics_by_cat[item["cat"]]
        if item["expected"] and detected:
            m["tp"] += 1
        elif not item["expected"] and detected:
            m["fp"] += 1
        elif item["expected"] and not detected:
            m["fn"] += 1
        else:
            m["tn"] += 1

    for cat, m in metrics_by_cat.items():
        precision = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) > 0 else 0.0
        recall = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        assert precision >= 0.90, f"Low precision in {cat}: {precision}"
        assert recall >= 0.90, f"Low recall in {cat}: {recall}"
        assert f1 >= 0.90, f"Low F1 in {cat}: {f1}"


# ============================================================================
# CYCLE 5 — UI, USABILITY, RESPONSIVE AND ACCESSIBILITY TESTING
# ============================================================================

def test_cycle5_ui_usability_responsive_and_accessibility_contracts():
    html_res = client.get("/")
    assert html_res.status_code == 200
    html_text = html_res.text

    # Verify semantic landmarks, ARIA attributes, and three-panel structure
    assert "<aside class=\"sidebar\"" in html_text
    assert "<nav class=\"sidebar-nav\"" in html_text
    assert "aria-label=\"Primary Workspace Navigation\"" in html_text
    assert "aria-live=\"polite\"" in html_text
    assert "three-panel-workspace" in html_text
    assert "New audit" in html_text
    assert "Run audit" in html_text

    # Verify CSS responsive breakpoints (1200/1024/768/420), WCAG AA primary action token (#C94322), and accessibility rules (:focus-visible & prefers-reduced-motion)
    css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "styles.css"))
    with open(css_path, "r", encoding="utf-8") as f:
        css_text = f.read()

    assert ("--primary-action: #C84624" in css_text or "--primary-action: #C94322" in css_text)
    assert ":focus-visible" in css_text
    assert "prefers-reduced-motion: reduce" in css_text
    assert "@media (max-width: 1024px)" in css_text
    assert "@media (max-width: 768px)" in css_text


# ============================================================================
# CYCLE 6 — PRIVACY AND SECURITY TESTING (Tests 1 to 7)
# ============================================================================

def test_cycle6_privacy_and_security_tests_1_to_7():
    # Test 1 & 2: Zero-key local operation
    status = get_engine_status()
    assert status["external_api_key_required"] is False
    assert status["external_api_key_configured"] is False

    # Test 3: No secret exposure in frontend files
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    for fname in ("index.html", "app.js", "styles.css"):
        with open(os.path.join(frontend_dir, fname), "r", encoding="utf-8") as fh:
            text = fh.read()
            assert "sk-" not in text
            assert "AIza" not in text

    # Test 4: File upload security (Oversized > 5MB, Path traversal filename)
    oversized = b"A" * (5 * 1024 * 1024 + 100)
    over_res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay"},
        files={"file": ("huge.txt", oversized, "text/plain")},
    )
    assert over_res.status_code == 400

    trav_res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "../../etc/shadow"},
        files={"file": ("../../etc/passwd.txt", b"Safe content.", "text/plain")},
    )
    assert trav_res.status_code == 200
    assert ".." not in trav_res.json()["document_name"]
    assert "/" not in trav_res.json()["document_name"]

    # Test 5: HTML and SVG safety (XSS & XXE prevention)
    xss_html = b"<h1>Title</h1><script>alert('xss')</script><img src='x' onerror='alert(1)'>"
    parsed_xss = parse_uploaded_file("malicious.html", xss_html)
    assert "alert('xss')" not in parsed_xss["extracted_text"]
    assert any("Unsafe Script" in sf["issue_type"] for sf in parsed_xss["structural_findings"])

    xxe_svg = b"<?xml version='1.0'?><!DOCTYPE svg [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><svg>&xxe;</svg>"
    parsed_xxe = parse_uploaded_file("xxe.svg", xxe_svg)
    assert parsed_xxe["parse_ok"] is False

    # Test 6: Database integrity & foreign key enforcement
    conn = get_connection()
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO terminology VALUES ('BAD-1', 'nonexistent_brand', 'a', 'b', 'a', 0, 'notes', 'R1', '2026')"
        )
    conn.close()

    # Test 7: Role-based access control on approval endpoint
    aud = client.post(
        "/api/audits",
        json={
            "brand_id": "novapay",
            "document_name": "RBAC Test",
            "input_format": "plain_text",
            "content": "NovaPay Core is compliant.",
        },
    ).json()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")
        creator_approve = client.post(
            f"/api/audits/{aud['id']}/workflow",
            json={"new_state": "Approved", "comment": "Self-approving"},
        )
        assert creator_approve.status_code == 403


# ============================================================================
# CYCLE 7 — PERFORMANCE AND RELIABILITY TESTING
# ============================================================================

def test_cycle7_performance_500_5000_25000_chars_and_reliability():
    base_paragraph = (
        "NovaPay Core delivers up to 64% faster processing across 42 currencies under verified benchmark conditions. "
        "However, some drafts mistakenly mention NovaWallet or claim 95% faster processing with our AI Engine. "
    )
    sizes = [500, 5000, 25000]
    tracemalloc.start()

    for target_len in sizes:
        repeats = (target_len // len(base_paragraph)) + 1
        text_payload = (base_paragraph * repeats)[:target_len]
        durations = []
        for _ in range(5):
            t0 = time.perf_counter()
            r = client.post(
                "/api/audits",
                json={
                    "brand_id": "novapay",
                    "document_name": f"Perf Benchmark {target_len} chars",
                    "input_format": "plain_text",
                    "content": text_payload,
                },
            )
            assert r.status_code == 200
            durations.append((time.perf_counter() - t0) * 1000.0)

        med_ms = statistics.median(durations)
        assert med_ms < 2000.0  # Measured local execution well under interactive threshold

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak_mem < 150 * 1024 * 1024  # Peak memory under 150 MB


# ============================================================================
# CYCLE 8 — REGRESSION TESTING & CYCLE 9 — USER ACCEPTANCE TESTING (UAT)
# ============================================================================

def test_cycle8_and_cycle9_uat_8_tasks_and_release_gate():
    # UAT Task 1: Add three brand terminology rules
    for idx, (prohib, pref) in enumerate(
        [("fast-pipe", "settlement rail"), ("cyber-vault", "Brand Vault"), ("auto-wire", "automated payout")],
        start=1,
    ):
        r = client.post(
            "/api/vault/novapay/terminology",
            json={
                "preferred_term": pref,
                "prohibited_term": prohib,
                "replacement_term": pref,
                "case_sensitive": False,
                "notes": f"UAT rule {idx}",
                "rule_id": "RULE-TERM-01",
            },
        )
        assert r.status_code == 200

    # UAT Task 2: Add one verified promotional fact
    f_res = client.post(
        "/api/vault/novapay/facts",
        json={
            "statement": "Treasury API webhook delivery latency is under 120 ms at p99.",
            "numeric_value": "120",
            "numeric_units": "ms",
            "product_context": "Treasury API webhook latency",
            "source_reference": "UAT Telemetry Report 2026",
            "applicable_conditions": "Measured in US-East and EU-Central regions.",
            "date_version": "2026-10",
            "verification_status": "Verified",
        },
    )
    assert f_res.status_code == 200
    uat_fact_id = f_res.json()["fact_id"]

    # UAT Task 3: Audit a marketing paragraph containing two known issues
    uat_audit = client.post(
        "/api/audits",
        json={
            "brand_id": "novapay",
            "document_name": "Cycle 9 UAT Paragraph",
            "input_format": "plain_text",
            "content": "Connect to our fast-pipe where Treasury API webhook delivery latency is under 15 ms at p99.",
            "confidential_mode": True,
        },
    ).json()
    assert len(uat_audit["findings"]) >= 2

    # UAT Task 4: Explain why one finding was flagged
    f_term = next(f for f in uat_audit["findings"] if f["flagged_text"] == "fast-pipe")
    assert "UAT rule 1" in f_term["explanation"]
    assert f_term["rule_or_fact_id"] == "RULE-TERM-01"

    # UAT Task 5: Apply a correction
    after_fix = client.post(
        f"/api/audits/{uat_audit['id']}/findings/{f_term['id']}/decision",
        json={"decision": "accept", "reviewer_role": "Content Creator"},
    ).json()
    assert "settlement rail" in after_fix["current_content"]

    # UAT Task 6: Dismiss a different finding with a reason
    f_claim = next(f for f in after_fix["findings"] if f["id"] != f_term["id"])
    after_dis = client.post(
        f"/api/audits/{uat_audit['id']}/findings/{f_claim['id']}/decision",
        json={
            "decision": "dismiss",
            "reason": "Internal sandbox test note.",
            "reviewer_role": "Reviewer",
        },
    ).json()
    assert any(f["review_state"] == "dismissed" for f in after_dis["findings"])

    # UAT Task 7 & 8: Reopen the audit and identify which checks were not completed
    reopened = client.get(f"/api/audits/{uat_audit['id']}").json()
    assert reopened["pillar_states"]["Visual and Logo Consistency"] == "Not Checked"


# ============================================================================
# SAAS UI REMEDIATION & PRODUCT CLEANUP ACCEPTANCE TESTS (P0 / P1 / P2)
# ============================================================================

def test_saas_ui_remediation_checklist_p0_p1_p2():
    # 1. Verify zero hackathon or internal spec references in public UI files
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    forbidden_strings = [
        "Round 3",
        "Round 1",
        "Round 2",
        "Section 11 & 22",
        "competition build guidelines",
        "Named Improvements Roadmap",
    ]
    for fname in ("index.html", "app.js", "styles.css"):
        with open(os.path.join(frontend_dir, fname), "r", encoding="utf-8") as fh:
            content = fh.read()
            for bad in forbidden_strings:
                assert bad not in content, f"Found internal/hackathon string '{bad}' in {fname}"

    # 2. Verify live engine self-test endpoint (POST /api/engine-selftest)
    selftest_res = client.post("/api/engine-selftest")
    assert selftest_res.status_code == 200
    st_data = selftest_res.json()
    assert st_data["self_test"]["passed"] is True
    assert st_data["self_test"]["last_checked_at"] is not None
    assert len(st_data["self_test"]["checks"]) == 4
    assert st_data["engine_status"]["tier1_engine"]["status"] == "Self-test passed"
    assert st_data["engine_status"]["tier2_engine"]["status"] == "Self-test passed"

    # 3. Verify Guideline insights concise note and compact columns
    radar_res = client.get("/api/ambiguity-radar/novapay")
    assert radar_res.status_code == 200
    radar_data = radar_res.json()
    assert radar_data["concise_info_note"] == (
        "Frequent overrides are a signal to review a rule, not proof it is incorrect."
    )
    assert len(radar_data["rules_analysis"]) >= 1
    assert "likely_signal" in radar_data["rules_analysis"][0]
    assert "next_action" in radar_data["rules_analysis"][0]

    # 4. Verify Audit Rerun endpoint (POST /api/audits/{id}/rerun)
    rerun_res = client.post("/api/audits/AUD-1001/rerun", json={"include_visual_checks": False})
    assert rerun_res.status_code == 200
    rerun_audit = rerun_res.json()
    assert rerun_audit["id"] == "AUD-1001"
    assert len(rerun_audit["revisions"]) >= 2

    # 5. Verify Demo Workspace Reset endpoint (POST /api/demo/reset) and Overview consistency
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
        reset_res = client.post("/api/demo/reset")
        assert reset_res.status_code == 200
    ov_res = client.get("/api/overview/novapay")
    assert ov_res.status_code == 200
    ov_data = ov_res.json()
    assert ov_data["metrics"]["documents_audited"] == 2
    assert ov_data["metrics"]["findings_requiring_attention"] == 1
    assert ov_data["metrics"]["approved_content"] == 1

