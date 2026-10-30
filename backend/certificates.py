"""
Ed25519 Signed Compliance Certificates for LoomShield (Round 3 — Part B).

Provides:
- Deterministic canonical JSON serialization (sorted keys, UTF-8, no whitespace, certificate_version=1)
- Key management via LOOMSHIELD_SIGNING_KEY (base64 32-byte Ed25519 seed) with automatic
  ephemeral fallback at startup when unset (never logs private keys or seeds)
- Key ID (kid) = first 16 hex characters of SHA-256(raw 32-byte public key)
- Certificate issuance (idempotent per Approved audit) and cryptographic verification
"""

import base64
import hashlib
import json
import logging
import os

logger = logging.getLogger("loomshield.certificates")
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

CERTIFICATE_VERSION = 2
ENGINE_VERSION = "2.1.0"
EPHEMERAL_KEY_NOTICE = "ephemeral demo key: valid only until the server restarts"
PERSISTENT_KEY_NOTICE = "configured persistent signing key"
CERTIFICATE_LIMITATIONS = (
    "Certifies that this review process was completed against the stated guideline version "
    "and content hash; not legal advice; not a guarantee of regulatory compliance."
)

# Process-lifetime ephemeral 32-byte seed used when LOOMSHIELD_SIGNING_KEY is unset
_PROCESS_EPHEMERAL_SEED: bytes = os.urandom(32)


def compute_kid_from_public_bytes(pub_bytes: bytes) -> str:
    """Return the first 16 hex characters of SHA-256(public_key_raw_bytes)."""
    return hashlib.sha256(pub_bytes).hexdigest()[:16]


def get_signing_key() -> Tuple[Ed25519PrivateKey, bytes, str, bool]:
    """Return (private_key, public_key_raw_bytes, kid, is_ephemeral). Never logs keys."""
    env_seed_b64 = os.environ.get("LOOMSHIELD_SIGNING_KEY", "").strip()
    is_ephemeral = True
    seed_bytes = _PROCESS_EPHEMERAL_SEED

    if env_seed_b64:
        try:
            decoded = base64.b64decode(env_seed_b64, validate=True)
            if len(decoded) == 32:
                seed_bytes = decoded
                is_ephemeral = False
            else:
                logger.warning(
                    "LOOMSHIELD_SIGNING_KEY is malformed (decoded seed must be 32 bytes, got %d); "
                    "falling back to ephemeral Ed25519 demo signing key.",
                    len(decoded),
                )
        except Exception:
            logger.warning(
                "LOOMSHIELD_SIGNING_KEY is malformed (invalid base64 encoding); "
                "falling back to ephemeral Ed25519 demo signing key."
            )
            is_ephemeral = True
            seed_bytes = _PROCESS_EPHEMERAL_SEED

    priv = Ed25519PrivateKey.from_private_bytes(seed_bytes)
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    kid = compute_kid_from_public_bytes(pub_bytes)
    return priv, pub_bytes, kid, is_ephemeral


def log_signing_key_startup_status() -> None:
    """Log a startup warning (never logging any key material) if an ephemeral or malformed key is active."""
    env_seed_b64 = os.environ.get("LOOMSHIELD_SIGNING_KEY", "").strip()
    _, _, kid, is_ephemeral = get_signing_key()
    if not env_seed_b64:
        logger.warning(
            "LOOMSHIELD_SIGNING_KEY is unset; using ephemeral Ed25519 demo signing key (kid=%s). "
            "Certificates will only verify until the server restarts.",
            kid,
        )
    elif is_ephemeral:
        logger.warning(
            "LOOMSHIELD_SIGNING_KEY is malformed; using ephemeral Ed25519 demo signing key (kid=%s).",
            kid,
        )


def get_public_key_metadata() -> Dict[str, Any]:
    """Return public key metadata for GET /api/certificates/public-key."""
    _, pub_bytes, kid, is_ephemeral = get_signing_key()
    return {
        "alg": "Ed25519",
        "kid": kid,
        "public_key_b64": base64.b64encode(pub_bytes).decode("ascii"),
        "ephemeral_key": is_ephemeral,
        "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
    }


def canonicalize_payload(payload: Dict[str, Any]) -> bytes:
    """Serialize certificate payload to canonical JSON bytes (sorted keys, UTF-8, no whitespace)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_certificate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sign a canonicalized certificate payload and return the full certificate envelope."""
    priv, _, kid, is_ephemeral = get_signing_key()
    canonical_bytes = canonicalize_payload(payload)
    sig_bytes = priv.sign(canonical_bytes)
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")
    return {
        "payload": payload,
        "alg": "Ed25519",
        "kid": kid,
        "signature_b64": sig_b64,
        "ephemeral_key": is_ephemeral,
        "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
    }


def build_certificate_payload(
    *,
    certificate_id: str,
    issued_at: str,
    audit: Dict[str, Any],
    brand_name: str,
    approval_row: Dict[str, Any],
    processing_mode_str: str,
    is_ephemeral: bool,
) -> Dict[str, Any]:
    """Construct the canonical v1 compliance certificate payload for an Approved audit."""
    current_content = str(audit.get("current_content") or "")
    original_content = str(audit.get("original_content") or "")
    content_sha256 = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
    original_content_sha256 = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

    approval_hash = str(approval_row.get("content_sha256") or "")
    if approval_hash and approval_hash != content_sha256:
        raise ValueError(
            f"Audit content hash ({content_sha256}) does not match approval record content_sha256 ({approval_hash})."
        )

    findings = audit.get("findings") or []
    summary = {
        "total": len(findings),
        "accepted": sum(1 for f in findings if f.get("review_state") == "accepted"),
        "modified": sum(1 for f in findings if f.get("review_state") == "modified"),
        "dismissed": sum(1 for f in findings if f.get("review_state") == "dismissed"),
        "open": sum(1 for f in findings if f.get("review_state") in ("open", "needs_review")),
    }

    dismissals = [
        {
            "finding_id": str(f["id"]),
            "reason": str(f.get("decision_note") or ""),
        }
        for f in sorted(findings, key=lambda x: str(x.get("id") or ""))
        if f.get("review_state") == "dismissed"
    ]

    approver_name = (
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
    }


def verify_certificate_envelope(
    envelope: Any,
    *,
    public_key_b64: Optional[str] = None,
    expected_kid: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify an Ed25519 certificate envelope and return structured verification result with plain-language reasons."""
    _, server_pub_bytes, server_kid, is_ephemeral = get_signing_key()
    reasons: List[str] = []

    if not isinstance(envelope, dict):
        return {
            "valid": False,
            "status": "invalid",
            "reasons": ["Malformed certificate: top-level JSON value must be an object."],
            "ephemeral_key": is_ephemeral,
            "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        }

    payload = envelope.get("payload")
    alg = envelope.get("alg")
    kid = envelope.get("kid")
    sig_b64 = envelope.get("signature_b64")

    if not isinstance(payload, dict):
        reasons.append("Malformed certificate: missing or invalid 'payload' object.")
    if alg != "Ed25519":
        reasons.append(f"Malformed certificate: unsupported signature algorithm '{alg}' (expected 'Ed25519').")
    if not isinstance(kid, str) or not kid.strip():
        reasons.append("Malformed certificate: missing key ID ('kid').")
    if not isinstance(sig_b64, str) or not sig_b64.strip():
        reasons.append("Malformed certificate: missing base64 signature ('signature_b64').")

    required_payload_fields_v1 = (
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
                    reasons.append("Malformed certificate payload: 'verification_url' must be a valid URL string.")

    if reasons:
        return {
            "valid": False,
            "status": "malformed",
            "reasons": reasons,
            "kid": kid if isinstance(kid, str) else None,
            "ephemeral_key": is_ephemeral,
            "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        }

    # Resolve public key bytes to verify against
    pub_bytes_to_use = server_pub_bytes
    active_kid = expected_kid or server_kid

    if public_key_b64:
        try:
            decoded_pub = base64.b64decode(public_key_b64.strip(), validate=True)
            if len(decoded_pub) != 32:
                return {
                    "valid": False,
                    "status": "malformed",
                    "reasons": ["Malformed public key: Ed25519 public key must be 32 raw bytes in base64."],
                    "kid": kid,
                    "ephemeral_key": is_ephemeral,
                    "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
                }
            pub_bytes_to_use = decoded_pub
            active_kid = compute_kid_from_public_bytes(decoded_pub)
        except Exception:
            return {
                "valid": False,
                "status": "malformed",
                "reasons": ["Malformed public key: could not decode base64 public key."],
                "kid": kid,
                "ephemeral_key": is_ephemeral,
                "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
            }

    if kid != active_kid:
        reasons.append(
            f"Unknown key ID (kid '{kid}' does not match verification key '{active_kid}'). "
            "The certificate was signed by a different key or an ephemeral key from a previous server run."
        )
        return {
            "valid": False,
            "status": "unknown_kid",
            "reasons": reasons,
            "kid": kid,
            "expected_kid": active_kid,
            "ephemeral_key": is_ephemeral,
            "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        }

    try:
        sig_bytes = base64.b64decode(sig_b64.strip(), validate=True)
        if len(sig_bytes) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")
    except Exception:
        return {
            "valid": False,
            "status": "malformed",
            "reasons": ["Malformed certificate: 'signature_b64' is not a valid 64-byte base64 Ed25519 signature."],
            "kid": kid,
            "ephemeral_key": is_ephemeral,
            "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        }

    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes_to_use)
    canonical_bytes = canonicalize_payload(payload)
    try:
        pub_key.verify(sig_bytes, canonical_bytes)
    except InvalidSignature:
        return {
            "valid": False,
            "status": "bad_signature",
            "reasons": [
                "Bad signature: the Ed25519 signature does not match the canonical payload bytes. "
                "The certificate content was modified after signing or signed with a different key."
            ],
            "kid": kid,
            "ephemeral_key": is_ephemeral,
            "key_notice": EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE,
        }

    return {
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
    }
