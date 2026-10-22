import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import DB_PATH, init_db, reset_demo_workspace
from backend.main import app


@pytest.fixture(scope="module", autouse=True)
def setup_clean_database():
    init_db()
    reset_demo_workspace()
    yield
    reset_demo_workspace()


client = TestClient(app)


# ============================================================================
# D. PRIVACY & TWO-TIER LOCAL ENGINE TESTS
# ============================================================================

def test_privacy_and_two_tier_local_engine_status():
    res = client.get("/api/engine-status")
    assert res.status_code == 200
    data = res.json()
    assert data["external_api_key_required"] is False
    assert data["external_api_key_configured"] is False
    assert data["confidential_mode_default"] is True
    assert data["tier1_engine"]["status"] in ("Available", "Self-test passed")
    assert data["tier2_engine"]["status"] in ("Available", "Self-test passed")
    assert len(data["architecture_matrix"]) == 4


def test_overview_reads_real_database_metrics():
    res = client.get("/api/overview/novapay")
    assert res.status_code == 200
    data = res.json()
    assert data["brand_id"] == "novapay"
    assert data["metrics"]["documents_audited"] == 2
    assert data["metrics"]["findings_requiring_attention"] == 1
    assert data["metrics"]["approved_content"] == 1
    assert data["metrics"]["brand_rules"] >= 7


# ============================================================================
# A. TERMINOLOGY TESTS
# ============================================================================

def test_terminology_prohibited_and_case_sensitive_detection():
    payload = {
        "brand_id": "novapay",
        "document_name": "Terminology Test Draft",
        "input_format": "plain_text",
        "content": "Welcome to novapay! Our proprietary AI Engine powers cross-border treasury.",
        " confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    term_findings = [f for f in audit["findings"] if f["pillar"] == "Terminology"]
    flagged_terms = [f["flagged_text"] for f in term_findings]
    assert "novapay" in flagged_terms
    assert "AI Engine" in flagged_terms


def test_compliant_text_produces_no_false_terminology_finding():
    payload = {
        "brand_id": "novapay",
        "document_name": "Compliant Terminology Draft",
        "input_format": "markdown",
        "content": (
            "# NovaPay Treasury Update\n\n"
            "Our Local Governance Engine operates with human-approved policy guardrails "
            "to support global finance teams."
        ),
        "confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    term_findings = [f for f in audit["findings"] if f["pillar"] == "Terminology"]
    assert len(term_findings) == 0
    assert audit["pillar_states"]["Terminology"] == "Passed"
    # Unchecked visual pillar must be Not Checked, never Passed!
    assert audit["pillar_states"]["Visual and Logo Consistency"] == "Not Checked"


# ============================================================================
# B. PROMOTIONAL CLAIM TESTS (SECTION 8 & 21.B)
# ============================================================================

def test_promotional_claims_exact_match_passes():
    payload = {
        "brand_id": "novapay",
        "document_name": "Verified 64% Claim Draft",
        "input_format": "plain_text",
        "content": (
            "Our platform delivers up to 64% faster processing compared to legacy T+2 SWIFT batching "
            "with human-approved policy guardrails."
        ),
        "confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    claim_findings = [f for f in audit["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claim_findings) == 0
    assert audit["pillar_states"]["Promotional Claims"] == "Passed"


def test_promotional_claims_exaggerated_95_percent_vs_fact_101():
    payload = {
        "brand_id": "novapay",
        "document_name": "Exaggerated 95% Claim Draft",
        "input_format": "plain_text",
        "content": "Our platform guarantees 95% faster processing for enterprise treasury teams.",
        "confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    claim_findings = [f for f in audit["findings"] if f["pillar"] == "Promotional Claims"]
    assert len(claim_findings) >= 1

    numeric_mismatch = next(
        (f for f in claim_findings if "FACT-101" in f["rule_or_fact_id"]),
        None,
    )
    assert numeric_mismatch is not None
    assert "64%" in numeric_mismatch["explanation"]
    assert "64% faster processing" in numeric_mismatch["suggested_correction"]
    assert "Local NLP" in numeric_mismatch["detection_method"]


def test_promotional_claims_unsupported_superlative_and_missing_fact():
    payload = {
        "brand_id": "novapay",
        "document_name": "Missing Evidence & Superlative Test",
        "input_format": "plain_text",
        "content": (
            "NovaPay reduces orbital lunar satellite latency by 83% across deep space relays "
            "and is #1 in the world."
        ),
        "confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    claim_findings = [f for f in audit["findings"] if f["pillar"] == "Promotional Claims"]

    # 1. Superlative '#1 in the world' flagged deterministically
    sup = next((f for f in claim_findings if "#1 in the world" in f["flagged_text"].lower()), None)
    assert sup is not None

    # 2. Claim with no supporting fact in Brand Vault marked needs_review with exact required message
    missing_ev = next((f for f in claim_findings if f["review_state"] == "needs_review"), None)
    assert missing_ev is not None
    assert (
        missing_ev["source_evidence"]
        == "No supporting fact was found in the configured Brand Vault. Human verification is required."
    )


# ============================================================================
# C. CORRECTION TESTS & E. WORKFLOW TESTS (SECTION 14 & 21.C/E)
# ============================================================================

def test_correction_accept_modify_dismiss_and_workflow_approval():
    payload = {
        "brand_id": "novapay",
        "document_name": "End-to-End Correction & Approval Test",
        "input_format": "plain_text",
        "content": (
            "Our platform guarantees 95% faster processing. "
            "Our AI Engine is built with human-approved policy guardrails."
        ),
        "confidential_mode": True,
    }
    res = client.post("/api/audits", json=payload)
    assert res.status_code == 200
    audit = res.json()
    audit_id = audit["id"]
    findings = audit["findings"]
    assert len(findings) >= 2

    # E1: Unresolved findings must block unacknowledged approval
    block_res = client.post(
        f"/api/audits/{audit_id}/workflow",
        json={
            "new_state": "Approved",
            "approver_role": "Reviewer",
            "comment": "Trying to approve with open findings",
            "override_acknowledged": False,
        },
    )
    assert block_res.status_code == 400

    # C1: Accept first finding correction
    f0 = findings[0]
    if f0["suggested_correction"]:
        acc_res = client.post(
            f"/api/audits/{audit_id}/findings/{f0['id']}/decision",
            json={"decision": "accept", "reviewer_role": "Content Creator"},
        )
        assert acc_res.status_code == 200
        updated_audit = acc_res.json()
        assert f0["suggested_correction"] in updated_audit["current_content"]
        # Original content must remain preserved!
        assert updated_audit["original_content"] == payload["content"]

    # Refresh findings and test Modify & Dismiss on remaining findings
    current_detail = client.get(f"/api/audits/{audit_id}").json()
    open_list = [
        f for f in current_detail["findings"] if f["review_state"] in ("open", "needs_review")
    ]

    if len(open_list) >= 1:
        f_mod = open_list[0]
        mod_res = client.post(
            f"/api/audits/{audit_id}/findings/{f_mod['id']}/decision",
            json={
                "decision": "modify",
                "modified_replacement": "Local Governance Engine",
                "reviewer_role": "Content Creator",
            },
        )
        assert mod_res.status_code == 200
        assert "Local Governance Engine" in mod_res.json()["current_content"]

    # Resolve any remaining findings via dismiss with mandatory reason
    current_detail = client.get(f"/api/audits/{audit_id}").json()
    for f_rem in current_detail["findings"]:
        if f_rem["review_state"] in ("open", "needs_review"):
            # Dismissing without reason must fail (400)
            bad_dis = client.post(
                f"/api/audits/{audit_id}/findings/{f_rem['id']}/decision",
                json={"decision": "dismiss", "reason": "", "reviewer_role": "Reviewer"},
            )
            assert bad_dis.status_code == 400

            good_dis = client.post(
                f"/api/audits/{audit_id}/findings/{f_rem['id']}/decision",
                json={
                    "decision": "dismiss",
                    "reason": "Verified footnote context attached in appendix.",
                    "reviewer_role": "Reviewer",
                },
            )
            assert good_dis.status_code == 200

    # E2: Now that all findings are resolved, Reviewer approval succeeds and records approval trail
    app_res = client.post(
        f"/api/audits/{audit_id}/workflow",
        json={
            "new_state": "Approved",
            "approver_role": "Reviewer",
            "comment": "All findings resolved and verified against NovaPay Brand Vault.",
            "override_acknowledged": False,
        },
    )
    assert app_res.status_code == 200
    final_audit = app_res.json()
    assert final_audit["overall_status"] == "Approved"
    assert len(final_audit["approvals"]) >= 1
    assert len(final_audit["revisions"]) >= 2


# ============================================================================
# BRAND VAULT CRUD & AMBIGUITY RADAR TESTS
# ============================================================================

def test_brand_vault_crud_and_ambiguity_radar():
    # Add terminology item
    t_res = client.post(
        "/api/vault/novapay/terminology",
        json={
            "preferred_term": "settlement rails",
            "prohibited_term": "crypto pipes",
            "replacement_term": "settlement rails",
            "case_sensitive": False,
            "notes": "Use enterprise banking terminology.",
            "rule_id": "RULE-TERM-01",
        },
    )
    assert t_res.status_code == 200
    term_id = t_res.json()["term_id"]

    # Edit terminology item
    u_res = client.put(
        f"/api/vault/novapay/terminology/{term_id}",
        json={
            "preferred_term": "regulated settlement rails",
            "prohibited_term": "crypto pipes",
            "replacement_term": "regulated settlement rails",
            "case_sensitive": False,
            "notes": "Updated note for regulated settlement rails.",
            "rule_id": "RULE-TERM-01",
        },
    )
    assert u_res.status_code == 200

    # Delete terminology item
    d_res = client.delete(f"/api/vault/novapay/terminology/{term_id}")
    assert d_res.status_code == 200

    # Check Ambiguity Radar
    radar_res = client.get("/api/ambiguity-radar/novapay")
    assert radar_res.status_code == 200
    radar = radar_res.json()
    assert "honest_scope_note" in radar
    assert len(radar["rules_analysis"]) >= 7


def test_corrupted_docx_upload_marks_check_failed_never_passed():
    files = {"file": ("corrupted.docx", b"not-a-valid-zip-or-docx-stream", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post(
        "/api/audits/upload",
        data={"brand_id": "novapay", "document_name": "Corrupted DOCX Test"},
        files=files,
    )
    assert res.status_code == 200
    audit = res.json()
    assert audit["pillar_states"]["Accessibility"] == "Check Failed"
    assert audit["pillar_states"]["Accessibility"] != "Passed"
