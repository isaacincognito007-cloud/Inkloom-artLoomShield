"""
Workspace configuration, signed-in identity and role permissions.

LoomShield runs as a production workspace by default. A separate, isolated sample
workspace is only available when the deployment explicitly sets
``LOOMSHIELD_WORKSPACE_MODE=demo`` (for example ``python run_loomshield.py --demo``).

There is no interactive login in this local build. The signed-in identity and role are
therefore taken from deployment configuration (``LOOMSHIELD_USER_NAME`` and
``LOOMSHIELD_USER_ROLE``) and enforced on the server. Client-supplied roles are ignored in
production; they are only honoured inside the clearly labelled demo workspace so that
evaluators can preview how each role behaves.
"""

import os
from typing import Any, Dict, Optional

VALID_ROLES = ("Content Creator", "Reviewer", "Brand Administrator")

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


def configured_role() -> str:
    role = os.environ.get("LOOMSHIELD_USER_ROLE", "Brand Administrator").strip()
    return role if role in VALID_ROLES else "Brand Administrator"


def configured_user_name() -> str:
    default_name = "Sample workspace user" if is_demo_mode() else "Workspace owner"
    return os.environ.get("LOOMSHIELD_USER_NAME", default_name).strip() or default_name


def resolve_role(requested_role: Optional[str] = None) -> str:
    """Return the role the server will actually enforce for this request.

    Production: always the configured role (client-supplied roles are ignored).
    Demo workspace: a valid requested role is honoured as an explicit role preview.
    """
    if is_demo_mode() and requested_role in VALID_ROLES:
        return str(requested_role)
    return configured_role()


def has_permission(role: str, permission: str) -> bool:
    return bool(ROLE_PERMISSIONS.get(role, {}).get(permission, False))


def actor_label(role: str) -> str:
    return f"{configured_user_name()} ({role})"


def session_payload(requested_role: Optional[str] = None) -> Dict[str, Any]:
    role = resolve_role(requested_role)
    name = configured_user_name()
    return {
        "workspace_mode": workspace_mode(),
        "is_demo": is_demo_mode(),
        "is_demo_mode": is_demo_mode(),
        "user_name": name,
        "user_role": role,
        "user": {"name": name, "role": role},
        "configured_role": configured_role(),
        "role_source": "demo_role_preview" if (is_demo_mode() and requested_role in VALID_ROLES) else "deployment_configuration",
        "role_preview_enabled": is_demo_mode(),
        "available_roles": list(VALID_ROLES),
        "permissions": dict(ROLE_PERMISSIONS[role]),
        "role_permissions": {r: dict(p) for r, p in ROLE_PERMISSIONS.items()},
    }
