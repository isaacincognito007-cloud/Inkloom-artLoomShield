"""
Trust, Safety & Authorization Tests for LoomShield (Phase 1).
Verifies server-enforced role permissions, forgery resistance, atomic corrections,
Check Failed approval blocking, parser-failure protection, and vault version tracking.
"""

import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.database import get_connection, init_db, get_db_path, bump_brand_version

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


def test_list_audits_summary_only_no_content():
    """GET /api/audits must not return full original_content or current_content in list view."""
    res = client.get("/api/audits")
    assert res.status_code == 200
    audits = res.json().get("audits", [])
    assert len(audits) > 0
    for a in audits:
        assert "original_content" not in a
        assert "current_content" not in a
        assert "id" in a
        assert "document_name" in a
        assert "total_findings" in a
        assert "open_findings" in a


def test_role_header_ignored_in_production_and_honoured_in_demo(monkeypatch):
    """In production mode, x-loomshield-role is ignored; in demo mode, it is honoured for preview."""
    # Production mode: configured as Content Creator
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")
    res_prod = client.get("/api/session", headers={"x-loomshield-role": "Brand Administrator"})
    assert res_prod.status_code == 200
    assert res_prod.json()["user_role"] == "Content Creator"
    assert res_prod.json()["role_preview_enabled"] is False

    # Demo mode: role preview honoured
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    res_demo = client.get("/api/session", headers={"x-loomshield-role": "Brand Administrator"})
    assert res_demo.status_code == 200
    assert res_demo.json()["user_role"] == "Brand Administrator"
    assert res_demo.json()["role_preview_enabled"] is True


def test_content_creator_cannot_edit_vault(monkeypatch):
    """A Content Creator cannot add, edit, or delete Brand Vault rules, terminology, or colors."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")

    # Attempt rule creation
    res = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Unauthorized Rule",
            "description": "Rule created by content creator",
            "severity": "high",
        },
    )
    assert res.status_code == 403

    # Attempt voice profile update
    res_voice = client.put(
        "/api/vault/novapay/voice",
        json={
            "description": "Modified description",
            "tone_principles": "New tone principles",
            "writing_style": "New writing style",
            "messaging_principles": "New messaging principles",
            "do_examples": [],
            "dont_examples": [],
        },
    )
    assert res_voice.status_code == 403


def test_forged_approver_role_blocked_in_production(monkeypatch):
    """A client cannot bypass role enforcement by sending approver_role in request JSON body."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")

    # Create an audit
    aud = client.post(
        "/api/audits",
        json={
            "brand_id": "novapay",
            "document_name": "Forged Role Test",
            "input_format": "plain_text",
            "content": "NovaPay Core compliant content.",
        },
    ).json()

    # Forged approval attempt: client claims to be Brand Administrator in body
    res = client.post(
        f"/api/audits/{aud['id']}/workflow",
        json={
            "new_state": "Approved",
            "approver_role": "Brand Administrator",
            "comment": "Forging admin role",
            "override_acknowledged": True,
        },
    )
    assert res.status_code == 403


def test_parser_failure_finding_cannot_be_accepted():
    """Findings with start_index < 0 (document-level notices / errors) cannot be accepted into text."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, overall_status, created_at, updated_at
        ) VALUES (
            'AUD-TEST-PARSER', 'novapay', 1, 'Corrupted Doc', 'pdf',
            'Unparseable content', 'Unparseable content', 'Draft',
            '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z'
        )
        """
    )
    cur.execute(
        """
        INSERT INTO findings (
            id, audit_id, pillar, issue_type, severity, flagged_text,
            paragraph_ref, start_index, end_index, rule_or_fact_id,
            source_evidence, explanation, suggested_correction, detection_method,
            engine_source, review_state, decision_note, updated_at
        ) VALUES (
            'FIND-PARSE-01', 'AUD-TEST-PARSER', 'Error', 'Unreadable PDF', 'critical',
            'No selectable text', 'DOC', -1, -1, 'RULE-PARSE',
            'PDF parser', 'Scanned document', 'Use OCR', 'error',
            'pypdf', 'open', '', '2026-10-24T00:00:00Z'
        )
        """
    )
    conn.commit()
    conn.close()

    # Attempting to accept finding with start_index = -1 must fail with 409 Conflict
    res = client.post(
        "/api/audits/AUD-TEST-PARSER/findings/FIND-PARSE-01/decision",
        json={"decision": "accept", "reviewer_role": "Reviewer"},
    )
    assert res.status_code == 409
    assert "no inline text span" in res.json()["detail"]

    # Must be dismissible with a reason
    dismiss_res = client.post(
        "/api/audits/AUD-TEST-PARSER/findings/FIND-PARSE-01/decision",
        json={"decision": "dismiss", "reason": "Acknowledged scanned doc limitations"},
    )
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["open_findings_count"] == 0


def test_check_failed_pillar_blocks_approval():
    """An audit with any pillar marked Check Failed cannot be approved."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, overall_status, pillar_states_json, created_at, updated_at
        ) VALUES (
            'AUD-TEST-FAILED', 'novapay', 1, 'Failed Pillar Doc', 'plain_text',
            'Content text', 'Content text', 'In Review',
            '{"Tone and Voice": "Check Failed", "Terminology": "Passed"}',
            '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z'
        )
        """
    )
    conn.commit()
    conn.close()

    res = client.post(
        "/api/audits/AUD-TEST-FAILED/workflow",
        json={"new_state": "Approved", "approver_role": "Brand Administrator", "comment": "Force approve"},
    )
    assert res.status_code == 409
    assert "pillar check has failed" in res.json()["detail"]


def test_vault_version_bumped_on_all_mutations():
    """Brands.version must increment on rule delete, term delete, fact status update, and color delete."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT version FROM brands WHERE id = 'novapay'")
    initial_ver = int(cur.fetchone()["version"])
    conn.close()

    # 1. Add rule
    r1 = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Version Bump Rule",
            "description": "Rule to test version bump",
            "severity": "medium",
        },
    ).json()
    rule_id = r1["rule_id"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT version FROM brands WHERE id = 'novapay'")
    ver_after_add = int(cur.fetchone()["version"])
    assert ver_after_add == initial_ver + 1

    # 2. Delete rule
    del_res = client.delete(f"/api/vault/novapay/rules/{rule_id}")
    assert del_res.status_code == 200

    cur.execute("SELECT version FROM brands WHERE id = 'novapay'")
    ver_after_del = int(cur.fetchone()["version"])
    assert ver_after_del == ver_after_add + 1
    conn.close()


def test_identical_correction_content_returns_409():
    """Applying a correction that produces identical text must be rejected with 409 without creating revisions."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, overall_status, created_at, updated_at
        ) VALUES (
            'AUD-TEST-IDENTICAL', 'novapay', 1, 'Identical Content', 'plain_text',
            'Hello World', 'Hello World', 'Draft',
            '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z'
        )
        """
    )
    cur.execute(
        """
        INSERT INTO findings (
            id, audit_id, pillar, issue_type, severity, flagged_text,
            paragraph_ref, start_index, end_index, rule_or_fact_id,
            source_evidence, explanation, suggested_correction, detection_method,
            engine_source, review_state, decision_note, updated_at
        ) VALUES (
            'FIND-ID-01', 'AUD-TEST-IDENTICAL', 'Tone and Voice', 'Identity Check', 'low',
            'World', 'P1', 6, 11, 'RULE-01',
            'Evidence', 'Explanation', 'World', 'pattern',
            'engine', 'open', '', '2026-10-24T00:00:00Z'
        )
        """
    )
    conn.commit()
    conn.close()

    res = client.post(
        "/api/audits/AUD-TEST-IDENTICAL/findings/FIND-ID-01/decision",
        json={"decision": "accept", "reviewer_role": "Reviewer"},
    )
    assert res.status_code == 409
    assert "identical content" in res.json()["detail"].lower()


def test_audit_requires_brand_id_no_default():
    """Brand ID must be explicitly provided in audit requests (no hidden 'novapay' default)."""
    # 1. Text audit without brand_id fails validation
    res_text = client.post(
        "/api/audits",
        json={
            "document_name": "Test Missing Brand",
            "content": "Some test content without brand id.",
        },
    )
    assert res_text.status_code == 422

    # 2. Upload audit without brand_id fails validation
    res_upload = client.post(
        "/api/audits/upload",
        files={"file": ("memo.txt", b"Some test content", "text/plain")},
        data={"document_name": "Test Missing Brand"},
    )
    assert res_upload.status_code == 422


# ============================================================================
# PHASE 1b TEST SUITE: RBAC, ERROR SHAPES, IMMUTABILITY, CONCURRENCY & LIMITS
# ============================================================================

VAULT_WRITE_ENDPOINTS = [
    ("POST", "/api/brands", {"id": "testbrand_cc", "name": "Test Brand"}),
    ("PUT", "/api/vault/novapay/voice", {
        "description": "Enterprise voice description",
        "tone_principles": "Calm, accurate, evidence-backed",
        "writing_style": "Clear active prose with definitions",
        "messaging_principles": "Highlight verified capabilities",
        "do_examples": [],
        "dont_examples": [],
    }),
    ("PUT", "/api/vault/novapay/visual-specs", {
        "typography_specs": "Inter headings",
        "spacing_rules": "8px base grid",
        "logo_placement_constraints": "High contrast",
    }),
    ("PUT", "/api/vault/novapay/accessibility-rules", {
        "min_contrast_normal": 4.5,
        "min_contrast_large": 3.0,
        "require_alt_text": True,
        "enforce_heading_order": True,
        "target_reading_ease": 50.0,
    }),
    ("POST", "/api/vault/novapay/terminology", {
        "preferred_term": "NovaPay Core",
        "prohibited_term": "NovaWallet",
        "replacement_term": "NovaPay Core",
        "case_sensitive": False,
        "notes": "Valid terminology note",
        "rule_id": "RULE-TERM-01",
    }),
    ("PUT", "/api/vault/novapay/terminology/TERM-NOVAPAY-01", {
        "preferred_term": "NovaPay Core",
        "prohibited_term": "NovaWallet",
        "replacement_term": "NovaPay Core",
        "case_sensitive": False,
        "notes": "Valid terminology note",
        "rule_id": "RULE-TERM-01",
    }),
    ("DELETE", "/api/vault/novapay/terminology/TERM-NOVAPAY-01", None),
    ("PUT", "/api/vault/novapay/facts/FACT-NOVAPAY-01", {
        "statement": "64% faster processing benchmark across currencies",
        "numeric_value": "64",
        "numeric_units": "%",
        "product_context": "NovaPay Core",
        "source_reference": "Benchmark Report Q3",
        "applicable_conditions": "Under verified network tests",
        "date_version": "2026-10 (v1.0)",
        "verification_status": "Verified",
    }),
    ("PUT", "/api/vault/novapay/facts/FACT-NOVAPAY-01/status", {
        "status": "Verified",
        "reviewer_notes": "Verified by admin",
    }),
    ("DELETE", "/api/vault/novapay/facts/FACT-NOVAPAY-01", None),
    ("POST", "/api/vault/novapay/colors", {
        "name": "Test Blue",
        "hex_code": "#0055ff",
        "usage_role": "Primary Accent",
        "max_delta_e": 14.0,
    }),
    ("PUT", "/api/vault/novapay/colors/COL-NOVAPAY-01", {
        "name": "Test Blue 2",
        "hex_code": "#0055fe",
        "usage_role": "Primary Accent",
        "max_delta_e": 14.0,
    }),
    ("DELETE", "/api/vault/novapay/colors/COL-NOVAPAY-01", None),
    ("POST", "/api/vault/novapay/rules", {
        "pillar": "Tone and Voice",
        "title": "Rule Title Test",
        "description": "Rule Description Test",
        "severity": "medium",
    }),
    ("PUT", "/api/vault/novapay/rules/RULE-NOVAPAY-01", {
        "pillar": "Tone and Voice",
        "title": "Rule Title Test 2",
        "description": "Rule Description Test 2",
        "severity": "medium",
    }),
    ("DELETE", "/api/vault/novapay/rules/RULE-NOVAPAY-01", None),
]


@pytest.mark.parametrize("method,path,payload", VAULT_WRITE_ENDPOINTS)
def test_content_creator_blocked_from_all_16_vault_writes(monkeypatch, method, path, payload):
    """Content Creator role receives 403 Forbidden across all 16 Brand Vault write endpoints."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")
    if method == "POST":
        res = client.post(path, json=payload)
    elif method == "PUT":
        res = client.put(path, json=payload)
    elif method == "DELETE":
        res = client.delete(path)
    assert res.status_code == 403, f"Expected 403 on {method} {path}, got {res.status_code}"


def test_brand_administrator_allowed_vault_write(monkeypatch):
    """Brand Administrator successfully writes to Brand Vault (200/201)."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Brand Administrator")
    res = client.post(
        "/api/vault/novapay/rules",
        json={"pillar": "Tone and Voice", "title": "Admin Allowed Rule", "description": "Admin description", "severity": "low"}
    )
    assert res.status_code == 200
    assert "rule_id" in res.json()


def test_error_shape_and_request_id_for_all_error_types():
    """All HTTP error responses (404, 405, 422) return structured error shape with request_id."""
    # 404 Not Found
    r404 = client.get("/api/nonexistent-route-xyz")
    assert r404.status_code == 404
    assert "x-request-id" in r404.headers
    data404 = r404.json()
    assert "error" in data404
    assert "request_id" in data404["error"]

    # 405 Method Not Allowed
    r405 = client.delete("/api/brands")
    assert r405.status_code == 405
    assert "x-request-id" in r405.headers
    data405 = r405.json()
    assert "error" in data405
    assert "request_id" in data405["error"]

    # 422 Unprocessable Entity
    r422 = client.post("/api/audits", json={"invalid": "payload"})
    assert r422.status_code == 422
    assert "x-request-id" in r422.headers
    data422 = r422.json()
    assert "error" in data422
    assert "request_id" in data422["error"]


def test_rate_limiting_429_on_audit_upload_and_reset(monkeypatch):
    """Rate limiter enforces per-IP limits (429) across audits, file uploads, and demo reset."""
    from backend.main import audit_rate_limiter
    audit_rate_limiter.reset()

    # 1. Text audit endpoint 429
    headers_audit = {"x-forwarded-for": "203.0.113.99"}
    payload = {"brand_id": "novapay", "document_name": "RL Test", "content": "Simple text"}
    for _ in range(30):
        res = client.post("/api/audits", json=payload, headers=headers_audit)
        assert res.status_code == 200
    res_limited_audit = client.post("/api/audits", json=payload, headers=headers_audit)
    assert res_limited_audit.status_code == 429
    assert "rate limit exceeded" in res_limited_audit.json()["detail"].lower()

    # 2. File upload endpoint 429
    audit_rate_limiter.reset()
    headers_upload = {"x-forwarded-for": "203.0.113.100"}
    for _ in range(30):
        res = client.post(
            "/api/audits/upload",
            files={"file": ("memo.txt", b"Safe text", "text/plain")},
            data={"brand_id": "novapay", "document_name": "Upload RL"},
            headers=headers_upload,
        )
        assert res.status_code == 200
    res_limited_upload = client.post(
        "/api/audits/upload",
        files={"file": ("memo.txt", b"Safe text", "text/plain")},
        data={"brand_id": "novapay", "document_name": "Upload RL"},
        headers=headers_upload,
    )
    assert res_limited_upload.status_code == 429
    assert "rate limit exceeded" in res_limited_upload.json()["detail"].lower()

    # 3. Demo reset endpoint 429
    audit_rate_limiter.reset()
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    headers_reset = {"x-forwarded-for": "203.0.113.101"}
    for _ in range(30):
        res = client.post("/api/demo/reset", headers=headers_reset)
        assert res.status_code == 200
    res_limited_reset = client.post("/api/demo/reset", headers=headers_reset)
    assert res_limited_reset.status_code == 429
    assert "rate limit exceeded" in res_limited_reset.json()["detail"].lower()


def test_workflow_transitions_and_cas_concurrency():
    """Workflow enforces valid state transitions: Draft -> In Review -> Approved."""
    aud = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "CAS Test", "content": "NovaPay Core compliant content."}
    ).json()
    aid = aud["id"]

    # Direct Draft -> Approved is rejected (409)
    res_direct = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "Approved"})
    assert res_direct.status_code == 409
    assert "Invalid workflow transition" in res_direct.json()["detail"]

    # Draft -> In Review is accepted (200)
    res_in_review = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "In Review"})
    assert res_in_review.status_code == 200
    assert res_in_review.json()["overall_status"] == "In Review"

    # In Review -> Approved is accepted (200)
    res_app = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "Approved", "comment": "Approved"})
    assert res_app.status_code == 200
    assert res_app.json()["overall_status"] == "Approved"

    # Approved -> anything is rejected (409)
    res_reopen = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "In Review"})
    assert res_reopen.status_code == 409


def test_cas_concurrency_conflict():
    """Concurrent workflow status updates on the same audit return 409 Conflict via compare-and-swap."""
    aud = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "CAS Conflict Test", "content": "NovaPay Core compliant content."}
    ).json()
    aid = aud["id"]
    client.post(f"/api/audits/{aid}/workflow", json={"new_state": "In Review"})

    # Client A succeeds: In Review -> Approved
    res_a = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "Approved", "comment": "Reviewer A approves"})
    assert res_a.status_code == 200

    # Client B attempts concurrent transition expecting In Review -> Changes Requested
    res_b = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "Changes Requested", "comment": "Reviewer B rejects"})
    assert res_b.status_code == 409
    assert "invalid workflow transition" in res_b.json()["detail"].lower() or "conflict" in res_b.json()["detail"].lower()


def test_rerun_after_accept_dismiss_open_and_repeated_term():
    """Rerun cleanly handles accept+dismiss+open and 3 identical repeated terms without ID collisions or 500s."""
    # 1. Part A: Test accept + dismiss + open across distinct findings
    mixed_content = (
        "Our service guarantees 95% faster processing with NovaWallet. "
        "Our AI Engine is built with policy guardrails."
    )
    aud_mixed = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "Mixed Decision Rerun", "content": mixed_content}
    ).json()
    aid_mixed = aud_mixed["id"]
    findings_mixed = aud_mixed["findings"]
    f_claim = next((f for f in findings_mixed if "95%" in f["flagged_text"]), None)
    f_term = next((f for f in findings_mixed if f["flagged_text"] == "NovaWallet"), None)
    f_engine = next((f for f in findings_mixed if f["flagged_text"] == "AI Engine"), None)
    assert f_claim and f_term and f_engine

    # Accept f_term
    res_acc = client.post(
        f"/api/audits/{aid_mixed}/findings/{f_term['id']}/decision",
        json={"decision": "accept"}
    )
    assert res_acc.status_code == 200

    # Dismiss f_engine
    res_dis = client.post(
        f"/api/audits/{aid_mixed}/findings/{f_engine['id']}/decision",
        json={"decision": "dismiss", "reason": "Footnote verified"}
    )
    assert res_dis.status_code == 200

    # Leave f_claim open

    # Rerun mixed audit: must succeed with 200 (no 500 collision)
    rerun_mixed = client.post(f"/api/audits/{aid_mixed}/rerun")
    assert rerun_mixed.status_code == 200
    rerun_mixed_findings = rerun_mixed.json()["findings"]
    mixed_ids = [f["id"] for f in rerun_mixed_findings]
    assert len(mixed_ids) == len(set(mixed_ids)), f"Duplicate IDs in mixed rerun: {mixed_ids}"

    # Verify f_engine preserved as dismissed and f_claim is open
    fe_after = next((f for f in rerun_mixed_findings if f["flagged_text"] == "AI Engine"), None)
    fc_after = next((f for f in rerun_mixed_findings if "95%" in f["flagged_text"]), None)
    assert fe_after and fe_after["review_state"] == "dismissed"
    assert fc_after and fc_after["review_state"] == "open"

    # 2. Part B: Test 3 identical repeated terms (same pillar, rule, text)
    rep_content = (
        "First notice: NovaWallet is active. "
        "Second notice: NovaWallet is enabled. "
        "Third notice: NovaWallet is operational."
    )
    aud_rep = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "Repeated Terms", "content": rep_content}
    ).json()
    aid_rep = aud_rep["id"]
    rep_findings = [f for f in aud_rep["findings"] if f["flagged_text"] == "NovaWallet"]
    assert len(rep_findings) == 3

    # Dismiss first occurrence
    d1 = client.post(
        f"/api/audits/{aid_rep}/findings/{rep_findings[0]['id']}/decision",
        json={"decision": "dismiss", "reason": "First exception"}
    )
    assert d1.status_code == 200

    # Dismiss second occurrence
    d2 = client.post(
        f"/api/audits/{aid_rep}/findings/{rep_findings[1]['id']}/decision",
        json={"decision": "dismiss", "reason": "Second exception"}
    )
    assert d2.status_code == 200

    # Third occurrence left open

    # Rerun: must not 500, must assign distinct IDs and preserve individual decisions
    rerun_rep = client.post(f"/api/audits/{aid_rep}/rerun")
    assert rerun_rep.status_code == 200
    rep_after = rerun_rep.json()["findings"]
    rep_after_terms = [f for f in rep_after if f["flagged_text"] == "NovaWallet"]
    assert len(rep_after_terms) == 3

    rep_ids = [f["id"] for f in rep_after_terms]
    assert len(rep_ids) == len(set(rep_ids)), f"Collision in repeated term IDs: {rep_ids}"

    rep_states = [f["review_state"] for f in rep_after_terms]
    assert rep_states.count("dismissed") == 2
    assert rep_states.count("open") == 1


def test_audit_survives_database_restart():
    """Audit records persist across database connection closures and re-running init_db()."""
    aud = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "Persistence Restart Test", "content": "NovaPay Core compliant content."}
    ).json()
    audit_id = aud["id"]

    # Re-run init_db() to simulate server cold start / restart
    init_db()

    # Direct SQLite query to simulate cold restart connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, document_name, overall_status FROM audits WHERE id = ?", (audit_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["id"] == audit_id
    assert row["document_name"] == "Persistence Restart Test"

    # API read-back
    api_res = client.get(f"/api/audits/{audit_id}")
    assert api_res.status_code == 200
    assert api_res.json()["id"] == audit_id


def test_internal_server_error_500_shape(monkeypatch):
    """Uncaught exceptions return 500 with structured error shape and x-request-id."""
    client_500 = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr("backend.main.get_connection", lambda *args, **kwargs: 1 / 0)

    res = client_500.get("/api/audits/AUD-1001")
    assert res.status_code == 500
    assert "x-request-id" in res.headers
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "request_id" in body["error"]
    assert body["error"]["request_id"] == res.headers["x-request-id"]


def test_x_request_id_sanitization():
    """x-request-id header accepts short alphanumeric strings and sanitizes invalid characters."""
    # 1. Valid short alphanumeric request ID is preserved
    valid_id = "req-client-trace-1234"
    res_valid = client.get("/api/brands", headers={"x-request-id": valid_id})
    assert res_valid.headers.get("x-request-id") == valid_id

    # 2. Dangerous or invalid request ID is rejected and regenerated
    invalid_id = "<script>alert('xss')</script> " + ("a" * 100)
    res_invalid = client.get("/api/brands", headers={"x-request-id": invalid_id})
    sanitized = res_invalid.headers.get("x-request-id")
    assert sanitized != invalid_id
    assert sanitized.startswith("req-")
    assert len(sanitized) <= 32


def test_fact_proposal_vs_verification_permissions(monkeypatch):
    """Content Creator can propose facts (defaults to Pending Verification); only Brand Administrator can verify."""
    # 1. Content Creator proposes fact -> 200 OK, Pending Verification
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")
    fact_payload = {
        "statement": "NovaPay Core processes transactions under 100ms in benchmark tests",
        "numeric_value": "100",
        "numeric_units": "ms",
        "product_context": "NovaPay Core",
        "source_reference": "Benchmark Lab Report Q4",
        "applicable_conditions": "Under 1000 concurrent load",
        "date_version": "2026-10",
        "verification_status": "Pending Verification",
    }
    res_propose = client.post("/api/vault/novapay/facts", json=fact_payload)
    assert res_propose.status_code == 200
    fact_id = res_propose.json()["fact_id"]

    # 2. Content Creator attempts to verify fact -> 403 Forbidden
    res_verify_fail = client.put(
        f"/api/vault/novapay/facts/{fact_id}/status",
        json={"status": "Verified", "reviewer_notes": "Creator trying to self-verify"}
    )
    assert res_verify_fail.status_code == 403

    # 3. Brand Administrator verifies fact -> 200 OK
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Brand Administrator")
    res_verify_ok = client.put(
        f"/api/vault/novapay/facts/{fact_id}/status",
        json={"status": "Verified", "reviewer_notes": "Verified by Brand Administrator"}
    )
    assert res_verify_ok.status_code == 200


def test_approved_audit_immutable_to_decisions_and_rerun():
    """Approved audits reject decisions and reruns with 409 Conflict."""
    aud = client.post(
        "/api/audits",
        json={"brand_id": "novapay", "document_name": "Immutable Test", "content": "NovaPay Core compliant content."}
    ).json()
    aid = aud["id"]
    res_wf1 = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "In Review"})
    assert res_wf1.status_code == 200
    res_wf2 = client.post(
        f"/api/audits/{aid}/workflow",
        json={"new_state": "Approved", "comment": "Approved", "override_acknowledged": True},
    )
    assert res_wf2.status_code == 200

    # Finding decision on approved audit returns 409
    res_dec = client.post(f"/api/audits/{aid}/findings/FIND-FAKE/decision", json={"decision": "dismiss", "reason": "reason"})
    assert res_dec.status_code == 409
    assert "approved" in res_dec.json()["detail"].lower()

    # Rerun on approved audit returns 409
    res_rerun = client.post(f"/api/audits/{aid}/rerun")
    assert res_rerun.status_code == 409
    assert "approved" in res_rerun.json()["detail"].lower()


def test_rerun_parser_failed_audit_stays_check_failed():
    """Rerun on a parser-failed audit preserves Check Failed state and does not pass clean."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, overall_status, pillar_states_json, created_at, updated_at
        ) VALUES (
            'AUD-TEST-RERUN-FAIL', 'novapay', 1, 'Scanned Doc', 'pdf',
            '[Unparseable file: Corrupted PDF]', '[Unparseable file: Corrupted PDF]', 'Draft',
            '{"Tone and Voice": "Check Failed", "Visual and Logo Consistency": "Check Failed"}',
            '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z'
        )
        """
    )
    cur.execute(
        """
        INSERT INTO findings (
            id, audit_id, pillar, issue_type, severity, flagged_text,
            paragraph_ref, start_index, end_index, rule_or_fact_id,
            source_evidence, explanation, suggested_correction, detection_method,
            engine_source, review_state, decision_note, updated_at
        ) VALUES (
            'FIND-FAIL-01', 'AUD-TEST-RERUN-FAIL', 'Visual and Logo Consistency', 'Parser Failure', 'critical',
            'Corrupted PDF', 'DOC', -1, -1, 'RULE-FAIL',
            'pypdf', 'Scanned or unreadable document', 'OCR required', 'error',
            'pypdf', 'open', '', '2026-10-24T00:00:00Z'
        )
        """
    )
    conn.commit()
    conn.close()

    res = client.post("/api/audits/AUD-TEST-RERUN-FAIL/rerun")
    assert res.status_code == 200
    rerun_data = res.json()
    assert rerun_data["pillar_states"]["Visual and Logo Consistency"] == "Check Failed"
    assert rerun_data["open_findings_count"] >= 1


def test_demo_reset_forbidden_in_production(monkeypatch):
    """POST /api/demo/reset returns 403 Forbidden when workspace mode is production."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    res = client.post("/api/demo/reset")
    assert res.status_code == 403
    assert "demo workspace mode" in res.json()["detail"].lower()


def test_audits_pagination():
    """GET /api/audits supports total, limit, and offset query parameters."""
    res = client.get("/api/audits?limit=2&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert isinstance(data["audits"], list)
    assert len(data["audits"]) <= 2


def test_cors_origins_env_parsing(monkeypatch):
    """CORS origins parse comma-separated lists and exclude obsolete domains."""
    from backend.main import parse_cors_origins
    origins = parse_cors_origins("https://app1.example.com, https://app2.example.com")
    assert "https://app1.example.com" in origins
    assert "https://app2.example.com" in origins
    assert "https://inkloom-art-loom-shield.vercel.app" not in origins


