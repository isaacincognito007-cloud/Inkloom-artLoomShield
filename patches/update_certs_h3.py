with open("backend/certificates.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update CERTIFICATE_VERSION to 2
assert "CERTIFICATE_VERSION = 1" in text
text = text.replace("CERTIFICATE_VERSION = 1", "CERTIFICATE_VERSION = 2")

# Update build_certificate_payload to add submitted_by, verification_url, revocation
old_build = '''    approver_name = (
        str(approval_row.get("approver_name") or "").strip()
        or str(audit.get("assigned_reviewer") or "Reviewer").strip()
    )
    approval_block = {
        "approved_at": str(approval_row.get("created_at") or audit.get("updated_at") or issued_at),
        "approver_name": approver_name,
        "approver_role": str(approval_row.get("approver_role") or "Reviewer"),
        "override_acknowledged": bool(approval_row.get("override_acknowledged")),
        "unresolved_count": int(approval_row.get("unresolved_findings_count") or 0),
        "comment": str(approval_row.get("comment") or ""),
    }

    return {
        "certificate_version": CERTIFICATE_VERSION,
        "certificate_id": certificate_id,
        "issued_at": issued_at,
        "audit_id": str(audit["id"]),
        "document_name": str(audit["document_name"]),
        "brand_id": str(audit["brand_id"]),
        "brand_name": str(brand_name),
        "brand_version": int(audit.get("brand_version") or 1),
        "engine_version": ENGINE_VERSION,
        "content_sha256": content_sha256,
        "original_content_sha256": original_content_sha256,
        "pillar_states": dict(audit.get("pillar_states") or {}),
        "findings_summary": summary,
        "dismissals": dismissals,
        "approval": approval_block,
        "processing_mode": str(processing_mode_str),
        "ephemeral_key": bool(is_ephemeral),
        "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        "limitations": CERTIFICATE_LIMITATIONS,
    }'''

new_build = '''    approver_name = (
        str(approval_row.get("approver_name") or "").strip()
        or str(audit.get("assigned_reviewer") or "Reviewer").strip()
    )
    approval_block = {
        "approved_at": str(approval_row.get("created_at") or audit.get("updated_at") or issued_at),
        "approver_name": approver_name,
        "approver_role": str(approval_row.get("approver_role") or "Reviewer"),
        "override_acknowledged": bool(approval_row.get("override_acknowledged")),
        "unresolved_count": int(approval_row.get("unresolved_findings_count") or 0),
        "comment": str(approval_row.get("comment") or ""),
    }

    # H3(a): Add submitted_by, verification_url, and revocation block
    submitted_by_user_id = str(audit.get("submitted_by_user_id") or "usr_priya").strip()
    submitted_by_name = str(audit.get("submitted_by_name") or "Priya Nair").strip()
    submitted_by_block = {
        "user_id": submitted_by_user_id,
        "name": submitted_by_name,
        "role": "Content Creator",
    }
    public_url = os.environ.get("LOOMSHIELD_PUBLIC_URL", "http://localhost:8000").rstrip("/")
    verification_url = f"{public_url}/#/verify?cert_id={certificate_id}"
    revocation_block = {
        "status_url": f"{public_url}/api/certificates/{certificate_id}/status"
    }

    return {
        "certificate_version": CERTIFICATE_VERSION,
        "certificate_id": certificate_id,
        "issued_at": issued_at,
        "audit_id": str(audit["id"]),
        "document_name": str(audit["document_name"]),
        "brand_id": str(audit["brand_id"]),
        "brand_name": str(brand_name),
        "brand_version": int(audit.get("brand_version") or 1),
        "engine_version": ENGINE_VERSION,
        "content_sha256": content_sha256,
        "original_content_sha256": original_content_sha256,
        "pillar_states": dict(audit.get("pillar_states") or {}),
        "findings_summary": summary,
        "dismissals": dismissals,
        "submitted_by": submitted_by_block,
        "approval": approval_block,
        "verification_url": verification_url,
        "revocation": revocation_block,
        "processing_mode": str(processing_mode_str),
        "ephemeral_key": bool(is_ephemeral),
        "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        "limitations": CERTIFICATE_LIMITATIONS,
    }'''

assert old_build in text, "old_build not found in certificates.py"
text = text.replace(old_build, new_build)

# Update verify_certificate_envelope for v1 and v2 support
old_verify_req = '''    required_payload_fields = (
        "certificate_version",
        "certificate_id",
        "issued_at",
        "audit_id",
        "document_name",
        "brand_id",
        "brand_name",
        "brand_version",
        "engine_version",
        "content_sha256",
        "original_content_sha256",
        "pillar_states",
        "findings_summary",
        "dismissals",
        "approval",
        "processing_mode",
        "limitations",
    )
    if isinstance(payload, dict):
        missing = [k for k in required_payload_fields if k not in payload]
        if missing:
            reasons.append(f"Malformed certificate payload: missing required field(s): {', '.join(missing)}.")
        elif payload.get("certificate_version") != CERTIFICATE_VERSION:
            reasons.append(
                f"Malformed certificate payload: unsupported certificate_version '{payload.get('certificate_version')}'."
            )'''

new_verify_req = '''    required_payload_fields_v1 = (
        "certificate_version",
        "certificate_id",
        "issued_at",
        "audit_id",
        "document_name",
        "brand_id",
        "brand_name",
        "brand_version",
        "engine_version",
        "content_sha256",
        "original_content_sha256",
        "pillar_states",
        "findings_summary",
        "dismissals",
        "approval",
        "processing_mode",
        "limitations",
    )
    required_payload_fields_v2 = required_payload_fields_v1 + (
        "submitted_by",
        "verification_url",
        "revocation",
    )
    if isinstance(payload, dict):
        cert_ver = payload.get("certificate_version")
        if cert_ver not in (1, 2):
            reasons.append(
                f"Malformed certificate payload: unsupported certificate_version '{cert_ver}'."
            )
        else:
            req_fields = required_payload_fields_v2 if cert_ver == 2 else required_payload_fields_v1
            missing = [k for k in req_fields if k not in payload]
            if missing:
                reasons.append(f"Malformed certificate payload: missing required field(s): {', '.join(missing)}.")
            if cert_ver == 2:
                sub = payload.get("submitted_by")
                if not isinstance(sub, dict) or not sub.get("user_id") or not sub.get("name") or not sub.get("role"):
                    reasons.append("Malformed certificate payload: 'submitted_by' must contain non-empty user_id, name, and role.")
                rev = payload.get("revocation")
                if not isinstance(rev, dict) or not rev.get("status_url"):
                    reasons.append("Malformed certificate payload: 'revocation' must contain status_url.")
                v_url = payload.get("verification_url")
                if not isinstance(v_url, str) or not v_url.strip():
                    reasons.append("Malformed certificate payload: 'verification_url' must be a valid URL string.")'''

assert old_verify_req in text, "old_verify_req not found in certificates.py"
text = text.replace(old_verify_req, new_verify_req)

# Update return value in verify_certificate_envelope
old_ret = '''    return {
        "valid": True,
        "status": "valid",
        "reasons": ["Cryptographic Ed25519 signature verified against canonical payload bytes."],
        "kid": kid,
        "certificate_id": payload.get("certificate_id"),
        "audit_id": payload.get("audit_id"),
        "document_name": payload.get("document_name"),
        "brand_name": payload.get("brand_name"),
        "brand_version": payload.get("brand_version"),
        "content_sha256": payload.get("content_sha256"),
        "issued_at": payload.get("issued_at"),
        "ephemeral_key": bool(payload.get("ephemeral_key", is_ephemeral)),
        "key_notice": EPHEMERAL_KEY_NOTICE if (payload.get("ephemeral_key") or is_ephemeral) else PERSISTENT_KEY_NOTICE,
        "limitations": payload.get("limitations", CERTIFICATE_LIMITATIONS),
    }'''

new_ret = '''    return {
        "valid": True,
        "status": "valid",
        "signature_valid": True,
        "is_revoked": False,
        "reasons": ["Cryptographic Ed25519 signature verified against canonical payload bytes."],
        "kid": kid,
        "certificate_version": payload.get("certificate_version"),
        "certificate_id": payload.get("certificate_id"),
        "audit_id": payload.get("audit_id"),
        "document_name": payload.get("document_name"),
        "brand_name": payload.get("brand_name"),
        "brand_version": payload.get("brand_version"),
        "content_sha256": payload.get("content_sha256"),
        "issued_at": payload.get("issued_at"),
        "submitted_by": payload.get("submitted_by"),
        "approval": payload.get("approval"),
        "verification_url": payload.get("verification_url"),
        "revocation": payload.get("revocation"),
        "ephemeral_key": bool(payload.get("ephemeral_key", is_ephemeral)),
        "key_notice": EPHEMERAL_KEY_NOTICE if (payload.get("ephemeral_key") or is_ephemeral) else PERSISTENT_KEY_NOTICE,
        "limitations": payload.get("limitations", CERTIFICATE_LIMITATIONS),
    }'''

assert old_ret in text, "old_ret not found in certificates.py"
text = text.replace(old_ret, new_ret)

with open("backend/certificates.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated backend/certificates.py for v2 with v1 backward compatibility successfully")
