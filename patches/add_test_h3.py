with open("tests/test_certificates_and_identities.py", "r", encoding="utf-8") as f:
    text = f.read()

new_h3_test = '''

def test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility(monkeypatch):
    """H3: v2 payload with submitted_by, verification_url, revocation; tamper fails; revoke flow; v1 backward compat."""
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    init_db()
    reset_demo_workspace()
    client = TestClient(app)

    # 1. Get or issue certificate for approved audit AUD-1002
    res = client.post(
        "/api/audits/AUD-1002/certificate",
        headers={"X-Loomshield-Role": "Editorial & Brand Reviewer"},
    )
    assert res.status_code == 200, res.text
    envelope = res.json()["certificate"]
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
    del v1_payload["submitted_by"]
    del v1_payload["verification_url"]
    del v1_payload["revocation"]
    v1_envelope = sign_certificate_payload(v1_payload)

    v1_verify = client.post("/api/certificates/verify", json={"certificate": v1_envelope}).json()
    assert v1_verify["valid"] is True
    assert v1_verify["status"] == "valid"
'''

assert "def test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility" not in text
text = text + new_h3_test

with open("tests/test_certificates_and_identities.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Added test_h3 to tests/test_certificates_and_identities.py successfully")
