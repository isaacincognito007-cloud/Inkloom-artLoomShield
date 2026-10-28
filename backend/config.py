"""
Workspace configuration, signed-in identity, demo user tokens, and role permissions.

LoomShield runs as a production workspace by default. A separate, isolated sample
workspace is only available when the deployment explicitly sets
``LOOMSHIELD_WORKSPACE_MODE=demo`` (for example ``python run_loomshield.py --demo``).

In production deployments, the signed-in identity and role are taken from deployment
configuration (``LOOMSHIELD_USER_NAME`` and ``LOOMSHIELD_USER_ROLE``) and enforced on the
server; client headers and demo tokens are ignored.

In demo mode, evaluators can sign in as one of three seeded demo identities via
``POST /api/demo/login`` (which issues an 8-hour HMAC-signed Bearer token using
``LOOMSHIELD_SESSION_SECRET``) to experience separation of duties (e.g. a submitter cannot
approve their own audit). When no Bearer token is sent in demo mode, the legacy
``x-loomshield-role`` header remains supported for backwards compatibility.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("loomshield.config")

VALID_ROLES = ("Content Creator", "Reviewer", "Brand Administrator")

DEMO_SIGNIN_DISCLOSURE = (
    "Demo sign-in: anyone can choose any demo user. This shows separation of duties; it is not authentication."
)

DEMO_USERS: List[Dict[str, str]] = [
    {
        "user_id": "usr_priya",
        "name": "Priya Nair",
        "initials": "PN",
        "role": "Content Creator",
        "title": "Product Marketing Writer",
    },
    {
        "user_id": "usr_marcus",
        "name": "Marcus Lee",
        "initials": "ML",
        "role": "Reviewer",
        "title": "Editorial & Brand Reviewer",
    },
    {
        "user_id": "usr_ava",
        "name": "Ava Chen",
        "initials": "AC",
        "role": "Brand Administrator",
        "title": "Head of Brand Governance",
    },
]

DEMO_USERS_BY_ID: Dict[str, Dict[str, str]] = {u["user_id"]: u for u in DEMO_USERS}

# Process-level fallback secret when LOOMSHIELD_SESSION_SECRET is unset
_PROCESS_SESSION_SECRET: str = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

ROLE_PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "Content Creator": {
        "run_audits": True,
        "apply_corrections": True,
        "dismiss_findings": True,
        "submit_for_review": True,
        "request_changes": False,
        "approve": False,
        "approve_with_override": False,
        "edit_brand_vault": False,
        "propose_facts": True,
        "verify_facts": False,
        "manage_brands": False,
    },
    "Reviewer": {
        "run_audits": True,
        "apply_corrections": True,
        "dismiss_findings": True,
        "submit_for_review": True,
        "request_changes": True,
        "approve": True,
        "approve_with_override": True,
        "edit_brand_vault": False,
        "propose_facts": True,
        "verify_facts": False,
        "manage_brands": False,
    },
    "Brand Administrator": {
        "run_audits": True,
        "apply_corrections": True,
        "dismiss_findings": True,
        "submit_for_review": True,
        "request_changes": True,
        "approve": True,
        "approve_with_override": True,
        "edit_brand_vault": True,
        "propose_facts": True,
        "verify_facts": True,
        "manage_brands": True,
    },
}


def workspace_mode() -> str:
    raw = os.environ.get("LOOMSHIELD_WORKSPACE_MODE", "production").strip().lower()
    return "demo" if raw == "demo" else "production"


def is_demo_mode() -> bool:
    return workspace_mode() == "demo"


def deployment_mode() -> str:
    return os.environ.get("LOOMSHIELD_DEPLOYMENT", "").strip().lower()


def processing_mode() -> str:
    return "local" if deployment_mode() == "local" else "hosted"


def configured_role() -> str:
    """Return configured role. In hosted production, unconfigured defaults to least-privilege Content Creator."""
    role = os.environ.get("LOOMSHIELD_USER_ROLE", "").strip()
    if role in VALID_ROLES:
        return role

    if deployment_mode() == "local":
        return "Brand Administrator"

    logger.warning(
        "LOOMSHIELD_USER_ROLE is unset in hosted deployment; defaulting to least-privilege role: 'Content Creator'."
    )
    return "Content Creator"


def configured_user_name() -> str:
    default_name = "Sample workspace user" if is_demo_mode() else "Workspace owner"
    return os.environ.get("LOOMSHIELD_USER_NAME", default_name).strip() or default_name


def get_session_secret() -> bytes:
    raw = os.environ.get("LOOMSHIELD_SESSION_SECRET", "").strip() or _PROCESS_SESSION_SECRET
    return raw.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("ascii"))


def issue_demo_token(user_id: str, ttl_seconds: int = 8 * 3600, now_ts: Optional[int] = None) -> Dict[str, Any]:
    """Issue an HMAC-SHA256 signed demo session token (exp 8h) for a seeded demo user."""
    user = DEMO_USERS_BY_ID.get(user_id)
    if not user:
        raise ValueError(f"Unknown demo user_id '{user_id}'.")

    issued_at = int(now_ts if now_ts is not None else time.time())
    exp = issued_at + int(ttl_seconds)
    claims = {
        "user_id": user["user_id"],
        "user_name": user["name"],
        "initials": user["initials"],
        "role": user["role"],
        "iat": issued_at,
        "exp": exp,
    }
    payload_bytes = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(get_session_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    token = f"{payload_b64}.{sig_b64}"
    return {
        "token": token,
        "token_type": "Bearer",
        "user_id": user["user_id"],
        "user_name": user["name"],
        "initials": user["initials"],
        "role": user["role"],
        "exp": exp,
        "disclosure": DEMO_SIGNIN_DISCLOSURE,
    }


def verify_demo_token(token: str, now_ts: Optional[float] = None) -> Dict[str, Any]:
    """Verify an HMAC-signed demo token. Raises ValueError if malformed, tampered, forged, or expired."""
    if not token or not isinstance(token, str) or "." not in token:
        raise ValueError("Malformed demo session token.")

    parts = token.strip().split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Malformed demo session token structure.")

    payload_b64, sig_b64 = parts
    try:
        payload_ascii_bytes = payload_b64.encode("ascii")
        sig_input_bytes = sig_b64.encode("ascii")
        expected_sig = hmac.new(get_session_secret(), payload_ascii_bytes, hashlib.sha256).digest()
        expected_sig_b64_bytes = _b64url_encode(expected_sig).encode("ascii")
        sig_matches = hmac.compare_digest(expected_sig_b64_bytes, sig_input_bytes)
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Invalid or tampered demo session token signature.") from exc

    if not sig_matches:
        raise ValueError("Invalid or tampered demo session token signature.")

    try:
        raw_bytes = _b64url_decode(payload_b64)
        claims = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Malformed demo session token payload.") from exc

    if not isinstance(claims, dict):
        raise ValueError("Malformed demo session token claims.")

    user_id = claims.get("user_id")
    role = claims.get("role")
    exp = claims.get("exp")

    if not isinstance(user_id, str) or user_id not in DEMO_USERS_BY_ID:
        raise ValueError("Unknown demo user identity in token.")

    canonical_user = DEMO_USERS_BY_ID[user_id]
    if role != canonical_user["role"] or role not in VALID_ROLES:
        raise ValueError("Demo token role mismatch.")

    if not isinstance(exp, (int, float)):
        raise ValueError("Demo session token missing expiration ('exp').")

    current_time = float(now_ts if now_ts is not None else time.time())
    if float(exp) <= current_time:
        raise ValueError("Demo session token has expired.")

    return {
        "user_id": canonical_user["user_id"],
        "user_name": canonical_user["name"],
        "initials": canonical_user["initials"],
        "role": canonical_user["role"],
        "exp": int(exp),
    }


def resolve_actor(
    authorization: Optional[str] = None,
    requested_role: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve the active actor (user_id, user_name, initials, role, source) for a request.

    - Production mode: always uses deployment configuration; ignores tokens and role headers.
    - Demo mode with Authorization header: verifies Bearer token (raises ValueError on invalid/expired token)
      and takes role and identity strictly from the verified token (never from x-loomshield-role).
    - Demo mode without Authorization header: honours legacy x-loomshield-role preview if valid.
    """
    if not is_demo_mode():
        role = configured_role()
        name = configured_user_name()
        return {
            "user_id": "",
            "user_name": name,
            "initials": "".join(p[0].upper() for p in name.split()[:2]) or "WO",
            "role": role,
            "source": "deployment_configuration",
        }

    if authorization is not None and str(authorization).strip() != "":
        auth_str = str(authorization).strip()
        if not auth_str.lower().startswith("bearer "):
            raise ValueError("Authorization header must use Bearer token scheme.")
        raw_token = auth_str[7:].strip()
        verified = verify_demo_token(raw_token)
        return {
            "user_id": verified["user_id"],
            "user_name": verified["user_name"],
            "initials": verified["initials"],
            "role": verified["role"],
            "source": "demo_token",
        }

    role = str(requested_role) if requested_role in VALID_ROLES else configured_role()
    name = configured_user_name()
    return {
        "user_id": "",
        "user_name": name,
        "initials": "".join(p[0].upper() for p in name.split()[:2]) or "SW",
        "role": role,
        "source": "demo_role_preview" if requested_role in VALID_ROLES else "deployment_configuration",
    }


def resolve_role(requested_role: Optional[str] = None) -> str:
    """Return the role the server will actually enforce when no Bearer token is present."""
    if is_demo_mode() and requested_role in VALID_ROLES:
        return str(requested_role)
    return configured_role()


def has_permission(role: str, permission: str) -> bool:
    return bool(ROLE_PERMISSIONS.get(role, {}).get(permission, False))


def actor_label(role: str) -> str:
    return f"{configured_user_name()} ({role})"


def session_payload(
    requested_role: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Dict[str, Any]:
    actor = resolve_actor(authorization=authorization, requested_role=requested_role)
    role = actor["role"]
    name = actor["user_name"]
    return {
        "workspace_mode": workspace_mode(),
        "is_demo": is_demo_mode(),
        "is_demo_mode": is_demo_mode(),
        "deployment_mode": deployment_mode() or "hosted",
        "processing_mode": processing_mode(),
        "user_id": actor["user_id"],
        "user_name": name,
        "user_initials": actor["initials"],
        "user_role": role,
        "user": {
            "user_id": actor["user_id"],
            "name": name,
            "initials": actor["initials"],
            "role": role,
        },
        "configured_role": configured_role(),
        "role_source": actor["source"],
        "role_preview_enabled": is_demo_mode(),
        "available_roles": list(VALID_ROLES),
        "demo_users": list(DEMO_USERS) if is_demo_mode() else [],
        "demo_signin_disclosure": DEMO_SIGNIN_DISCLOSURE if is_demo_mode() else "",
        "permissions": dict(ROLE_PERMISSIONS[role]),
        "role_permissions": {r: dict(p) for r, p in ROLE_PERMISSIONS.items()},
    }
