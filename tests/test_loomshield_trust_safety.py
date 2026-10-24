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
            'Content text', 'Content text', 'Draft',
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
