"""
Tests for Round 3 Day 2:
- Part B: Ed25519 Signed Compliance Certificates (canonical JSON, sign/verify round trip,
  byte-flip detection, wrong key detection, 409 on unapproved audits, idempotency across calls,
  content_sha256 matching approval, rate limiting on /api/certificates/verify, ephemeral key flag,
  and CLI scripts generate_signing_key.py / verify_certificate.py).
- Part C: Demo Identities & Separation of Duties (HMAC token login, forged/tampered/expired -> 401,
  self-approval blocked, different reviewer approves, actor recorded in audits/approvals/events,
  production ignores tokens, token overrides role header).
"""

import base64
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.main as main_mod
from backend.certificates import canonicalize_payload, verify_certificate_envelope
from backend.config import _b64url_encode, issue_demo_token
from backend.database import init_db

client = TestClient(main_mod.app)
ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    init_db()
    main_mod.audit_rate_limiter.reset()
    main_mod.verify_rate_limiter.reset()


# ============================================================================
# PART B: SIGNED COMPLIANCE CERTIFICATE TESTS
# ============================================================================

def test_certificate_sign_and_verify_round_trip(tmp_path):
    """Issue a certificate for Approved audit AUD-1002 and verify via API and offline CLI."""
    res_post = client.post("/api/audits/AUD-1002/certificate")
    assert res_post.status_code == 200
    env = res_post.json()

    assert env["alg"] == "Ed25519"
    assert isinstance(env["kid"], str) and len(env["kid"]) == 16
    assert isinstance(env["signature_b64"], str) and len(env["signature_b64"]) > 40

    payload = env["payload"]
    assert payload["certificate_version"] == 2
    assert payload["audit_id"] == "AUD-1002"
    assert "not legal advice; not a guarantee of regulatory compliance" in payload["limitations"].lower()

    # Verify via POST /api/certificates/verify
    res_ver = client.post("/api/certificates/verify", json=env)
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["valid"] is True
    assert ver_data["status"] == "valid"
    assert ver_data["audit_exists_on_server"] is True
    assert ver_data["content_hash_matches_server"] is True

    # Verify via offline CLI script scripts/verify_certificate.py
    pub_res = client.get("/api/certificates/public-key")
    assert pub_res.status_code == 200
    pub_b64 = pub_res.json()["public_key_b64"]

    cert_file = tmp_path / "cert_aud_1002.json"
    cert_file.write_text(json.dumps(env), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "verify_certificate.py"), str(cert_file), "--public-key", pub_b64],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Offline verifier failed: {proc.stdout} {proc.stderr}"
    assert "VALID:" in proc.stdout


def test_certificate_flipping_any_payload_byte_invalid():
    """Mutating any field or byte in the certificate payload invalidates the Ed25519 signature."""
    env = client.post("/api/audits/AUD-1002/certificate").json()

    # 1. Mutate document_name by 1 character
    tampered_doc = copy.deepcopy(env)
    tampered_doc["payload"]["document_name"] = tampered_doc["payload"]["document_name"] + "!"
    res1 = client.post("/api/certificates/verify", json=tampered_doc)
    assert res1.status_code == 200
    assert res1.json()["valid"] is False
    assert res1.json()["status"] == "bad_signature"
    assert any("bad signature" in r.lower() for r in res1.json()["reasons"])

    # 2. Flip a single bit in content_sha256
    tampered_hash = copy.deepcopy(env)
    orig_h = tampered_hash["payload"]["content_sha256"]
    flipped_char = "0" if orig_h[0] != "0" else "1"
    tampered_hash["payload"]["content_sha256"] = flipped_char + orig_h[1:]
    res2 = client.post("/api/certificates/verify", json=tampered_hash)
    assert res2.status_code == 200
    assert res2.json()["valid"] is False
    assert res2.json()["status"] == "bad_signature"


def test_certificate_wrong_key_invalid():
    """Verifying a certificate against a different Ed25519 key fails with unknown_kid or bad_signature."""
    env = client.post("/api/audits/AUD-1002/certificate").json()

    # Generate a different Ed25519 keypair
    other_priv = Ed25519PrivateKey.from_private_bytes(os.urandom(32))
    other_pub_bytes = other_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    other_pub_b64 = base64.b64encode(other_pub_bytes).decode("ascii")

    # 1. Verify with wrong public_key_b64 -> unknown_kid
    res_kid = client.post(
        "/api/certificates/verify",
        json={"certificate": env, "public_key_b64": other_pub_b64},
    )
    assert res_kid.status_code == 200
    assert res_kid.json()["valid"] is False
    assert res_kid.json()["status"] == "unknown_kid"

    # 2. Even if attacker spoofs kid to match other_pub_b64, Ed25519 signature check fails with bad_signature
    spoofed = copy.deepcopy(env)
    spoofed["kid"] = res_kid.json()["expected_kid"]
    res_sig = verify_certificate_envelope(spoofed, public_key_b64=other_pub_b64)
    assert res_sig["valid"] is False
    assert res_sig["status"] == "bad_signature"


def test_certificate_unapproved_audit_returns_409():
    """Issuing or downloading a certificate for an unapproved audit (In Review or Draft) returns 409."""
    # AUD-1001 is In Review
    res_post = client.post("/api/audits/AUD-1001/certificate")
    assert res_post.status_code == 409
    body = res_post.json()
    assert "error" in body
    assert body["error"]["code"] == "CONFLICT"

    res_get = client.get("/api/audits/AUD-1001/certificate")
    assert res_get.status_code == 409


def test_certificate_stable_across_calls():
    """Re-issuing or downloading a certificate for an Approved audit is idempotent and byte-identical."""
    c1 = client.post("/api/audits/AUD-1002/certificate").json()
    time.sleep(0.05)
    c2 = client.post("/api/audits/AUD-1002/certificate").json()
    c3 = client.get("/api/audits/AUD-1002/certificate?download=true")

    assert c3.status_code == 200
    assert "attachment; filename=" in c3.headers.get("content-disposition", "")
    c3_json = c3.json()

    assert c1 == c2 == c3_json
    assert c1["payload"]["certificate_id"] == c2["payload"]["certificate_id"]
    assert c1["payload"]["issued_at"] == c2["payload"]["issued_at"]
    assert c1["signature_b64"] == c2["signature_b64"]


def test_certificate_canonicalization_deterministic_key_order_and_unicode():
    """canonicalize_payload produces identical UTF-8 bytes regardless of dict key order and preserves unicode."""
    p1 = {
        "z_key": "Valeur vérifiée — 100% conforme",
        "a_key": 1,
        "nested": {"b": [1, 2, 3], "a": "café"},
    }
    p2 = {
        "nested": {"a": "café", "b": [1, 2, 3]},
        "a_key": 1,
        "z_key": "Valeur vérifiée — 100% conforme",
    }
    b1 = canonicalize_payload(p1)
    b2 = canonicalize_payload(p2)
    assert b1 == b2
    decoded = b1.decode("utf-8")
    assert "Valeur vérifiée — 100% conforme" in decoded
    assert "\n" not in decoded and ": " not in decoded


def test_certificate_content_sha256_equals_approval_sha256():
    """Certificate content_sha256 must match the approval record's content_sha256."""
    detail = client.get("/api/audits/AUD-1002").json()
    approved_records = [a for a in detail["approvals"] if a["new_state"] == "Approved"]
    assert len(approved_records) >= 1
    approval_sha = approved_records[-1]["content_sha256"]

    cert = client.post("/api/audits/AUD-1002/certificate").json()
    assert cert["payload"]["content_sha256"] == approval_sha


def test_certificate_verify_endpoint_rate_limited():
    """POST /api/certificates/verify enforces per-IP rate limiting and returns 429 in standard error shape."""
    env = client.post("/api/audits/AUD-1002/certificate").json()
    main_mod.verify_rate_limiter.reset()

    statuses = []
    last_resp = None
    for _ in range(35):
        r = client.post("/api/certificates/verify", json=env)
        statuses.append(r.status_code)
        if r.status_code == 429:
            last_resp = r
            break

    assert 429 in statuses
    assert last_resp is not None
    err_body = last_resp.json()
    assert err_body["error"]["code"] == "RATE_LIMITED"
    assert "request_id" in err_body["error"]


def test_certificate_ephemeral_key_flag_and_generate_key_script(monkeypatch):
    """When LOOMSHIELD_SIGNING_KEY is unset, ephemeral_key is True; when set via generate_signing_key.py, False."""
    monkeypatch.delenv("LOOMSHIELD_SIGNING_KEY", raising=False)
    pub_ephem = client.get("/api/certificates/public-key").json()
    assert pub_ephem["ephemeral_key"] is True
    assert "ephemeral demo key: valid only until the server restarts" in pub_ephem["key_notice"]

    # Run scripts/generate_signing_key.py and configure LOOMSHIELD_SIGNING_KEY
    proc = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_signing_key.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = dict(line.strip().split("=", 1) for line in proc.stdout.strip().splitlines() if "=" in line)
    assert "LOOMSHIELD_SIGNING_KEY" in lines
    assert "PUBLIC_KEY_B64" in lines
    assert "KID" in lines

    monkeypatch.setenv("LOOMSHIELD_SIGNING_KEY", lines["LOOMSHIELD_SIGNING_KEY"])
    pub_pers = client.get("/api/certificates/public-key").json()
    assert pub_pers["ephemeral_key"] is False
    assert pub_pers["kid"] == lines["KID"]
    assert pub_pers["public_key_b64"] == lines["PUBLIC_KEY_B64"]


# ============================================================================
# PART C: DEMO IDENTITIES & SEPARATION OF DUTIES TESTS
# ============================================================================

def test_demo_login_and_forged_expired_tampered_tokens_return_401(monkeypatch):
    """Forged, tampered, and expired Bearer tokens return 401 in standard error shape."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    monkeypatch.setenv("LOOMSHIELD_SESSION_SECRET", "test-secret-key-for-hmac-verification")

    # 1. Valid login for Priya Nair (Content Creator)
    login_res = client.post("/api/demo/login", json={"user_id": "usr_priya"})
    assert login_res.status_code == 200
    token_data = login_res.json()
    token = token_data["token"]
    assert token_data["role"] == "Content Creator"
    assert token_data["user_name"] == "Priya Nair"

    sess_ok = client.get("/api/session", headers={"Authorization": f"Bearer {token}"})
    assert sess_ok.status_code == 200
    assert sess_ok.json()["user_id"] == "usr_priya"
    assert sess_ok.json()["user_role"] == "Content Creator"

    # 2. Forged signature -> 401
    forged_token = token.rsplit(".", 1)[0] + ".forgedSignatureBytes12345"
    res_forged = client.get("/api/session", headers={"Authorization": f"Bearer {forged_token}"})
    assert res_forged.status_code == 401
    assert res_forged.json()["error"]["code"] == "UNAUTHORIZED"

    # 3. Tampered payload (attempting to escalate usr_priya to Brand Administrator) -> 401
    tampered_claims = {
        "user_id": "usr_priya",
        "user_name": "Priya Nair",
        "initials": "PN",
        "role": "Brand Administrator",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    tampered_b64 = _b64url_encode(json.dumps(tampered_claims).encode("utf-8"))
    tampered_token = f"{tampered_b64}.{token.rsplit('.', 1)[1]}"
    res_tampered = client.get("/api/session", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401
    assert res_tampered.json()["error"]["code"] == "UNAUTHORIZED"

    # 4. Expired token -> 401
    expired_bundle = issue_demo_token("usr_marcus", ttl_seconds=-10)
    res_expired = client.get("/api/session", headers={"Authorization": f"Bearer {expired_bundle['token']}"})
    assert res_expired.status_code == 401
    assert res_expired.json()["error"]["code"] == "UNAUTHORIZED"
    assert "expired" in res_expired.json()["error"]["message"].lower()


def test_self_approval_blocked_and_different_reviewer_succeeds(monkeypatch):
    """The user who submitted an audit for review cannot approve it; a different reviewer succeeds."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")

    marcus_token = client.post("/api/demo/login", json={"user_id": "usr_marcus"}).json()["token"]
    ava_token = client.post("/api/demo/login", json={"user_id": "usr_ava"}).json()["token"]

    # Marcus (Reviewer) creates an audit and submits it for review
    create_res = client.post(
        "/api/audits",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={
            "brand_id": "novapay",
            "document_name": "Separation of Duties Check",
            "content": "NovaPay Core processes enterprise cross-border payouts.",
        },
    )
    assert create_res.status_code == 200
    audit_id = create_res.json()["id"]

    sub_res = client.post(
        f"/api/audits/{audit_id}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "In Review", "comment": "Submitting my draft for peer review"},
    )
    assert sub_res.status_code == 200
    sub_detail = sub_res.json()
    assert sub_detail["submitted_by_user_id"] == "usr_marcus"
    assert sub_detail["submitted_by_name"] == "Marcus Lee"

    # Marcus attempts to approve his own submission -> 403 Forbidden (Separation of duties)
    self_app_res = client.post(
        f"/api/audits/{audit_id}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "Approved", "comment": "Trying to self-approve", "override_acknowledged": True},
    )
    assert self_app_res.status_code == 403
    assert "separation of duties" in self_app_res.json()["error"]["message"].lower()

    # Ava Chen (Brand Administrator, a different user) approves Marcus's submission -> 200 OK
    peer_app_res = client.post(
        f"/api/audits/{audit_id}/workflow",
        headers={"Authorization": f"Bearer {ava_token}"},
        json={"new_state": "Approved", "comment": "Peer reviewed and approved by Ava Chen", "override_acknowledged": True},
    )
    assert peer_app_res.status_code == 200
    approved_detail = peer_app_res.json()
    assert approved_detail["overall_status"] == "Approved"

    # Verify actor identity recorded in approvals and events
    last_approval = approved_detail["approvals"][-1]
    assert last_approval["approver_user_id"] == "usr_ava"
    assert last_approval["approver_name"] == "Ava Chen"
    assert last_approval["approver_role"] == "Brand Administrator"

    last_event = approved_detail["events"][-1]
    assert last_event["actor_user_id"] == "usr_ava"
    assert last_event["actor_name"] == "Ava Chen"


def test_production_ignores_demo_tokens_and_blocks_demo_login(monkeypatch):
    """Production mode blocks /api/demo/login with 403 and ignores Bearer demo tokens."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    ava_token = client.post("/api/demo/login", json={"user_id": "usr_ava"}).json()["token"]

    # Switch to production mode configured as Content Creator
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")
    monkeypatch.setenv("LOOMSHIELD_USER_NAME", "Production Operator")

    login_prod = client.post("/api/demo/login", json={"user_id": "usr_ava"})
    assert login_prod.status_code == 403

    # Sending Ava's Brand Administrator demo token in production is ignored; role remains Content Creator
    sess_prod = client.get("/api/session", headers={"Authorization": f"Bearer {ava_token}"})
    assert sess_prod.status_code == 200
    assert sess_prod.json()["user_role"] == "Content Creator"
    assert sess_prod.json()["user_name"] == "Production Operator"
    assert sess_prod.json()["user_id"] == ""


def test_token_takes_precedence_over_role_header_in_demo(monkeypatch):
    """When a Bearer token is sent in demo mode, role comes strictly from the verified token, never from x-loomshield-role."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    priya_token = client.post("/api/demo/login", json={"user_id": "usr_priya"}).json()["token"]

    sess = client.get(
        "/api/session",
        headers={
            "Authorization": f"Bearer {priya_token}",
            "x-loomshield-role": "Brand Administrator",
        },
    )
    assert sess.status_code == 200
    assert sess.json()["user_role"] == "Content Creator"
    assert sess.json()["user_id"] == "usr_priya"


# ============================================================================
# DAY 2 HARDENING TESTS (H1 - H8)
# ============================================================================

def test_h1_header_only_approval_blocked_when_submitter_identified(monkeypatch):
    """H1(b): When an audit has an identified submitter, header-only Reviewer approval is rejected with 403."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    marcus_token = client.post("/api/demo/login", json={"user_id": "usr_marcus"}).json()["token"]

    aud = client.post(
        "/api/audits",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={
            "brand_id": "novapay",
            "document_name": "H1 Header Approval Block",
            "content": "NovaPay Core processes enterprise cross-border payouts.",
        },
    ).json()
    aid = aud["id"]

    sub_res = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "In Review", "comment": "Submitted with Marcus token"},
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["submitted_by_user_id"] == "usr_marcus"

    # Header-only Reviewer (no Bearer token) attempts to approve -> 403
    app_res = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"x-loomshield-role": "Reviewer"},
        json={"new_state": "Approved", "comment": "Header-only approval attempt", "override_acknowledged": True},
    )
    assert app_res.status_code == 403
    assert app_res.json()["error"]["message"] == "Sign in as a demo user to approve this audit."


def test_h1_resubmit_history_blocks_original_submitter_and_header_only_resubmit(monkeypatch):
    """H1(a,c): Header-only cannot resubmit an identified audit; original submitter in approvals history cannot approve."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    marcus_token = client.post("/api/demo/login", json={"user_id": "usr_marcus"}).json()["token"]
    priya_token = client.post("/api/demo/login", json={"user_id": "usr_priya"}).json()["token"]
    ava_token = client.post("/api/demo/login", json={"user_id": "usr_ava"}).json()["token"]

    aud = client.post(
        "/api/audits",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={
            "brand_id": "novapay",
            "document_name": "H1 History SoD Check",
            "content": "NovaPay Core processes enterprise cross-border payouts.",
        },
    ).json()
    aid = aud["id"]

    # 1. Marcus submits to In Review with token
    r_sub1 = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "In Review", "comment": "Initial submit by Marcus"},
    )
    assert r_sub1.status_code == 200
    assert r_sub1.json()["submitted_by_user_id"] == "usr_marcus"

    # 2. Marcus requests changes -> Changes Requested
    r_chg = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "Changes Requested", "comment": "Needs minor revision"},
    )
    assert r_chg.status_code == 200
    assert r_chg.json()["overall_status"] == "Changes Requested"
    assert r_chg.json()["submitted_by_user_id"] == "usr_marcus"

    # 3. Header-only attempts to resubmit to In Review -> rejected (403), submitted_by_user_id preserved
    r_hdr_resub = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"x-loomshield-role": "Content Creator"},
        json={"new_state": "In Review", "comment": "Trying to wipe submitter via header-only resubmit"},
    )
    assert r_hdr_resub.status_code == 403
    assert "sign in as a demo user" in r_hdr_resub.json()["error"]["message"].lower()

    detail_after_hdr = client.get(f"/api/audits/{aid}").json()
    assert detail_after_hdr["submitted_by_user_id"] == "usr_marcus"

    # 4. Priya (Content Creator) resubmits with her token -> succeeds, current submitted_by_user_id is usr_priya
    r_priya_resub = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {priya_token}"},
        json={"new_state": "In Review", "comment": "Resubmitted by Priya"},
    )
    assert r_priya_resub.status_code == 200
    assert r_priya_resub.json()["submitted_by_user_id"] == "usr_priya"

    # 5. Marcus tries to approve with his token -> still rejected (403) because Marcus is in approvals history for In Review
    r_marcus_app = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {marcus_token}"},
        json={"new_state": "Approved", "comment": "Marcus trying to approve after Priya resubmit", "override_acknowledged": True},
    )
    assert r_marcus_app.status_code == 403
    assert "separation of duties" in r_marcus_app.json()["error"]["message"].lower()

    # 6. Ava (a different signed-in reviewer not in submitter history) approves -> 200 OK
    r_ava_app = client.post(
        f"/api/audits/{aid}/workflow",
        headers={"Authorization": f"Bearer {ava_token}"},
        json={"new_state": "Approved", "comment": "Approved by Ava", "override_acknowledged": True},
    )
    assert r_ava_app.status_code == 200
    assert r_ava_app.json()["overall_status"] == "Approved"


def test_h1_production_workflow_unchanged(monkeypatch):
    """H1(4): Production mode workflow transitions remain unchanged without demo tokens."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Brand Administrator")
    monkeypatch.setenv("LOOMSHIELD_USER_NAME", "Prod Admin")

    aud = client.post(
        "/api/audits",
        json={
            "brand_id": "novapay",
            "document_name": "Production Workflow Audit",
            "content": "NovaPay Core processes enterprise cross-border payouts.",
        },
    ).json()
    aid = aud["id"]

    r_sub = client.post(f"/api/audits/{aid}/workflow", json={"new_state": "In Review", "comment": "Prod submit"})
    assert r_sub.status_code == 200
    assert r_sub.json()["overall_status"] == "In Review"

    r_app = client.post(
        f"/api/audits/{aid}/workflow",
        json={"new_state": "Approved", "comment": "Prod approve", "override_acknowledged": True},
    )
    assert r_app.status_code == 200
    assert r_app.json()["overall_status"] == "Approved"


def test_h2_verify_invalid_envelope_reveals_no_audit_info_and_skips_db_lookup(monkeypatch):
    """H2: Invalid or malformed envelopes carrying a real audit_id trigger no DB lookup and reveal nothing about the audit."""
    env = client.post("/api/audits/AUD-1002/certificate").json()

    tampered = copy.deepcopy(env)
    tampered["payload"]["document_name"] = "Tampered Title"
    assert tampered["payload"]["audit_id"] == "AUD-1002"

    # Fail test if get_connection is called during verification of an invalid or malformed envelope
    def _forbid_db_lookup(*args, **kwargs):
        raise AssertionError("Database lookup must not be triggered for invalid or malformed certificate envelopes")

    monkeypatch.setattr(main_mod, "get_connection", _forbid_db_lookup)

    res_invalid = client.post("/api/certificates/verify", json=tampered)
    assert res_invalid.status_code == 200
    body_inv = res_invalid.json()
    assert body_inv["valid"] is False
    assert "audit_exists_on_server" not in body_inv
    assert "server_audit_status" not in body_inv
    assert "content_hash_matches_server" not in body_inv
    assert "server_content_sha256" not in body_inv

    res_malformed = client.post(
        "/api/certificates/verify",
        json={"alg": "Ed25519", "kid": env["kid"], "payload": {"audit_id": "AUD-1002"}},
    )
    assert res_malformed.status_code == 200
    body_mal = res_malformed.json()
    assert body_mal["valid"] is False
    assert "audit_exists_on_server" not in body_mal
    assert "server_audit_status" not in body_mal
    assert "content_hash_matches_server" not in body_mal
    assert "server_content_sha256" not in body_mal


def test_h2_verify_valid_certificate_returns_boolean_only_no_hashes():
    """H2: Valid certificate returns audit_exists_on_server, server_audit_status, and content_hash_matches_server boolean without hash fragments."""
    env = client.post("/api/audits/AUD-1002/certificate").json()

    res_ok = client.post("/api/certificates/verify", json=env)
    assert res_ok.status_code == 200
    data_ok = res_ok.json()
    assert data_ok["valid"] is True
    assert data_ok["audit_exists_on_server"] is True
    assert data_ok["server_audit_status"] == "Approved"
    assert data_ok["content_hash_matches_server"] is True
    assert "server_content_sha256" not in data_ok

    # Simulate server content drift on AUD-1002 and verify no hash fragment is leaked in reasons
    from backend.database import get_connection
    conn = get_connection()
    orig_row = conn.execute("SELECT current_content FROM audits WHERE id = 'AUD-1002'").fetchone()
    orig_content = orig_row["current_content"]
    try:
        conn.execute("UPDATE audits SET current_content = 'Drifted content after approval' WHERE id = 'AUD-1002'")
        conn.commit()
        conn.close()

        res_drift = client.post("/api/certificates/verify", json=env)
        assert res_drift.status_code == 200
        data_drift = res_drift.json()
        assert data_drift["valid"] is False
        assert data_drift["status"] == "content_hash_mismatch"
        assert data_drift["audit_exists_on_server"] is True
        assert data_drift["content_hash_matches_server"] is False
        assert "server_content_sha256" not in data_drift
        for reason in data_drift.get("reasons", []):
            assert env["payload"]["content_sha256"][:12] not in reason
    finally:
        conn2 = get_connection()
        conn2.execute("UPDATE audits SET current_content = ? WHERE id = 'AUD-1002'", (orig_content,))
        conn2.commit()
        conn2.close()


def test_h3_certificate_post_requires_approve_and_get_never_issues(monkeypatch):
    """H3: POST /api/audits/{id}/certificate requires approve permission (403 for Content Creator); GET returns 404 before issue and never issues."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    from backend.database import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM certificates WHERE audit_id = 'AUD-1002'")
    conn.commit()
    conn.close()

    priya_token = client.post("/api/demo/login", json={"user_id": "usr_priya"}).json()["token"]
    ava_token = client.post("/api/demo/login", json={"user_id": "usr_ava"}).json()["token"]

    # 1. Before issue, GET on Approved audit AUD-1002 returns 404 and does not issue
    get_before = client.get("/api/audits/AUD-1002/certificate")
    assert get_before.status_code == 404
    assert get_before.json()["error"]["code"] == "NOT_FOUND"

    # 2. Content Creator POST to issue certificate -> 403 Forbidden
    post_cc = client.post(
        "/api/audits/AUD-1002/certificate",
        headers={"Authorization": f"Bearer {priya_token}"},
    )
    assert post_cc.status_code == 403
    assert post_cc.json()["error"]["code"] == "PERMISSION_DENIED"

    # Confirm certificate was still not issued
    assert client.get("/api/audits/AUD-1002/certificate").status_code == 404

    # 3. Brand Administrator issues certificate via POST -> 200 OK
    post_admin = client.post(
        "/api/audits/AUD-1002/certificate",
        headers={"Authorization": f"Bearer {ava_token}"},
    )
    assert post_admin.status_code == 200

    # 4. GET after issue returns 200 and is identical to POST
    get_after = client.get("/api/audits/AUD-1002/certificate")
    assert get_after.status_code == 200
    assert get_after.json() == post_admin.json()


def test_h4_non_ascii_token_signature_returns_401_standard_error_shape(monkeypatch):
    """H4: A demo token with non-ASCII characters in the signature returns 401 in the standard error shape."""
    from backend.config import verify_demo_token
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    valid_token = client.post("/api/demo/login", json={"user_id": "usr_marcus"}).json()["token"]
    payload_part = valid_token.split(".", 1)[0]

    # Direct unit check with arbitrary Unicode characters (including multi-byte UTF-8)
    with pytest.raises(ValueError, match="Invalid or tampered"):
        verify_demo_token(f"{payload_part}.sig_é_ü_Ω_🚀")

    # End-to-end HTTP header check with non-ASCII bytes (decoded by ASGI/Starlette as non-ASCII str)
    raw_auth_header = b"Bearer " + payload_part.encode("ascii") + ".sig_\u00e9_\u00fc".encode("latin-1")

    # 1. On /api/session
    res_sess = client.get("/api/session", headers={"Authorization": raw_auth_header})
    assert res_sess.status_code == 401
    err_sess = res_sess.json()
    assert "error" in err_sess
    assert err_sess["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in err_sess["error"]

    # 2. On a protected endpoint (POST /api/audits)
    res_prot = client.post(
        "/api/audits",
        headers={"Authorization": raw_auth_header},
        json={"brand_id": "novapay", "document_name": "Non-ASCII Sig", "content": "NovaPay Core text."},
    )
    assert res_prot.status_code == 401
    err_prot = res_prot.json()
    assert "error" in err_prot
    assert err_prot["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in err_prot["error"]


def test_h6_signing_key_startup_warning_logs_without_leaking_key(monkeypatch, caplog):
    """H6: Startup check logs a warning when LOOMSHIELD_SIGNING_KEY is unset or malformed and never logs the key material."""
    import logging
    from backend.certificates import log_signing_key_startup_status

    # 1. Ephemeral key warning when unset
    monkeypatch.delenv("LOOMSHIELD_SIGNING_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="loomshield.certificates"):
        caplog.clear()
        log_signing_key_startup_status()
        assert any("ephemeral ed25519 demo signing key" in rec.message.lower() for rec in caplog.records)

    # 2. Malformed key warning without logging the secret value
    secret_malformed_value = "super-secret-malformed-key-material-987654321"
    monkeypatch.setenv("LOOMSHIELD_SIGNING_KEY", secret_malformed_value)
    with caplog.at_level(logging.WARNING, logger="loomshield.certificates"):
        caplog.clear()
        log_signing_key_startup_status()
        assert any("malformed" in rec.message.lower() for rec in caplog.records)
        for rec in caplog.records:
            assert secret_malformed_value not in rec.message


def test_h8_get_client_ip_render_proxy_anti_spoofing(monkeypatch):
    """H8 & A1: get_client_ip resolves hops[-(N+1)] with N=0/1/2, header mode, invalid values, and /api/_diag/client-ip."""
    from types import SimpleNamespace
    from backend.rate_limiter import get_client_ip

    monkeypatch.delenv("LOOMSHIELD_CLIENT_IP_HEADER", raising=False)
    monkeypatch.delenv("LOOMSHIELD_TRUST_VERCEL_HEADER", raising=False)
    monkeypatch.delenv("LOOMSHIELD_TRUST_X_REAL_IP", raising=False)
    monkeypatch.delenv("LOOMSHIELD_TRUSTED_PROXY_HOPS", raising=False)
    monkeypatch.delenv("LOOMSHIELD_DEBUG_HEADERS", raising=False)

    # 1. Default N=1 (1 trusted proxy entry on the RIGHT, e.g. "client, cloudflare-edge-ip"):
    # Forged prefix "8.8.8.8" before real client "198.51.100.42" and edge proxy "172.68.0.10" -> selects hops[-2] = 198.51.100.42
    req_one_proxy = SimpleNamespace(
        headers={
            "x-vercel-forwarded-for": "1.1.1.1",
            "x-real-ip": "9.9.9.9",
            "x-forwarded-for": "8.8.8.8, 198.51.100.42, 172.68.0.10",
        },
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_one_proxy) == "198.51.100.42"

    # Another user through the same Cloudflare edge gets their own bucket (198.51.100.99)
    req_user2 = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.99, 172.68.0.10"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_user2) == "198.51.100.99"

    # When len(hops) <= N (e.g. only 1 hop when N=1), falls back to socket address
    req_too_short = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.99"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_too_short) == "10.0.0.5"

    # 2. N=2 (two trusted proxy entries on the RIGHT: "forged, client, proxy1, proxy2") -> selects hops[-3]
    monkeypatch.setenv("LOOMSHIELD_TRUSTED_PROXY_HOPS", "2")
    req_two_proxies = SimpleNamespace(
        headers={"x-forwarded-for": "8.8.8.8, 198.51.100.77, 172.68.0.10, 10.10.0.2"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_two_proxies) == "198.51.100.77"
    # With N=2 and only 2 hops, len(hops) <= N -> falls back to socket address
    assert get_client_ip(req_user2) == "10.0.0.5"

    # 3. N=0 (zero trusted proxy entries on the RIGHT: selects hops[-1])
    monkeypatch.setenv("LOOMSHIELD_TRUSTED_PROXY_HOPS", "0")
    req_zero_proxies = SimpleNamespace(
        headers={"x-forwarded-for": "8.8.8.8, 198.51.100.42"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_zero_proxies) == "198.51.100.42"

    # 4. Invalid IP values in XFF or custom header fall back safely to socket address
    monkeypatch.setenv("LOOMSHIELD_TRUSTED_PROXY_HOPS", "1")
    req_invalid_xff = SimpleNamespace(
        headers={"x-forwarded-for": "not-an-ip, 172.68.0.10"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_invalid_xff) == "10.0.0.5"

    # 5. Header mode (LOOMSHIELD_CLIENT_IP_HEADER=cf-connecting-ip)
    monkeypatch.setenv("LOOMSHIELD_CLIENT_IP_HEADER", "cf-connecting-ip")
    req_cf = SimpleNamespace(
        headers={
            "cf-connecting-ip": "203.0.113.55",
            "x-forwarded-for": "8.8.8.8, 198.51.100.42, 172.68.0.10",
        },
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_cf) == "203.0.113.55"

    # Invalid value in LOOMSHIELD_CLIENT_IP_HEADER falls through to XFF resolution
    req_cf_invalid = SimpleNamespace(
        headers={
            "cf-connecting-ip": "malformed_ip_value",
            "x-forwarded-for": "8.8.8.8, 198.51.100.42, 172.68.0.10",
        },
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert get_client_ip(req_cf_invalid) == "198.51.100.42"
    monkeypatch.delenv("LOOMSHIELD_CLIENT_IP_HEADER", raising=False)

    # 6. Explicit flags for x-real-ip and x-vercel-forwarded-for
    monkeypatch.setenv("LOOMSHIELD_TRUST_X_REAL_IP", "1")
    assert get_client_ip(req_one_proxy) == "9.9.9.9"
    monkeypatch.delenv("LOOMSHIELD_TRUST_X_REAL_IP", raising=False)

    monkeypatch.setenv("LOOMSHIELD_TRUST_VERCEL_HEADER", "1")
    assert get_client_ip(req_one_proxy) == "1.1.1.1"
    monkeypatch.delenv("LOOMSHIELD_TRUST_VERCEL_HEADER", raising=False)

    # 7. GET /api/_diag/client-ip returns 404 unless LOOMSHIELD_DEBUG_HEADERS=1
    assert client.get("/api/_diag/client-ip").status_code == 404
    monkeypatch.setenv("LOOMSHIELD_DEBUG_HEADERS", "1")
    diag_res = client.get(
        "/api/_diag/client-ip",
        headers={
            "x-forwarded-for": "198.51.100.88, 172.68.0.10",
            "cf-connecting-ip": "198.51.100.88",
        },
    )
    assert diag_res.status_code == 200
    diag_body = diag_res.json()
    assert set(diag_body.keys()) == {
        "x-forwarded-for",
        "cf-connecting-ip",
        "true-client-ip",
        "x-real-ip",
        "socket_host",
        "computed_ip",
    }
    assert diag_body["computed_ip"] == "198.51.100.88"


def test_a4_hosted_mode_unset_env_defaults_to_content_creator(monkeypatch):
    """A4: When LOOMSHIELD_DEPLOYMENT and LOOMSHIELD_USER_ROLE are unset, configured_role() defaults to Content Creator."""
    from backend.config import configured_role
    monkeypatch.delenv("LOOMSHIELD_DEPLOYMENT", raising=False)
    monkeypatch.delenv("LOOMSHIELD_USER_ROLE", raising=False)
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")

    assert configured_role() == "Content Creator"
    sess = client.get("/api/session")
    assert sess.status_code == 200
    assert sess.json()["user_role"] == "Content Creator"
    assert sess.json()["configured_role"] == "Content Creator"



def test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility(monkeypatch):
    """H3: v2 payload with submitted_by, verification_url, revocation; tamper fails; revoke flow; v1 backward compat."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    from backend.database import reset_demo_workspace
    init_db()
    reset_demo_workspace()
    client = TestClient(main_mod.app)

    # 1. Get or issue certificate for approved audit AUD-1002
    res = client.post(
        "/api/audits/AUD-1002/certificate",
        headers={"X-Loomshield-Role": "Editorial & Brand Reviewer"},
    )
    assert res.status_code == 200, res.text
    envelope = res.json().get("certificate") or res.json()
    payload = envelope["payload"]

    # Verify v2 structure
    assert payload["certificate_version"] == 2
    assert "submitted_by" in payload
    assert payload["submitted_by"]["user_id"] != ""
    assert payload["submitted_by"]["name"] != ""
    assert payload["submitted_by"]["role"] == "Content Creator"
    assert "verification_url" in payload
    assert "revocation" in payload
    assert "status_url" in payload["revocation"]

    # Initial verification passes
    v_res = client.post("/api/certificates/verify", json={"certificate": envelope})
    assert v_res.status_code == 200
    assert v_res.json()["valid"] is True
    assert v_res.json()["status"] == "valid"

    # 2. Tampering with any field in new blocks breaks the cryptographic signature
    import copy
    tampered_sub = copy.deepcopy(envelope)
    tampered_sub["payload"]["submitted_by"]["user_id"] = "usr_forged_creator"
    v_tampered_sub = client.post("/api/certificates/verify", json={"certificate": tampered_sub}).json()
    assert v_tampered_sub["valid"] is False
    assert v_tampered_sub["status"] == "bad_signature"

    tampered_rev = copy.deepcopy(envelope)
    tampered_rev["payload"]["revocation"]["status_url"] = "http://evil.com/fake-status"
    v_tampered_rev = client.post("/api/certificates/verify", json={"certificate": tampered_rev}).json()
    assert v_tampered_rev["valid"] is False
    assert v_tampered_rev["status"] == "bad_signature"

    # 3. Revocation permissions: Content Creator is 403 Forbidden
    cert_id = payload["certificate_id"]
    rev_403 = client.post(
        f"/api/certificates/{cert_id}/revoke",
        json={"reason": "Should fail"},
        headers={"X-Loomshield-Role": "Content Creator"},
    )
    assert rev_403.status_code == 403

    # Admin without reason -> 400
    rev_400 = client.post(
        f"/api/certificates/{cert_id}/revoke",
        json={"reason": "   "},
        headers={"X-Loomshield-Role": "Brand Administrator"},
    )
    assert rev_400.status_code == 400

    # Admin revokes with reason -> 200
    rev_ok = client.post(
        f"/api/certificates/{cert_id}/revoke",
        json={"reason": "Audit superseded by corrected marketing campaign."},
        headers={"X-Loomshield-Role": "Brand Administrator"},
    )
    assert rev_ok.status_code == 200
    assert rev_ok.json()["status"] == "revoked"

    # 4. Verifying revoked certificate: reports revoked, signature remains valid
    v_after_rev = client.post("/api/certificates/verify", json={"certificate": envelope}).json()
    assert v_after_rev["status"] == "revoked"
    assert v_after_rev["is_revoked"] is True
    assert v_after_rev.get("signature_valid") is True or v_after_rev.get("valid") is True

    # 5. Public status check: returns status without content hashes
    st_res = client.get(f"/api/certificates/{cert_id}/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "revoked"
    assert st_data["is_revoked"] is True
    assert st_data["revocation_reason"] == "Audit superseded by corrected marketing campaign."
    assert "content_sha256" not in st_data
    assert "original_content_sha256" not in st_data

    # 6. v1 certificate backward compatibility: v1 envelope still verifies
    from backend.certificates import sign_certificate_payload
    v1_payload = copy.deepcopy(payload)
    v1_payload["certificate_version"] = 1
    v1_payload["certificate_id"] = "CERT-V1-COMPAT"
    del v1_payload["submitted_by"]
    del v1_payload["verification_url"]
    del v1_payload["revocation"]
    v1_envelope = sign_certificate_payload(v1_payload)

    v1_verify = client.post("/api/certificates/verify", json={"certificate": v1_envelope}).json()
    assert v1_verify["valid"] is True
    assert v1_verify["status"] == "valid"
