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
    assert payload["certificate_version"] == 1
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
