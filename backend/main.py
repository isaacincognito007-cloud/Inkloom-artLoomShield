from contextlib import asynccontextmanager
import base64
import hashlib
import json
import logging
import os
import platform
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .certificates import (
    EPHEMERAL_KEY_NOTICE,
    PERSISTENT_KEY_NOTICE,
    build_certificate_payload,
    canonicalize_payload,
    get_public_key_metadata,
    get_signing_key,
    log_signing_key_startup_status,
    sign_certificate_payload,
    verify_certificate_envelope,
)
from .config import (
    DEMO_SIGNIN_DISCLOSURE,
    DEMO_USERS,
    actor_label,
    configured_user_name,
    has_permission,
    is_demo_mode,
    issue_demo_token,
    processing_mode,
    resolve_actor,
    resolve_role,
    session_payload,
)
from .database import (
    allocate_audit_id,
    allocate_certificate_id,
    allocate_guideline_revision_id,
    allocate_color_id,
    allocate_fact_id,
    allocate_rule_id,
    allocate_term_id,
    bump_brand_version,
    db_session,
    get_connection,
    get_db_path,
    init_db,
    record_audit_event,
    reset_demo_workspace,
)
from .engine import (
    ImageTooLargeError,
    get_engine_status,
    inspect_raster_image,
    is_valid_hex,
    parse_uploaded_file,
    probe_and_decode_raster_image,
    run_engine_selftest,
    run_six_pillar_audit,
)
from .clarity_rewriter import (
    correlate_ambiguity_and_overrides,
    extract_numeric_tokens,
    generate_candidate_rewrite,
    load_vague_lexicon,
    score_rule_ambiguity,
)
from .heatmap import inspect_visual_heatmap, sanitize_svg_markup
from .rate_limiter import SimpleIpRateLimiter, get_client_ip
from .wizard import (
    WIZARD_OPTIONS,
    WizardAnswers,
    check_pattern_structural_safety,
    compose,
    create_wizard_profile_in_db,
    get_sample_text_for_answers,
    get_wizard_unavailable_reason,
    is_wizard_available,
)

logger = logging.getLogger("loomshield.api")
audit_rate_limiter = SimpleIpRateLimiter(max_requests=30, window_seconds=60)
verify_rate_limiter = SimpleIpRateLimiter(max_requests=30, window_seconds=60)

_LAST_SELFTEST_RESULT: Optional[Dict[str, Any]] = None
_LAST_SELFTEST_TIME: Optional[str] = None


def current_actor(
    authorization: Optional[str] = Header(None),
    x_loomshield_role: Optional[str] = Header(None),
) -> Dict[str, str]:
    """Resolve verified actor identity and role for this request."""
    try:
        return resolve_actor(authorization=authorization, requested_role=x_loomshield_role)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def current_role(actor: Dict[str, str] = Depends(current_actor)) -> str:
    """Role enforced for this request (deployment-configured; demo workspace uses verified token or role preview)."""
    return actor["role"]


def require_permission(role: str, permission: str, message: str) -> None:
    if not has_permission(role, permission):
        raise HTTPException(status_code=403, detail=f"{message} (signed-in role: {role}).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _LAST_SELFTEST_RESULT, _LAST_SELFTEST_TIME
    init_db()
    log_signing_key_startup_status()
    try:
        _LAST_SELFTEST_RESULT = run_engine_selftest()
        _LAST_SELFTEST_TIME = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.warning("Startup engine selftest encountered issue: %s", exc)
    yield


def get_app_description() -> str:
    mode = processing_mode()
    if mode == "local":
        return "Brand Governance Platform with Two Local Verification Engines (Deterministic Rules & Local NLP on-device)"
    return "Brand Governance Platform with Two Hosted Verification Engines (Deterministic Rules & Embedded NLP, Zero 3rd-Party AI APIs)"


app = FastAPI(
    title="LoomShield Brand Governance Workspace API",
    description=get_app_description(),
    version="2.1.0",
    lifespan=lifespan,
)

DEFAULT_CORS_ORIGINS = (
    "https://inkloom-artloomshield-frontend.vercel.app,"
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "http://localhost:8000,"
    "http://127.0.0.1:8000"
)


def parse_cors_origins(env_val: Optional[str] = None) -> list[str]:
    raw = env_val if env_val is not None else os.environ.get("LOOMSHIELD_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    raw = raw.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


allow_origins = parse_cors_origins()
allow_credentials = allow_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# F2: multipart form fields are parsed (and spooled) by Starlette before the route handler runs, so the
# in-handler chunked read alone cannot stop a large body from being received. Reject declared oversize
# bodies on the upload route up-front from Content-Length. MULTIPART_OVERHEAD_ALLOWANCE covers the form
# fields and multipart boundaries around a file of at most 5 MB.
# G6(a): upload_size_guard_middleware applies strictly to upload routes and never rejects
# a file of 5 MB minus 1 KB because of multipart header/boundary overhead.
UPLOAD_ROUTE_PATHS = ("/api/audits/upload",)
MULTIPART_OVERHEAD_ALLOWANCE = 256 * 1024


@app.middleware("http")
async def upload_size_guard_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path.rstrip("/") in UPLOAD_ROUTE_PATHS:
        declared = request.headers.get("content-length", "").strip()
        if declared.isdigit() and int(declared) > (5 * 1024 * 1024) + MULTIPART_OVERHEAD_ALLOWANCE:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "BAD_REQUEST", "message": "File size exceeds the 5 MB safety limit."}, "detail": "File size exceeds the 5 MB safety limit."},
            )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    raw_id = request.headers.get("x-request-id", "").strip()
    if raw_id and re.match(r"^[a-zA-Z0-9_\-]{1,64}$", raw_id):
        req_id = raw_id
    else:
        req_id = f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["x-request-id"] = req_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", "req-unknown")
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "REQUEST_ENTITY_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    err_code = code_map.get(exc.status_code, "HTTP_ERROR")
    msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": err_code,
                "message": msg,
                "request_id": req_id,
            },
            "detail": exc.detail,
        },
        headers={"x-request-id": req_id},
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", "req-unknown")
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "REQUEST_ENTITY_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    err_code = code_map.get(exc.status_code, "HTTP_ERROR")
    msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": err_code,
                "message": msg,
                "request_id": req_id,
            },
            "detail": msg,
        },
        headers={"x-request-id": req_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", "req-unknown")
    errors = exc.errors()
    first_err = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first_err.get("loc", []))
    msg = first_err.get("msg", "Validation error")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"Validation error at '{field}': {msg}",
                "field": field,
                "request_id": req_id,
            },
            "detail": errors,
        },
        headers={"x-request-id": req_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "req-unknown")
    # Log request_id and exception class/message; never log document content
    logger.error("Internal server error [req_id=%s]: %s: %s", req_id, exc.__class__.__name__, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "request_id": req_id,
            },
            "detail": "An internal server error occurred.",
        },
        headers={"x-request-id": req_id},
    )


# ============================================================================
# PYDANTIC VALIDATION SCHEMAS
# ============================================================================

class BrandVoiceUpdate(BaseModel):
    description: str = Field(..., min_length=5)
    tone_principles: str = Field(..., min_length=5)
    writing_style: str = Field(..., min_length=5)
    messaging_principles: str = Field(..., min_length=5)
    do_examples: List[str] = Field(default_factory=list)
    dont_examples: List[str] = Field(default_factory=list)


class VisualSpecsUpdate(BaseModel):
    typography_specs: str
    spacing_rules: str
    logo_placement_constraints: str


class AccessibilitySpecsUpdate(BaseModel):
    min_contrast_normal: float = Field(4.5, ge=1.0, le=21.0)
    min_contrast_large: float = Field(3.0, ge=1.0, le=21.0)
    require_alt_text: bool = True
    enforce_heading_order: bool = True
    target_reading_ease: float = Field(50.0, ge=0.0, le=100.0)


class TerminologyCreate(BaseModel):
    preferred_term: str = Field(..., min_length=1)
    prohibited_term: str = Field(..., min_length=1)
    replacement_term: str = Field(..., min_length=1)
    case_sensitive: bool = False
    notes: str = Field(..., min_length=3)
    rule_id: str = "RULE-TERM-01"


class VerifiedFactCreate(BaseModel):
    statement: str = Field(..., min_length=5)
    numeric_value: str = ""
    numeric_units: str = ""
    product_context: str = Field(..., min_length=2)
    source_reference: str = Field(..., min_length=3)
    applicable_conditions: str = Field(..., min_length=3)
    date_version: str = "2026-10 (v1.0)"
    verification_status: str = "Verified"  # "Verified", "Pending Verification", "Archived"


class BrandColorCreate(BaseModel):
    name: str = Field(..., min_length=2)
    hex_code: str = Field(..., pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    usage_role: str = Field(..., min_length=2)
    max_delta_e: float = Field(14.0, ge=1.0, le=50.0)


class RuleCreate(BaseModel):
    pillar: str
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5)
    severity: str = "high"
    pattern_regex: str = ""
    do_example: str = ""
    dont_example: str = ""


class NewAuditRequest(BaseModel):
    brand_id: str = Field(..., min_length=1, description="Brand profile identifier")
    document_name: str = Field(..., min_length=1)
    input_format: str = "markdown"
    content: str = Field(..., min_length=1)
    fg_color: str = ""
    bg_color: str = ""
    image_alt_text: str = ""
    has_visual_asset: bool = False
    confidential_mode: bool = True


class FindingDecisionRequest(BaseModel):
    decision: str  # "accept", "modify", "dismiss"
    modified_replacement: Optional[str] = None
    reason: Optional[str] = None


class WorkflowStateRequest(BaseModel):
    new_state: str  # "Draft", "In Review", "Changes Requested", "Revised", "Approved"
    comment: str = ""
    override_acknowledged: bool = False


# ============================================================================
# VAULT & DATA HELPERS
# ============================================================================

def get_brand_vault_bundle(brand_id: str) -> Dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM brands WHERE id = ?", (brand_id,))
    b_row = cur.fetchone()
    if not b_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")

    brand = dict(b_row)
    brand["is_demo"] = is_demo_mode()
    try:
        brand["do_examples_list"] = json.loads(brand.get("do_examples") or "[]")
    except Exception:
        brand["do_examples_list"] = []
    try:
        brand["dont_examples_list"] = json.loads(brand.get("dont_examples") or "[]")
    except Exception:
        brand["dont_examples_list"] = []

    cur.execute("SELECT * FROM rules WHERE brand_id = ? ORDER BY id", (brand_id,))
    rules = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM terminology WHERE brand_id = ? ORDER BY id", (brand_id,))
    terms = [dict(t) for t in cur.fetchall()]

    cur.execute("SELECT * FROM verified_facts WHERE brand_id = ? ORDER BY id", (brand_id,))
    facts = []
    for f_row in cur.fetchall():
        fd = dict(f_row)
        fd["is_demo"] = is_demo_mode()
        facts.append(fd)

    cur.execute("SELECT * FROM brand_colors WHERE brand_id = ? ORDER BY id", (brand_id,))
    colors = [dict(c) for c in cur.fetchall()]

    conn.close()
    return {
        "brand": brand,
        "rules": rules,
        "terminology": terms,
        "verified_facts": facts,
        "colors": colors,
    }


def persist_audit_record(
    brand_id: str,
    document_name: str,
    input_format: str,
    content: str,
    fg_color: str,
    bg_color: str,
    image_alt_text: str,
    has_visual_asset: bool,
    visual_metadata: Dict[str, Any],
    confidential_mode: bool,
    audit_output: Dict[str, Any],
    actor_role: str = "Content Creator",
    actor_name: str = "",
    actor_user_id: str = "",
    visual_asset_b64: str = "",
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    vault = get_brand_vault_bundle(brand_id)

    with db_session() as conn:
        cur = conn.cursor()
        audit_id = allocate_audit_id(cur)

        cur.execute(
            """
            INSERT INTO audits (
                id, brand_id, brand_version, document_name, input_format,
                original_content, current_content, fg_color, bg_color,
                image_alt_text, has_visual_asset, visual_metadata_json,
                confidential_mode, overall_status, assigned_reviewer,
                pillar_states_json, runtime_ms, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft',
                'Editorial & Brand Reviewer', ?, ?, ?, ?
            )
            """,
            (
                audit_id,
                brand_id,
                int(vault["brand"].get("version", 1)),
                document_name,
                input_format,
                content,
                content,
                fg_color,
                bg_color,
                image_alt_text,
                1 if has_visual_asset else 0,
                json.dumps(visual_metadata),
                1 if confidential_mode else 0,
                json.dumps(audit_output["pillar_states"]),
                float(audit_output.get("runtime_ms", 0.0)),
                now,
                now,
            ),
        )

        finding_rows = []
        if visual_asset_b64:
            cur.execute("UPDATE audits SET visual_asset_b64 = ? WHERE id = ?", (visual_asset_b64, audit_id))
        for idx, f in enumerate(audit_output["findings"], start=1):
            finding_pk = f"{audit_id}-F{idx:02d}"
            finding_rows.append(
                (
                    finding_pk,
                    audit_id,
                    f["pillar"],
                    f["issue_type"],
                    f["severity"],
                    f["flagged_text"],
                    f["paragraph_ref"],
                    int(f["start_index"]),
                    int(f["end_index"]),
                    f["rule_or_fact_id"],
                    f["source_evidence"],
                    f["explanation"],
                    f.get("suggested_correction") or "",
                    f["detection_method"],
                    f["engine_source"],
                    f.get("similarity_score"),
                    f.get("review_state", "open"),
                    now,
                )
            )
        if finding_rows:
            cur.executemany(
                """
                INSERT INTO findings (
                    id, audit_id, pillar, issue_type, severity, flagged_text,
                    paragraph_ref, start_index, end_index, rule_or_fact_id,
                    source_evidence, explanation, suggested_correction, detection_method,
                    engine_source, similarity_score, review_state, decision_note, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?
                )
                """,
                finding_rows,
            )

        cur.execute(
            """
            INSERT INTO revisions
            (audit_id, version_number, previous_content, revised_content, editor_role, change_summary, created_at)
            VALUES (?, 1, ?, ?, ?, 'Initial content submitted for pre-publication brand audit.', ?)
            """,
            (audit_id, content, content, actor_role, now),
        )

        open_cnt = sum(1 for f in audit_output["findings"] if f.get("review_state", "open") in ("open", "needs_review"))
        record_audit_event(
            cur,
            audit_id,
            "submitted",
            actor_name or configured_user_name(),
            actor_role,
            f"Submitted for audit (v1). {len(audit_output['findings'])} finding(s) recorded, {open_cnt} need review.",
            {"findings": len(audit_output["findings"]), "open_findings": open_cnt, "input_format": input_format},
            1,
            now,
            actor_user_id=actor_user_id,
        )

    return audit_id


# ============================================================================
# SYSTEM & OVERVIEW ENDPOINTS
# ============================================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "LoomShield Brand Governance Workspace",
        "engine": get_engine_status(),
    }


@app.get("/api/_diag/client-ip", include_in_schema=False)
def diag_client_ip(request: Request):
    if os.environ.get("LOOMSHIELD_DEBUG_HEADERS", "").strip() != "1":
        raise HTTPException(status_code=404, detail="Not found")
    socket_host = getattr(getattr(request, "client", None), "host", None)
    return {
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
        "cf-connecting-ip": request.headers.get("cf-connecting-ip"),
        "true-client-ip": request.headers.get("true-client-ip"),
        "x-real-ip": request.headers.get("x-real-ip"),
        "socket_host": socket_host,
        "computed_ip": get_client_ip(request),
    }


@app.get("/api/engine-status")
def engine_status_endpoint():
    status = get_engine_status()
    proc_mode = processing_mode()
    status["processing_mode"] = proc_mode
    if proc_mode == "local":
        status["operating_mode"] = f"Local-only processing on this device ({platform.system()} {platform.machine()}). No data leaves your machine."
        status["local_only_mode"] = "On"
    else:
        status["operating_mode"] = "Hosted processing on the LoomShield server. Submitted audits are saved to workspace history."
        status["local_only_mode"] = "Off (Hosted Server Deployment)"
    status["cloud_fallback_status"] = "not implemented"
    storage_type = os.environ.get("LOOMSHIELD_STORAGE", "").strip().lower()
    if not storage_type:
        storage_type = "persistent" if (os.environ.get("LOOMSHIELD_DEPLOYMENT") == "local" or os.environ.get("LOOMSHIELD_DB_PATH")) else "ephemeral"
    status["storage_type"] = storage_type
    status["db_type"] = "SQLite"
    status["last_selftest"] = _LAST_SELFTEST_RESULT
    status["selftest"] = _LAST_SELFTEST_RESULT
    status["last_selftest_time"] = _LAST_SELFTEST_TIME
    try:
        with db_session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM brands")
            b_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM audits")
            a_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM rules")
            r_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM findings")
            f_cnt = cur.fetchone()["c"]
            status["record_counts"] = {
                "brands": b_cnt,
                "audits": a_cnt,
                "rules": r_cnt,
                "findings": f_cnt,
            }
    except Exception:
        status["record_counts"] = {}
    return status


@app.post("/api/engine-selftest")
def run_engine_selftest_endpoint(role: str = Depends(current_role)):
    global _LAST_SELFTEST_RESULT, _LAST_SELFTEST_TIME
    result = run_engine_selftest()
    _LAST_SELFTEST_RESULT = result
    _LAST_SELFTEST_TIME = datetime.now(timezone.utc).isoformat()
    return {
        "selftest": result,
        "self_test": result,
        "last_checked_at": _LAST_SELFTEST_TIME,
        "engine_status": engine_status_endpoint(),
    }


class DemoLoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


@app.get("/api/session")
def get_session(
    authorization: Optional[str] = Header(None),
    x_loomshield_role: Optional[str] = Header(None),
):
    """Signed-in identity, enforced role and permissions for the current workspace."""
    try:
        return session_payload(requested_role=x_loomshield_role, authorization=authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/demo/users")
def list_demo_users_endpoint():
    return {
        "users": list(DEMO_USERS) if is_demo_mode() else [],
        "disclosure": DEMO_SIGNIN_DISCLOSURE if is_demo_mode() else "",
    }


@app.post("/api/demo/login")
def demo_login_endpoint(req: DemoLoginRequest):
    if not is_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Demo sign-in is only available when the server runs in demo workspace mode.",
        )
    try:
        return issue_demo_token(req.user_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/demo/reset")
def reset_demo_workspace_endpoint(request: Request):
    if not is_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Demo reset is only available in demo workspace mode.",
        )
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before resetting demo data.",
        )
    reset_demo_workspace()
    return {
        "status": "reset",
        "message": "Sample workspace restored to its initial state.",
        "overview": get_overview_dashboard("novapay"),
    }


class BrandCreateRequest(BaseModel):
    id: str = Field(..., min_length=2, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=2)
    industry: str = "Enterprise SaaS"
    description: str = "Organisational brand governance profile."
    tone_principles: str = "Calm, accurate, evidence-backed, and transparent."
    writing_style: str = "Clear active prose with defined technical terminology."
    messaging_principles: str = "Highlight human oversight and verified product capabilities."


@app.get("/api/brands")
def list_brands():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM brands ORDER BY name")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"brands": rows}


@app.post("/api/brands")
def create_brand_profile(req: BrandCreateRequest, role: str = Depends(current_role)):
    require_permission(role, "manage_brands", "Only a Brand Administrator can create brand profiles")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM brands WHERE id = ?", (req.id,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail=f"Brand '{req.id}' already exists.")
        cur.execute(
            """
            INSERT INTO brands (
                id, name, industry, description, tone_principles, writing_style,
                messaging_principles, do_examples, dont_examples, typography_specs,
                spacing_rules, logo_placement_constraints, min_contrast_normal,
                min_contrast_large, require_alt_text, enforce_heading_order,
                target_reading_ease, version, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, '[]', '[]',
                'Inter / Geist headings and body',
                '8px base spacing grid and 16px clear space',
                'Maintain aspect ratio and high-contrast placement',
                4.5, 3.0, 1, 1, 50.0, 1, ?
            )
            """,
            (
                req.id,
                req.name.strip(),
                req.industry.strip(),
                req.description.strip(),
                req.tone_principles.strip(),
                req.writing_style.strip(),
                req.messaging_principles.strip(),
                now,
            ),
        )
    return get_brand_vault_bundle(req.id)


@app.get("/api/wizard/options")
def get_wizard_options_endpoint():
    """Retrieve question options, tiles, and descriptions for guided audit setup."""
    if not is_wizard_available():
        raise HTTPException(
            status_code=503,
            detail="Guided setup is temporarily unavailable",
        )
    return WIZARD_OPTIONS


@app.post("/api/wizard/preview")
def preview_wizard_answers_endpoint(req: WizardAnswers):
    """Preview rule summaries, plain bullets, and tailored example text without writing to database."""
    if not is_wizard_available():
        raise HTTPException(
            status_code=503,
            detail="Guided setup is temporarily unavailable",
        )
    spec = compose(req.model_dump())
    return {
        "profile_label": spec["profile_label"],
        "summary": spec["summary"],
        "brand_text": spec["brand_text"],
        "accessibility": spec["accessibility"],
        "sample_text": get_sample_text_for_answers(req.model_dump()),
    }


@app.post("/api/wizard/profile")
def create_wizard_profile_endpoint(
    req: WizardAnswers,
    request: Request,
    role: str = Depends(current_role),
):
    """Atomically create a new isolated brand audit profile from wizard answers."""
    if not is_wizard_available():
        raise HTTPException(
            status_code=503,
            detail="Guided setup is temporarily unavailable",
        )
    require_permission(role, "run_audits", "Only users with run_audits permission can create audit profiles")
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before creating an audit profile.",
        )
    with db_session() as conn:
        profile_res = create_wizard_profile_in_db(conn, req.model_dump())

    vault = get_brand_vault_bundle(profile_res["brand_id"])
    return {
        "status": "created",
        "brand_id": profile_res["brand_id"],
        "profile_label": profile_res["name"],
        "summary": profile_res["summary"],
        "sample_text": profile_res["sample_text"],
        "vault": vault,
    }


@app.get("/api/overview/{brand_id}")
def get_overview_dashboard(brand_id: str):
    vault = get_brand_vault_bundle(brand_id)
    conn = get_connection()
    cur = conn.cursor()

    # F6: demo-only sample audits never count towards a non-demo overview.
    # G4: In demo mode, include all 6 sample audits (AUD-1001..AUD-1006). In non-demo mode, extra demo audits AUD-1003..1006 are excluded.
    DEMO_EXTRA_AUDIT_IDS = ("AUD-1003", "AUD-1004", "AUD-1005", "AUD-1006")
    demo_filter = "" if is_demo_mode() else f" AND id NOT IN {DEMO_EXTRA_AUDIT_IDS}"
    demo_join_filter = "" if is_demo_mode() else f" AND a.id NOT IN {DEMO_EXTRA_AUDIT_IDS}"

    cur.execute(f"SELECT COUNT(*) AS cnt FROM audits WHERE brand_id = ?{demo_filter}", (brand_id,))
    docs_audited = int(cur.fetchone()["cnt"])

    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM findings f
        JOIN audits a ON f.audit_id = a.id
        WHERE a.brand_id = ? AND f.review_state IN ('open', 'needs_review'){demo_join_filter}
        """,
        (brand_id,),
    )
    findings_requiring_attention = int(cur.fetchone()["cnt"])

    cur.execute(
        f"SELECT COUNT(*) AS cnt FROM audits WHERE brand_id = ? AND overall_status = 'Approved'{demo_filter}",
        (brand_id,),
    )
    approved_content = int(cur.fetchone()["cnt"])

    cur.execute(
        f"SELECT COUNT(*) AS cnt FROM audits WHERE brand_id = ? AND overall_status != 'Approved'{demo_filter}",
        (brand_id,),
    )
    awaiting_review = int(cur.fetchone()["cnt"])

    cur.execute(
        f"""
        SELECT COUNT(DISTINCT a.id) AS cnt
        FROM audits a JOIN findings f ON f.audit_id = a.id
        WHERE a.brand_id = ? AND f.review_state IN ('open', 'needs_review'){demo_join_filter}
        """,
        (brand_id,),
    )
    documents_needing_attention = int(cur.fetchone()["cnt"])

    active_rules_count = sum(1 for r in vault["rules"] if int(r.get("active", 1)) == 1)

    cur.execute(
        f"""
        SELECT
            a.id, a.document_name, a.input_format, a.overall_status, a.created_at, a.updated_at,
            COUNT(f.id) AS total_findings,
            SUM(CASE WHEN f.review_state IN ('open', 'needs_review') THEN 1 ELSE 0 END) AS open_findings
        FROM audits a
        LEFT JOIN findings f ON a.id = f.audit_id
        WHERE a.brand_id = ?{demo_join_filter}
        GROUP BY a.id
        ORDER BY a.updated_at DESC
        LIMIT 20
        """,
        (brand_id,),
    )
    recent_audits = []
    for r in cur.fetchall():
        recent_audits.append({
            "id": r["id"],
            "document_name": r["document_name"],
            "input_format": r["input_format"],
            "overall_status": r["overall_status"],
            "total_findings": int(r["total_findings"] or 0),
            "open_findings": int(r["open_findings"] or 0),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })

    conn.close()
    return {
        "brand_id": brand_id,
        "brand_name": vault["brand"]["name"],
        "brand_version": int(vault["brand"].get("version", 1)),
        "is_demo": bool(vault["brand"].get("is_demo", False)),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "documents_audited": docs_audited,
            "findings_requiring_attention": findings_requiring_attention,
            "approved_content": approved_content,
            "brand_rules": active_rules_count,
            "awaiting_review": awaiting_review,
            "documents_needing_attention": documents_needing_attention,
        },
        "recent_audits": recent_audits,
    }


# ============================================================================
# BRAND VAULT ENDPOINTS (5 SECTIONS: VOICE, TERMINOLOGY, FACTS, VISUAL, A11Y)
# ============================================================================

@app.get("/api/vault/{brand_id}")
def get_vault_endpoint(brand_id: str):
    return get_brand_vault_bundle(brand_id)


@app.put("/api/vault/{brand_id}/voice")
def update_brand_voice(brand_id: str, req: BrandVoiceUpdate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET description = ?, tone_principles = ?, writing_style = ?, messaging_principles = ?,
                do_examples = ?, dont_examples = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.description.strip(),
                req.tone_principles.strip(),
                req.writing_style.strip(),
                req.messaging_principles.strip(),
                json.dumps(req.do_examples),
                json.dumps(req.dont_examples),
                now,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
    return {"status": "updated", "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/visual-specs")
def update_visual_specs(brand_id: str, req: VisualSpecsUpdate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET typography_specs = ?, spacing_rules = ?, logo_placement_constraints = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.typography_specs.strip(),
                req.spacing_rules.strip(),
                req.logo_placement_constraints.strip(),
                now,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
    return {"status": "updated", "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/accessibility-rules")
def update_accessibility_rules(brand_id: str, req: AccessibilitySpecsUpdate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET min_contrast_normal = ?, min_contrast_large = ?, require_alt_text = ?,
                enforce_heading_order = ?, target_reading_ease = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.min_contrast_normal,
                req.min_contrast_large,
                1 if req.require_alt_text else 0,
                1 if req.enforce_heading_order else 0,
                req.target_reading_ease,
                now,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
    return {"status": "updated", "vault": get_brand_vault_bundle(brand_id)}


@app.post("/api/vault/{brand_id}/terminology")
def add_terminology_entry(brand_id: str, req: TerminologyCreate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        term_id = allocate_term_id(cur, brand_id)
        cur.execute(
            """
            INSERT INTO terminology (
                id, brand_id, preferred_term, prohibited_term, replacement_term,
                case_sensitive, notes, rule_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                term_id,
                brand_id,
                req.preferred_term.strip(),
                req.prohibited_term.strip(),
                req.replacement_term.strip(),
                1 if req.case_sensitive else 0,
                req.notes.strip(),
                req.rule_id.strip(),
                now,
            ),
        )
    return {"status": "created", "term_id": term_id, "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/terminology/{term_id}")
def update_terminology_entry(
    brand_id: str,
    term_id: str,
    req: TerminologyCreate,
    role: str = Depends(current_role),
):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE terminology
            SET preferred_term = ?, prohibited_term = ?, replacement_term = ?,
                case_sensitive = ?, notes = ?, rule_id = ?, updated_at = ?
            WHERE id = ? AND brand_id = ?
            """,
            (
                req.preferred_term.strip(),
                req.prohibited_term.strip(),
                req.replacement_term.strip(),
                1 if req.case_sensitive else 0,
                req.notes.strip(),
                req.rule_id.strip(),
                now,
                term_id,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Terminology rule not found")
    return {"status": "updated", "term_id": term_id, "vault": get_brand_vault_bundle(brand_id)}


@app.delete("/api/vault/{brand_id}/terminology/{term_id}")
def delete_terminology_entry(brand_id: str, term_id: str, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute("DELETE FROM terminology WHERE id = ? AND brand_id = ?", (term_id, brand_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Terminology entry not found")
    return {"status": "deleted", "term_id": term_id}


@app.post("/api/vault/{brand_id}/facts")
def add_verified_fact(brand_id: str, req: VerifiedFactCreate, role: str = Depends(current_role)):
    require_permission(role, "propose_facts", "Your role cannot add fact records")
    if req.verification_status == "Verified":
        require_permission(role, "verify_facts", "Only a Brand Administrator can mark a fact as Verified")
    if req.verification_status not in ("Verified", "Pending Verification", "Archived"):
        raise HTTPException(status_code=400, detail="Invalid verification_status")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        fact_id = allocate_fact_id(cur, brand_id)
        cur.execute(
            """
            INSERT INTO verified_facts (
                id, brand_id, statement, numeric_value, numeric_units, product_context,
                source_reference, applicable_conditions, date_version, verification_status,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                brand_id,
                req.statement.strip(),
                req.numeric_value.strip(),
                req.numeric_units.strip(),
                req.product_context.strip(),
                req.source_reference.strip(),
                req.applicable_conditions.strip(),
                req.date_version.strip(),
                req.verification_status,
                now,
            ),
        )
    return {"status": "created", "fact_id": fact_id, "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/facts/{fact_id}")
def update_verified_fact(
    brand_id: str,
    fact_id: str,
    req: VerifiedFactCreate,
    role: str = Depends(current_role),
):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    if req.verification_status not in ("Verified", "Pending Verification", "Archived"):
        raise HTTPException(status_code=400, detail="Invalid verification_status")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE verified_facts
            SET statement = ?, numeric_value = ?, numeric_units = ?, product_context = ?,
                source_reference = ?, applicable_conditions = ?, date_version = ?,
                verification_status = ?, updated_at = ?
            WHERE id = ? AND brand_id = ?
            """,
            (
                req.statement.strip(),
                req.numeric_value.strip(),
                req.numeric_units.strip(),
                req.product_context.strip(),
                req.source_reference.strip(),
                req.applicable_conditions.strip(),
                req.date_version.strip(),
                req.verification_status,
                now,
                fact_id,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Fact not found")
    return {"status": "updated", "fact_id": fact_id, "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/facts/{fact_id}/status")
def update_fact_status(
    brand_id: str,
    fact_id: str,
    payload: Dict[str, str],
    role: str = Depends(current_role),
):
    require_permission(role, "verify_facts", "Only a Brand Administrator can change fact verification status")
    new_status = payload.get("status")
    if new_status not in ("Verified", "Pending Verification", "Archived"):
        raise HTTPException(status_code=400, detail="Invalid verification status")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            "UPDATE verified_facts SET verification_status = ?, updated_at = ? WHERE id = ? AND brand_id = ?",
            (new_status, now, fact_id, brand_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Fact not found")
    return {"status": "updated", "fact_id": fact_id, "verification_status": new_status, "vault": get_brand_vault_bundle(brand_id)}


@app.delete("/api/vault/{brand_id}/facts/{fact_id}")
def delete_verified_fact(brand_id: str, fact_id: str, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute("DELETE FROM verified_facts WHERE id = ? AND brand_id = ?", (fact_id, brand_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Fact not found")
    return {"status": "deleted", "fact_id": fact_id}


@app.post("/api/vault/{brand_id}/colors")
def add_brand_color(brand_id: str, req: BrandColorCreate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        col_id = allocate_color_id(cur, brand_id)
        cur.execute(
            """
            INSERT INTO brand_colors (id, brand_id, name, hex_code, usage_role, max_delta_e)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (col_id, brand_id, req.name.strip(), req.hex_code.upper(), req.usage_role.strip(), req.max_delta_e),
        )
    return {"status": "created", "color_id": col_id, "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/colors/{color_id}")
def update_brand_color(brand_id: str, color_id: str, req: BrandColorCreate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brand_colors
            SET name = ?, hex_code = ?, usage_role = ?, max_delta_e = ?
            WHERE id = ? AND brand_id = ?
            """,
            (req.name.strip(), req.hex_code.upper(), req.usage_role.strip(), req.max_delta_e, color_id, brand_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Color not found")
    return {"status": "updated", "color_id": color_id, "vault": get_brand_vault_bundle(brand_id)}


@app.delete("/api/vault/{brand_id}/colors/{color_id}")
def delete_brand_color(brand_id: str, color_id: str, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute("DELETE FROM brand_colors WHERE id = ? AND brand_id = ?", (color_id, brand_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Color not found")
    return {"status": "deleted", "color_id": color_id}


@app.post("/api/vault/{brand_id}/rules")
def add_brand_rule(brand_id: str, req: RuleCreate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    if req.pattern_regex.strip():
        is_safe, reason = check_pattern_structural_safety(req.pattern_regex.strip())
        if not is_safe:
            raise HTTPException(
                status_code=422,
                detail=f"Rule pattern rejected: {reason} for pattern '{req.pattern_regex.strip()}'",
            )
    now = datetime.now(timezone.utc).isoformat()
    cfg = {"patterns": [req.pattern_regex]} if req.pattern_regex.strip() else {}
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        rule_id = allocate_rule_id(cur, brand_id)
        cur.execute(
            """
            INSERT INTO rules (
                id, brand_id, pillar, title, description, rule_config_json,
                severity, do_example, dont_example, active, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
            """,
            (
                rule_id,
                brand_id,
                req.pillar,
                req.title.strip(),
                req.description.strip(),
                json.dumps(cfg),
                req.severity,
                req.do_example.strip(),
                req.dont_example.strip(),
                now,
            ),
        )
    return {"status": "created", "rule_id": rule_id, "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/rules/{rule_id}")
def update_brand_rule(brand_id: str, rule_id: str, req: RuleCreate, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    if req.pattern_regex.strip():
        is_safe, reason = check_pattern_structural_safety(req.pattern_regex.strip())
        if not is_safe:
            raise HTTPException(
                status_code=422,
                detail=f"Rule pattern rejected: {reason} for pattern '{req.pattern_regex.strip()}'",
            )
    now = datetime.now(timezone.utc).isoformat()
    cfg = {"patterns": [req.pattern_regex]} if req.pattern_regex.strip() else {}
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE rules
            SET pillar = ?, title = ?, description = ?, rule_config_json = ?, severity = ?,
                do_example = ?, dont_example = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND brand_id = ?
            """,
            (
                req.pillar,
                req.title.strip(),
                req.description.strip(),
                json.dumps(cfg),
                req.severity,
                req.do_example.strip(),
                req.dont_example.strip(),
                now,
                rule_id,
                brand_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "updated", "rule_id": rule_id, "vault": get_brand_vault_bundle(brand_id)}


@app.delete("/api/vault/{brand_id}/rules/{rule_id}")
def delete_brand_rule(brand_id: str, rule_id: str, role: str = Depends(current_role)):
    require_permission(role, "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute("DELETE FROM rules WHERE id = ? AND brand_id = ?", (rule_id, brand_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted", "rule_id": rule_id}


# ============================================================================
# AUDIT EXECUTION, PERSISTENCE & CORRECTION DECISIONS
# ============================================================================

@app.post("/api/audits")
def create_and_run_audit(
    req: NewAuditRequest,
    request: Request,
    actor: Dict[str, str] = Depends(current_actor),
):
    role = actor["role"]
    require_permission(role, "run_audits", "Your role is not authorized to create and run audits")
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before running another audit.")
    vault = get_brand_vault_bundle(req.brand_id)
    structural_findings = []
    if req.input_format == "html" or re.search(r"<(?:h[1-6]|img|script)\b", req.content, re.IGNORECASE):
        parsed_html = parse_uploaded_file("snippet.html", req.content.encode("utf-8"))
        structural_findings = parsed_html.get("structural_findings", [])
    elif req.input_format in ("markdown", "md") or re.search(r"^\s*#{1,6}\s+", req.content, re.MULTILINE):
        parsed_md = parse_uploaded_file("snippet.md", req.content.encode("utf-8"))
        structural_findings = parsed_md.get("structural_findings", [])

    audit_output = run_six_pillar_audit(
        content=req.content,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color=req.fg_color,
        bg_color=req.bg_color,
        image_alt_text=req.image_alt_text,
        has_visual_asset=req.has_visual_asset,
        structural_findings=structural_findings,
    )
    timing_meta = {
        "deterministic_ms": audit_output.get("deterministic_ms", 0.0),
        "nlp_retrieval_ms": audit_output.get("nlp_retrieval_ms", 0.0),
    }
    audit_id = persist_audit_record(
        brand_id=req.brand_id,
        document_name=req.document_name,
        input_format=req.input_format,
        content=req.content,
        fg_color=req.fg_color,
        bg_color=req.bg_color,
        image_alt_text=req.image_alt_text,
        has_visual_asset=req.has_visual_asset,
        visual_metadata=timing_meta,
        confidential_mode=req.confidential_mode,
        audit_output=audit_output,
        actor_role=role,
        actor_name=actor["user_name"],
        actor_user_id=actor["user_id"],
    )
    return get_audit_detail(audit_id)


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 64 * 1024


async def _read_upload_in_chunks(
    upload_file: UploadFile,
    max_bytes: int = MAX_UPLOAD_BYTES,
    chunk_size: int = UPLOAD_CHUNK_BYTES,
) -> bytes:
    """F2: Read uploaded stream in chunks and abort at 5 MB + 1 byte without buffering the remaining body."""
    chunks: List[bytes] = []
    total_read = 0
    while True:
        # Never request more than (max_bytes + 1 - total_read), so the abort happens exactly at 5 MB + 1 byte.
        chunk = await upload_file.read(min(chunk_size, max_bytes + 1 - total_read))
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(status_code=400, detail="File size exceeds the 5 MB safety limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/audits/upload")
async def create_audit_from_upload(
    request: Request,
    brand_id: str = Form(..., min_length=1, description="Brand profile identifier"),
    document_name: str = Form(""),
    fg_color: str = Form(""),
    bg_color: str = Form(""),
    image_alt_text: str = Form(""),
    confidential_mode: bool = Form(True),
    grid_size: int = Form(4),
    logo_only: bool = Form(False),
    logo_rect: str = Form(""),
    text_regions: str = Form(""),
    file: UploadFile = File(...),
    role: str = Depends(current_role),
):
    require_permission(role, "run_audits", "Your role is not authorized to upload documents for auditing")
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before uploading another file.")
    raw_bytes = await _read_upload_in_chunks(file)

    raw_fname = (file.filename or "uploaded_file").replace("\\", "/")
    fname = os.path.basename(raw_fname).replace("..", "") or "uploaded_file"
    safe_doc_name = os.path.basename((document_name or fname).replace("\\", "/")).replace("..", "") or fname
    ext = os.path.splitext(fname.lower())[1]
    vault = get_brand_vault_bundle(brand_id)

    if ext in (".png", ".jpg", ".jpeg"):
        parsed_logo_rect = None
        if logo_rect and logo_rect.strip():
            try:
                parsed_logo_rect = json.loads(logo_rect)
            except Exception:
                parsed_logo_rect = None
        parsed_text_regions = None
        if text_regions and text_regions.strip():
            try:
                parsed_text_regions = json.loads(text_regions)
            except Exception:
                parsed_text_regions = None
        try:
            shared_rgba = probe_and_decode_raster_image(raw_bytes)
        except ImageTooLargeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception:
            shared_rgba = None

        legacy_vis = inspect_raster_image(raw_bytes, vault["colors"], decoded_image=shared_rgba)
        vis_info = inspect_visual_heatmap(
            raw_bytes,
            vault["colors"],
            brand=vault["brand"],
            filename=fname,
            grid_size=grid_size,
            logo_only=logo_only,
            logo_rect=parsed_logo_rect,
            text_regions=parsed_text_regions,
            decoded_image=shared_rgba,
        )
        if vis_info.get("inspect_ok"):
            vis_info["swatches"] = legacy_vis.get("swatches", [])
            vis_info["off_palette_swatches"] = legacy_vis.get("off_palette_swatches", [])
            vis_info["has_transparency"] = legacy_vis.get("has_transparency", False)
            vis_info["all_transparent"] = legacy_vis.get("all_transparent", False)
            vis_info["limitation_note"] = legacy_vis.get("limitation_note", "")
        mime_str = "image/png" if ext == ".png" else "image/jpeg"
        raster_b64 = (
            f"data:{mime_str};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
            if vis_info.get("inspect_ok")
            else ""
        )
        audit_output = run_six_pillar_audit(
            content=f"[Visual Asset Audit: {fname}]",
            brand=vault["brand"],
            rules=vault["rules"],
            terminology_rows=vault["terminology"],
            facts=vault["verified_facts"],
            brand_colors=vault["colors"],
            fg_color=fg_color,
            bg_color=bg_color,
            image_alt_text=image_alt_text,
            has_visual_asset=True,
            visual_inspection=vis_info,
        )
        audit_id = persist_audit_record(
            brand_id=brand_id,
            document_name=safe_doc_name,
            input_format=ext.lstrip("."),
            content=f"[Visual Asset Audit: {fname}]",
            fg_color=fg_color,
            bg_color=bg_color,
            image_alt_text=image_alt_text,
            has_visual_asset=True,
            visual_metadata=vis_info,
            visual_asset_b64=raster_b64,
            confidential_mode=confidential_mode,
            audit_output=audit_output,
            actor_role=role,
        )
        return get_audit_detail(audit_id)

    parsed = parse_uploaded_file(fname, raw_bytes)
    svg_heatmap_vis = None
    svg_asset_b64 = ""
    if parsed["input_format"] == "svg" and parsed["parse_ok"]:
        parsed_logo_rect = None
        if logo_rect and logo_rect.strip():
            try:
                parsed_logo_rect = json.loads(logo_rect)
            except Exception:
                parsed_logo_rect = None
        parsed_text_regions = None
        if text_regions and text_regions.strip():
            try:
                parsed_text_regions = json.loads(text_regions)
            except Exception:
                parsed_text_regions = None
        svg_heatmap_vis = inspect_visual_heatmap(
            raw_bytes,
            vault["colors"],
            brand=vault["brand"],
            filename=fname,
            grid_size=grid_size,
            logo_only=logo_only,
            logo_rect=parsed_logo_rect,
            text_regions=parsed_text_regions,
        )
        clean_svg_str = (svg_heatmap_vis or {}).get("sanitized_svg") or ""
        if clean_svg_str:
            svg_asset_b64 = f"data:image/svg+xml;base64,{base64.b64encode(clean_svg_str.encode('utf-8')).decode('ascii')}"
    audit_output = run_six_pillar_audit(
        content=parsed["extracted_text"],
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color=fg_color,
        bg_color=bg_color,
        image_alt_text=image_alt_text,
        has_visual_asset=(parsed["input_format"] == "svg"),
        structural_findings=parsed["structural_findings"],
        parser_failed=not parsed["parse_ok"],
        parser_error_msg=parsed["error"] or "",
        page_spans=parsed.get("page_spans"),
        visual_inspection=svg_heatmap_vis,
    )
    pdf_meta = {
        "format": "pdf",
        "page_count": parsed.get("page_count", 0),
        "page_spans": parsed.get("page_spans", []),
    } if parsed["input_format"] == "pdf" else {}
    audit_id = persist_audit_record(
        brand_id=brand_id,
        document_name=safe_doc_name,
        input_format=parsed["input_format"],
        content=parsed["extracted_text"] or f"[Unparseable file: {fname}]",
        fg_color=fg_color,
        bg_color=bg_color,
        image_alt_text=image_alt_text,
        has_visual_asset=(parsed["input_format"] == "svg"),
        visual_metadata=svg_heatmap_vis if svg_heatmap_vis else pdf_meta,
        visual_asset_b64=svg_asset_b64,
        confidential_mode=confidential_mode,
        audit_output=audit_output,
        actor_role=role,
    )
    return get_audit_detail(audit_id)


@app.get("/api/audits")
def list_audits(
    brand_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    role: str = Depends(current_role),
):
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    conn = get_connection()
    cur = conn.cursor()
    DEMO_EXTRA_AUDIT_IDS = ("AUD-1003", "AUD-1004", "AUD-1005", "AUD-1006")
    demo_filter = "" if is_demo_mode() else f" AND id NOT IN {DEMO_EXTRA_AUDIT_IDS}"
    demo_join_filter = "" if is_demo_mode() else f" AND a.id NOT IN {DEMO_EXTRA_AUDIT_IDS}"

    if brand_id:
        cur.execute(f"SELECT COUNT(*) AS total FROM audits WHERE brand_id = ?{demo_filter}", (brand_id,))
        total = int(cur.fetchone()["total"] or 0)
        cur.execute(
            f"""
            SELECT
                a.id, a.brand_id, a.brand_version, a.document_name, a.input_format,
                a.overall_status, a.assigned_reviewer, a.submitted_by_user_id, a.submitted_by_name,
                a.pillar_states_json, a.runtime_ms, a.created_at, a.updated_at,
                COUNT(f.id) AS total_findings,
                SUM(CASE WHEN f.review_state IN ('open', 'needs_review') THEN 1 ELSE 0 END) AS open_findings
            FROM audits a
            LEFT JOIN findings f ON a.id = f.audit_id
            WHERE a.brand_id = ?{demo_join_filter}
            GROUP BY a.id
            ORDER BY a.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (brand_id, safe_limit, safe_offset),
        )
    else:
        cur.execute(f"SELECT COUNT(*) AS total FROM audits WHERE 1=1{demo_filter}")
        total = int(cur.fetchone()["total"] or 0)
        cur.execute(
            f"""
            SELECT
                a.id, a.brand_id, a.brand_version, a.document_name, a.input_format,
                a.overall_status, a.assigned_reviewer, a.submitted_by_user_id, a.submitted_by_name,
                a.pillar_states_json, a.runtime_ms, a.created_at, a.updated_at,
                COUNT(f.id) AS total_findings,
                SUM(CASE WHEN f.review_state IN ('open', 'needs_review') THEN 1 ELSE 0 END) AS open_findings
            FROM audits a
            LEFT JOIN findings f ON a.id = f.audit_id
            WHERE 1=1{demo_join_filter}
            GROUP BY a.id
            ORDER BY a.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (safe_limit, safe_offset),
        )
    rows = cur.fetchall()
    result = []
    for r in rows:
        row_dict = dict(r)
        try:
            row_dict["pillar_states"] = json.loads(row_dict.get("pillar_states_json") or "{}")
        except Exception:
            row_dict["pillar_states"] = {}
        row_dict["total_findings"] = int(row_dict.get("total_findings") or 0)
        row_dict["open_findings"] = int(row_dict.get("open_findings") or 0)
        result.append(row_dict)
    conn.close()
    return {
        "audits": result,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }


@app.get("/api/audits/{audit_id}")
def get_audit_detail(audit_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audits WHERE id = ?", (audit_id,))
    a_row = cur.fetchone()
    if not a_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' not found.")
    audit = dict(a_row)

    cur.execute("SELECT * FROM findings WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    findings = [dict(f) for f in cur.fetchall()]

    cur.execute("SELECT * FROM revisions WHERE audit_id = ? ORDER BY version_number ASC", (audit_id,))
    revisions = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM review_decisions WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    decisions = [dict(d) for d in cur.fetchall()]

    cur.execute("SELECT * FROM approvals WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    approvals = [dict(ap) for ap in cur.fetchall()]

    cur.execute("SELECT * FROM audit_events WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    events = []
    for ev in cur.fetchall():
        evd = dict(ev)
        try:
            evd["detail"] = json.loads(evd.pop("detail_json") or "{}")
        except Exception:
            evd["detail"] = {}
        events.append(evd)

    conn.close()

    try:
        audit["pillar_states"] = json.loads(audit.get("pillar_states_json") or "{}")
    except Exception:
        audit["pillar_states"] = {}
    try:
        audit["visual_metadata"] = json.loads(audit.get("visual_metadata_json") or "{}")
    except Exception:
        audit["visual_metadata"] = {}

    audit["findings"] = findings
    audit["revisions"] = revisions
    audit["review_decisions"] = decisions
    audit["approvals"] = approvals
    audit["events"] = events
    audit["open_findings_count"] = sum(
        1 for f in findings if f["review_state"] in ("open", "needs_review")
    )
    return audit


@app.post("/api/audits/{audit_id}/findings/{finding_id}/decision")
def apply_finding_decision(
    audit_id: str,
    finding_id: str,
    req: FindingDecisionRequest,
    actor: Dict[str, str] = Depends(current_actor),
):
    role = actor["role"]
    if req.decision not in ("accept", "modify", "dismiss", "needs_review"):
        raise HTTPException(status_code=400, detail="Decision must be 'accept', 'modify', 'dismiss', or 'needs_review'.")

    now = datetime.now(timezone.utc).isoformat()

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT current_content, overall_status, brand_id FROM audits WHERE id = ?", (audit_id,))
        a_row = cur.fetchone()
        if not a_row:
            raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' not found.")
        if a_row["overall_status"] == "Approved":
            raise HTTPException(
                status_code=409,
                detail="Cannot modify findings on an approved audit. Approved documents are locked for compliance integrity.",
            )
        current_text = a_row["current_content"]
        brand_id = a_row["brand_id"]

        cur.execute("SELECT * FROM findings WHERE id = ? AND audit_id = ?", (finding_id, audit_id))
        f_row = cur.fetchone()
        if not f_row:
            raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found.")
        target = dict(f_row)

        if target["review_state"] not in ("open", "needs_review"):
            raise HTTPException(
                status_code=409,
                detail=f"Finding '{finding_id}' is already in '{target['review_state']}' state and cannot be decided again.",
            )

        if req.decision in ("accept", "modify"):
            require_permission(role, "apply_corrections", "Your role is not authorized to apply corrections")

            s_idx = int(target["start_index"])
            e_idx = int(target["end_index"])

            if s_idx < 0:
                raise HTTPException(
                    status_code=409,
                    detail="This finding represents a document-level check or parser notice and has no inline text span. It can only be dismissed with an explanatory reason.",
                )

            replacement_used = (
                req.modified_replacement.strip()
                if (req.decision == "modify" and req.modified_replacement is not None)
                else (target["suggested_correction"] or "")
            )
            if not replacement_used:
                raise HTTPException(
                    status_code=400,
                    detail="No suggested replacement is available; provide a manual replacement via 'modify'.",
                )

            flagged_text = target["flagged_text"]

            if s_idx >= 0 and e_idx > s_idx and e_idx <= len(current_text) and current_text[s_idx:e_idx] == flagged_text:
                actual_start = s_idx
                actual_end = e_idx
            else:
                occ = current_text.count(flagged_text)
                if occ == 1:
                    actual_start = current_text.find(flagged_text)
                    actual_end = actual_start + len(flagged_text)
                elif occ > 1:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Cannot relocate finding: flagged text '{flagged_text}' occurs {occ} times in the document. Relocation is ambiguous; please rerun the audit.",
                    )
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Cannot apply correction: flagged text '{flagged_text}' could not be located in current document content. Please rerun the audit or dismiss the finding.",
                    )

            new_text = current_text[:actual_start] + replacement_used + current_text[actual_end:]

            if new_text == current_text:
                raise HTTPException(
                    status_code=409,
                    detail="Correction produced identical content; no revision was applied.",
                )

            delta_len = len(replacement_used) - (actual_end - actual_start)

            cur.execute("SELECT id, start_index, end_index FROM findings WHERE audit_id = ? AND id != ?", (audit_id, finding_id))
            for other in cur.fetchall():
                o_s = int(other["start_index"])
                o_e = int(other["end_index"])
                if o_s >= actual_end:
                    cur.execute(
                        "UPDATE findings SET start_index = ?, end_index = ? WHERE id = ?",
                        (o_s + delta_len, o_e + delta_len, other["id"]),
                    )

            new_finding_state = "accepted" if req.decision == "accept" else "modified"
            change_desc = (
                f"{req.decision.capitalize()}ed correction for {finding_id} ({target['rule_or_fact_id']}): "
                f"replaced '{flagged_text}' with '{replacement_used}'."
            )

            cur.execute("SELECT COUNT(*) AS rev_cnt FROM revisions WHERE audit_id = ?", (audit_id,))
            next_ver = cur.fetchone()["rev_cnt"] + 1

            cur.execute(
                """
                INSERT INTO revisions
                (audit_id, version_number, previous_content, revised_content, editor_role, change_summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, next_ver, current_text, new_text, role, change_desc, now),
            )
            record_audit_event(
                cur,
                audit_id,
                "correction_applied",
                actor["user_name"],
                role,
                change_desc,
                {
                    "finding_id": finding_id,
                    "rule_or_fact_id": target["rule_or_fact_id"],
                    "decision": req.decision,
                    "from": flagged_text,
                    "to": replacement_used,
                },
                next_ver,
                now,
                actor_user_id=actor["user_id"],
            )
            cur.execute(
                "UPDATE findings SET review_state = ?, decision_note = ?, updated_at = ? WHERE id = ? AND review_state IN ('open', 'needs_review')",
                (new_finding_state, replacement_used, now, finding_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Finding '{finding_id}' was modified or decided concurrently.",
                )
            cur.execute(
                "UPDATE audits SET current_content = ?, updated_at = ? WHERE id = ?",
                (new_text, now, audit_id),
            )
            cur.execute(
                """
                INSERT INTO review_decisions
                (audit_id, finding_id, decision, replacement_applied, reason, reviewer_role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, finding_id, req.decision, replacement_used, req.reason or "", role, now),
            )

        elif req.decision == "needs_review":
            note_str = (req.reason or "Marked for human review").strip()
            record_audit_event(
                cur,
                audit_id,
                "finding_flagged_for_review",
                actor["user_name"],
                role,
                f"Marked {finding_id} ({target['rule_or_fact_id']}) for human review: \"{note_str}\"",
                {
                    "finding_id": finding_id,
                    "rule_or_fact_id": target["rule_or_fact_id"],
                    "reason": note_str,
                },
                None,
                now,
                actor_user_id=actor["user_id"],
            )
            cur.execute(
                "UPDATE findings SET review_state = 'needs_review', decision_note = ?, updated_at = ? WHERE id = ? AND review_state IN ('open', 'needs_review')",
                (note_str, now, finding_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Finding '{finding_id}' was modified or decided concurrently.",
                )
            cur.execute(
                """
                INSERT INTO review_decisions
                (audit_id, finding_id, decision, replacement_applied, reason, reviewer_role, created_at)
                VALUES (?, ?, 'needs_review', '', ?, ?, ?)
                """,
                (audit_id, finding_id, note_str, role, now),
            )

        else:
            require_permission(role, "dismiss_findings", "Your role is not authorized to dismiss findings")
            reason_str = (req.reason or "").strip()
            if not reason_str:
                raise HTTPException(status_code=400, detail="A dismissal reason is required when dismissing a finding.")

            new_finding_state = "dismissed"
            primary_rule_id = target["rule_or_fact_id"].split("/")[0].strip()
            cur.execute(
                """
                INSERT INTO guideline_feedback
                (brand_id, rule_id, audit_id, finding_id, override_reason, suspected_cause, admin_review_state, created_at)
                VALUES (?, ?, ?, ?, ?, 'Logged via creator/reviewer dismissal', 'Open', ?)
                """,
                (brand_id, primary_rule_id, audit_id, finding_id, reason_str, now),
            )
            record_audit_event(
                cur,
                audit_id,
                "finding_dismissed",
                actor["user_name"],
                role,
                f'Dismissed {finding_id} ({target["rule_or_fact_id"]}): "{reason_str}"',
                {
                    "finding_id": finding_id,
                    "rule_or_fact_id": target["rule_or_fact_id"],
                    "reason": reason_str,
                },
                None,
                now,
                actor_user_id=actor["user_id"],
            )
            cur.execute(
                "UPDATE findings SET review_state = ?, decision_note = ?, updated_at = ? WHERE id = ? AND review_state IN ('open', 'needs_review')",
                (new_finding_state, reason_str, now, finding_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Finding '{finding_id}' was modified or decided concurrently.",
                )
            cur.execute(
                """
                INSERT INTO review_decisions
                (audit_id, finding_id, decision, replacement_applied, reason, reviewer_role, created_at)
                VALUES (?, ?, 'dismiss', '', ?, ?, ?)
                """,
                (audit_id, finding_id, reason_str, role, now),
            )

    return get_audit_detail(audit_id)


@app.post("/api/audits/{audit_id}/workflow")
def transition_audit_workflow(
    audit_id: str,
    req: WorkflowStateRequest,
    actor: Dict[str, str] = Depends(current_actor),
):
    role = actor["role"]
    detail = get_audit_detail(audit_id)
    current_state = detail["overall_status"]
    target_state = req.new_state

    actor_uid = str(actor.get("user_id") or "").strip()
    actor_uname = str(actor.get("user_name") or configured_user_name())
    is_token_actor = (actor.get("source") == "demo_token" and bool(actor_uid))

    # Collect all identified submitter user_ids from audit record AND approvals history (new_state='In Review')
    history_submitter_uids = {
        str(ap.get("approver_user_id") or "").strip()
        for ap in (detail.get("approvals") or [])
        if ap.get("new_state") == "In Review" and str(ap.get("approver_user_id") or "").strip()
    }
    current_sub_uid = str(detail.get("submitted_by_user_id") or "").strip()
    identified_submitters = set(history_submitter_uids)
    if current_sub_uid:
        identified_submitters.add(current_sub_uid)

    # 1. Permission & Separation of Duties checks
    if target_state == "Approved":
        if not has_permission(role, "approve"):
            raise HTTPException(
                status_code=403,
                detail=f"Signed-in role '{role}' is not authorized to approve audits.",
            )
        if is_demo_mode() and identified_submitters:
            # H1b: If the audit has any identified submitter, an Approved transition with no verified token identity is rejected
            if not is_token_actor:
                raise HTTPException(
                    status_code=403,
                    detail="Sign in as a demo user to approve this audit.",
                )
            # H1a: Block approval if actor's user_id appears on ANY approvals row with new_state='In Review' or submitted_by_user_id
            if actor_uid in identified_submitters:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Separation of duties: '{actor['user_name']}' submitted this audit for review "
                        "and cannot approve their own submission. A different Reviewer or Brand Administrator must approve it."
                    ),
                )
    elif target_state == "In Review":
        require_permission(role, "submit_for_review", "Your role is not authorized to submit for review")
        # H1c: A header-only request cannot resubmit an audit that has an identified submitter
        if is_demo_mode() and identified_submitters and not is_token_actor:
            raise HTTPException(
                status_code=403,
                detail="Sign in as a demo user to resubmit this audit for review.",
            )
    elif target_state == "Changes Requested":
        require_permission(role, "request_changes", "Your role is not authorized to request changes")
    elif target_state == "Revised":
        require_permission(role, "apply_corrections", "Your role is not authorized to mark as revised")

    # 2. Block approval if unacknowledged unresolved findings exist
    unresolved_count = detail["open_findings_count"]
    if target_state == "Approved":
        if unresolved_count > 0:
            if not (req.override_acknowledged and req.comment.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"This document still has {unresolved_count} unresolved finding(s). "
                        "Overriding unresolved findings requires explicit override acknowledgment and an approval rationale."
                    ),
                )
            if not has_permission(role, "approve_with_override"):
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{role}' is not authorized to approve with override.",
                )

    # 3. State transition graph validation (Draft must pass through In Review before Approved)
    allowed = {
        "Draft": ["In Review"],
        "In Review": ["Approved", "Changes Requested"],
        "Changes Requested": ["In Review", "Revised"],
        "Revised": ["In Review", "Approved"],
        "Approved": [],
    }.get(current_state, [])

    if target_state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid workflow transition from '{current_state}' to '{target_state}'. Allowed transitions: {allowed}.",
        )

    # 4. Block approval if any pillar check failed
    if target_state == "Approved":
        pillar_states = detail.get("pillar_states", {})
        if any(v == "Check Failed" for v in pillar_states.values()):
            raise HTTPException(
                status_code=409,
                detail="Cannot approve an audit while any pillar check has failed. Please resolve or rerun the audit.",
            )
        if any(f.get("detection_method") == "error" and f.get("review_state") != "dismissed" for f in detail["findings"]):
            raise HTTPException(
                status_code=409,
                detail="Cannot approve document with active error findings. Error findings must be dismissed with justification.",
            )

    now = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(detail["current_content"].encode("utf-8")).hexdigest()
    latest_version = len(detail["revisions"])

    with db_session() as conn:
        cur = conn.cursor()
        if target_state == "In Review":
            # H1c: Never overwrite a non-empty submitted_by_user_id with an empty one
            cur.execute(
                """
                UPDATE audits
                SET overall_status = ?,
                    submitted_by_user_id = CASE WHEN ? != '' THEN ? ELSE submitted_by_user_id END,
                    submitted_by_name = CASE WHEN ? != '' THEN ? ELSE submitted_by_name END,
                    updated_at = ?
                WHERE id = ? AND overall_status = ?
                """,
                (
                    target_state,
                    actor_uid,
                    actor_uid,
                    actor_uid,
                    actor_uname,
                    now,
                    audit_id,
                    current_state,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE audits
                SET overall_status = ?, updated_at = ?
                WHERE id = ? AND overall_status = ?
                """,
                (target_state, now, audit_id, current_state),
            )
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: audit status changed concurrently from '{current_state}'.",
            )
        cur.execute(
            """
            INSERT INTO approvals
            (audit_id, previous_state, new_state, approver_role, approver_user_id, approver_name, version_reviewed,
             unresolved_findings_count, override_acknowledged, comment, content_sha256, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                current_state,
                target_state,
                role,
                actor_uid,
                actor_uname,
                latest_version,
                unresolved_count,
                1 if req.override_acknowledged else 0,
                req.comment.strip() or f"State changed to {target_state}.",
                content_hash,
                now,
            ),
        )
        event_type = "approved" if target_state == "Approved" else "status_changed"
        event_summary = (
            f"Approved for publication by {actor_uname} ({role}) with {unresolved_count} unresolved finding(s)"
            + (" (authorised override recorded)." if req.override_acknowledged else ".")
            if target_state == "Approved"
            else f"Workflow state transitioned from {current_state} to {target_state} by {actor_uname} ({role})."
        )
        record_audit_event(
            cur,
            audit_id,
            event_type,
            actor_uname,
            role,
            event_summary,
            {
                "previous_state": current_state,
                "new_state": target_state,
                "unresolved_findings": unresolved_count,
                "override_acknowledged": bool(req.override_acknowledged),
                "comment": req.comment.strip(),
                "actor_user_id": actor_uid,
            },
            latest_version,
            now,
            actor_user_id=actor_uid,
        )

    return get_audit_detail(audit_id)


# ============================================================================
# PART B: ED25519 SIGNED COMPLIANCE CERTIFICATES
# ============================================================================

def _issue_or_get_certificate(audit_id: str, actor: Dict[str, str]) -> Dict[str, Any]:
    detail = get_audit_detail(audit_id)
    if detail.get("overall_status") != "Approved":
        raise HTTPException(
            status_code=409,
            detail="Compliance certificates can only be issued for Approved audits.",
        )

    _, _, active_kid, is_ephemeral = get_signing_key()

    # Check if already issued in certificates table
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM certificates WHERE audit_id = ?", (audit_id,))
    existing = cur.fetchone()
    cur.execute("SELECT name FROM brands WHERE id = ?", (detail["brand_id"],))
    b_row = cur.fetchone()
    brand_name = str(b_row["name"]) if b_row else str(detail["brand_id"])
    conn.close()

    if existing and existing["kid"] == active_kid:
        payload = json.loads(existing["payload_json"])
        return {
            "payload": payload,
            "alg": "Ed25519",
            "kid": existing["kid"],
            "signature_b64": existing["signature"],
            "ephemeral_key": bool(payload.get("ephemeral_key", is_ephemeral)),
            "key_notice": payload.get("key_notice", EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE),
        }

    # Locate the latest Approved record in approvals
    approved_rows = [ap for ap in (detail.get("approvals") or []) if ap.get("new_state") == "Approved"]
    approval_row = approved_rows[-1] if approved_rows else {}

    with db_session() as s_conn:
        s_cur = s_conn.cursor()
        s_cur.execute("SELECT * FROM certificates WHERE audit_id = ?", (audit_id,))
        row = s_cur.fetchone()

        if row and row["kid"] == active_kid:
            payload = json.loads(row["payload_json"])
            return {
                "payload": payload,
                "alg": "Ed25519",
                "kid": row["kid"],
                "signature_b64": row["signature"],
                "ephemeral_key": bool(payload.get("ephemeral_key", is_ephemeral)),
                "key_notice": payload.get("key_notice", EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE),
            }

        cert_id = str(row["id"]) if row else allocate_certificate_id(s_cur)
        issued_at = str(row["issued_at"]) if row else datetime.now(timezone.utc).isoformat()
        issued_by = str(row["issued_by"]) if row else (actor.get("user_name") or configured_user_name())

        try:
            payload = build_certificate_payload(
                certificate_id=cert_id,
                issued_at=issued_at,
                audit=detail,
                brand_name=brand_name,
                approval_row=approval_row,
                processing_mode_str=processing_mode(),
                is_ephemeral=is_ephemeral,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        envelope = sign_certificate_payload(payload)
        canonical_str = canonicalize_payload(payload).decode("utf-8")

        if row:
            s_cur.execute(
                """
                UPDATE certificates
                SET payload_json = ?, signature = ?, kid = ?
                WHERE audit_id = ?
                """,
                (canonical_str, envelope["signature_b64"], envelope["kid"], audit_id),
            )
        else:
            s_cur.execute(
                """
                INSERT INTO certificates (id, audit_id, payload_json, signature, kid, issued_at, issued_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cert_id,
                    audit_id,
                    canonical_str,
                    envelope["signature_b64"],
                    envelope["kid"],
                    issued_at,
                    issued_by,
                ),
            )
        return envelope


def _get_existing_certificate(audit_id: str) -> Dict[str, Any]:
    """Return an already-issued certificate for an Approved audit, or raise 404 (never issues)."""
    detail = get_audit_detail(audit_id)
    if detail.get("overall_status") != "Approved":
        raise HTTPException(
            status_code=409,
            detail="Compliance certificates can only be issued for Approved audits.",
        )
    _, _, _, is_ephemeral = get_signing_key()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM certificates WHERE audit_id = ?", (audit_id,))
    existing = cur.fetchone()
    conn.close()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"No compliance certificate has been issued for audit '{audit_id}' yet.",
        )
    payload = json.loads(existing["payload_json"])
    return {
        "payload": payload,
        "alg": "Ed25519",
        "kid": existing["kid"],
        "signature_b64": existing["signature"],
        "ephemeral_key": bool(payload.get("ephemeral_key", is_ephemeral)),
        "key_notice": payload.get("key_notice", EPHEMERAL_KEY_NOTICE if is_ephemeral else PERSISTENT_KEY_NOTICE),
    }


@app.post("/api/audits/{audit_id}/certificate")
def create_or_get_audit_certificate(
    audit_id: str,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "approve", "Your role is not authorized to issue compliance certificates")
    return _issue_or_get_certificate(audit_id, actor)


@app.get("/api/audits/{audit_id}/certificate")
def download_audit_certificate(
    audit_id: str,
    download: bool = False,
    actor: Dict[str, str] = Depends(current_actor),
):
    envelope = _get_existing_certificate(audit_id)
    headers = {}
    if download:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", audit_id)
        headers["Content-Disposition"] = f'attachment; filename="LoomShield_Certificate_{safe_id}.json"'
    return JSONResponse(content=envelope, headers=headers)


@app.get("/api/certificates/public-key")
def get_certificate_public_key_endpoint():
    return get_public_key_metadata()


@app.post("/api/certificates/verify")
async def verify_certificate_endpoint(request: Request):
    client_ip = get_client_ip(request)
    if not verify_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for certificate verification. Please wait a moment and try again.",
        )

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON request body.") from exc

    if not isinstance(body, dict):
        return verify_certificate_envelope(body)

    # Support either {payload, alg, kid, signature_b64} directly or {certificate: {...}, public_key_b64: "..."}
    envelope = body.get("certificate") if isinstance(body.get("certificate"), dict) else body
    pub_override = body.get("public_key_b64") if isinstance(body.get("public_key_b64"), str) else None

    result = verify_certificate_envelope(envelope, public_key_b64=pub_override)

    # H2: Run the audit cross-check ONLY when the cryptographic signature verified.
    # Invalid or malformed envelopes trigger NO database lookup and reveal nothing about server audits.
    if result.get("valid") is True:
        payload = envelope.get("payload") if isinstance(envelope, dict) else None
        audit_id = payload.get("audit_id") if isinstance(payload, dict) else None
        cert_hash = payload.get("content_sha256") if isinstance(payload, dict) else None

        if isinstance(audit_id, str) and audit_id.strip():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT current_content, overall_status FROM audits WHERE id = ?", (audit_id.strip(),))
            a_row = cur.fetchone()
            conn.close()

            if a_row:
                live_hash = hashlib.sha256(str(a_row["current_content"] or "").encode("utf-8")).hexdigest()
                matches = bool(live_hash == cert_hash)
                result["audit_exists_on_server"] = True
                result["server_audit_status"] = a_row["overall_status"]
                result["content_hash_matches_server"] = matches
                if not matches:
                    result["status"] = "content_hash_mismatch"
                    result["valid"] = False
                    result["reasons"].append(
                        "Server audit content hash no longer matches the certified content hash."
                    )
            else:
                result["audit_exists_on_server"] = False
                result["server_audit_status"] = None
                result["content_hash_matches_server"] = False
        else:
            result["audit_exists_on_server"] = False
            result["server_audit_status"] = None
            result["content_hash_matches_server"] = False

    return result


@app.post("/api/audits/{audit_id}/rerun")
def rerun_existing_audit(
    audit_id: str,
    request: Request,
    role: str = Depends(current_role),
):
    require_permission(role, "run_audits", "Your role is not authorized to rerun audits")
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before rerunning the audit.",
        )

    detail = get_audit_detail(audit_id)
    if detail["overall_status"] == "Approved":
        raise HTTPException(
            status_code=409,
            detail="Cannot rerun an approved audit. Approved documents are locked for compliance integrity.",
        )

    vault = get_brand_vault_bundle(detail["brand_id"])
    content = detail["current_content"]

    existing_findings = detail.get("findings", [])
    err_finding = next((f for f in existing_findings if f.get("detection_method") == "error"), None)
    is_parser_failed = bool(
        err_finding
        or content.startswith("[Unparseable file:")
    )
    err_msg = err_finding.get("explanation") if err_finding else "Document parser failure; text could not be extracted."

    structural_findings = []
    if not is_parser_failed:
        if detail["input_format"] == "html" or re.search(r"<(?:h[1-6]|img|script)\b", content, re.IGNORECASE):
            parsed_html = parse_uploaded_file("snippet.html", content.encode("utf-8"))
            structural_findings = parsed_html.get("structural_findings", [])
        elif detail["input_format"] in ("markdown", "md") or re.search(r"^\s*#{1,6}\s+", content, re.MULTILINE):
            parsed_md = parse_uploaded_file("snippet.md", content.encode("utf-8"))
            structural_findings = parsed_md.get("structural_findings", [])

    audit_output = run_six_pillar_audit(
        content=content,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color=detail["fg_color"],
        bg_color=detail["bg_color"],
        image_alt_text=detail["image_alt_text"],
        has_visual_asset=bool(detail["has_visual_asset"]),
        structural_findings=structural_findings,
        parser_failed=is_parser_failed,
        parser_error_msg=err_msg if is_parser_failed else "",
    )

    now = datetime.now(timezone.utc).isoformat()

    # Collect available old resolved findings (each can be claimed by at most one new finding)
    available_resolved = [
        dict(ef)
        for ef in existing_findings
        if ef.get("review_state") in ("accepted", "modified", "dismissed")
    ]

    matched_assignments = {}
    used_ids = set()

    # Pass 1: Match each new finding to at most one old resolved finding by key + nearest start_index
    for idx, f in enumerate(audit_output["findings"]):
        f_key = (f["pillar"], f["rule_or_fact_id"], f["flagged_text"])
        candidates = [
            c for c in available_resolved
            if (c.get("pillar"), c.get("rule_or_fact_id"), c.get("flagged_text")) == f_key
        ]
        if candidates:
            f_start = int(f.get("start_index", 0))
            best_cand = min(
                candidates,
                key=lambda c: abs(int(c.get("start_index", 0)) - f_start),
            )
            available_resolved.remove(best_cand)
            pk = best_cand["id"]
            used_ids.add(pk)
            matched_assignments[idx] = (
                pk,
                best_cand["review_state"],
                best_cand.get("decision_note") or "",
            )

    # Pass 2: Assign new IDs from a counter that skips every ID already used
    counter = 1
    finding_rows = []
    for idx, f in enumerate(audit_output["findings"]):
        if idx in matched_assignments:
            finding_pk, r_state, d_note = matched_assignments[idx]
        else:
            while True:
                candidate_pk = f"{audit_id}-F{counter:02d}"
                counter += 1
                if candidate_pk not in used_ids:
                    used_ids.add(candidate_pk)
                    finding_pk = candidate_pk
                    break
            r_state = f.get("review_state", "open")
            d_note = ""

        finding_rows.append(
            (
                finding_pk,
                audit_id,
                f["pillar"],
                f["issue_type"],
                f["severity"],
                f["flagged_text"],
                f["paragraph_ref"],
                int(f["start_index"]),
                int(f["end_index"]),
                f["rule_or_fact_id"],
                f["source_evidence"],
                f["explanation"],
                f.get("suggested_correction") or "",
                f["detection_method"],
                f["engine_source"],
                f.get("similarity_score"),
                r_state,
                d_note,
                now,
            )
        )

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM findings WHERE audit_id = ?", (audit_id,))
        if finding_rows:
            cur.executemany(
                """
                INSERT INTO findings (
                    id, audit_id, pillar, issue_type, severity, flagged_text,
                    paragraph_ref, start_index, end_index, rule_or_fact_id,
                    source_evidence, explanation, suggested_correction,
                    detection_method, engine_source, similarity_score,
                    review_state, decision_note, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                finding_rows,
            )

        cur.execute(
            """
            UPDATE audits
            SET brand_version = ?, pillar_states_json = ?, runtime_ms = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                int(vault["brand"].get("version", 1)),
                json.dumps(audit_output["pillar_states"]),
                float(audit_output.get("runtime_ms", 0.0)),
                now,
                audit_id,
            ),
        )

        record_audit_event(
            cur,
            audit_id,
            "audit_rerun",
            configured_user_name(),
            role,
            f"Audit rerun completed with {len(audit_output['findings'])} finding(s).",
            {
                "findings_count": len(audit_output["findings"]),
                "brand_version": vault["brand"].get("version", 1),
                "pillar_states": audit_output["pillar_states"],
            },
            None,
            now,
        )

    return get_audit_detail(audit_id)


# ============================================================================
# GUIDELINE AMBIGUITY RADAR (BASELINE TELEMETRY & RECOMMENDATIONS)
# ============================================================================

class ProposeGuidelineRevisionRequest(BaseModel):
    new_text: Optional[str] = None
    do_examples: Optional[List[Dict[str, Any]]] = None
    dont_examples: Optional[List[Dict[str, Any]]] = None


class RejectGuidelineRevisionRequest(BaseModel):
    reason: str = "Rejected during Brand Administrator review."


class HeatmapInspectUpdateRequest(BaseModel):
    grid_size: int = 4
    logo_only: bool = False
    logo_rect: Optional[Dict[str, Any]] = None
    text_regions: Optional[List[Dict[str, Any]]] = None


def _compute_rule_loop_closure(
    cur,
    brand_id: str,
    rule_id: str,
    latest_approved: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """B5: Loop closure computed ONLY from audits created after the revision's decided_at timestamp."""
    if not latest_approved:
        return None
    decided_at = str(latest_approved.get("decided_at") or "").strip()
    if not decided_at:
        return None
    rev_date = decided_at[:10]

    cur.execute(
        "SELECT id FROM audits WHERE brand_id = ? AND created_at > ? ORDER BY created_at ASC",
        (brand_id, decided_at),
    )
    post_audits = [str(r["id"]) for r in cur.fetchall()]
    post_audits_cnt = len(post_audits)

    if post_audits_cnt == 0:
        return {
            "revision_id": latest_approved["id"],
            "revised_at": decided_at,
            "revised_date": rev_date,
            "post_revision_audits_count": 0,
            "post_revision_violations": 0,
            "post_revision_overrides": 0,
            "override_rate_since_revision": None,
            "display": f"Revised {rev_date}; override rate since revision: — (no audits since revision)",
        }

    placeholders = ",".join("?" for _ in post_audits)
    cur.execute(
        f"SELECT COUNT(*) AS cnt FROM findings WHERE audit_id IN ({placeholders}) AND rule_or_fact_id LIKE ?",
        (*post_audits, f"%{rule_id}%"),
    )
    post_v = int(cur.fetchone()["cnt"] or 0)

    cur.execute(
        f"SELECT COUNT(*) AS cnt FROM guideline_feedback WHERE brand_id = ? AND rule_id = ? AND audit_id IN ({placeholders}) AND created_at > ?",
        (brand_id, rule_id, *post_audits, decided_at),
    )
    post_o = int(cur.fetchone()["cnt"] or 0)

    if post_v == 0 and post_o == 0:
        rate_val = 0.0
        disp = f"Revised {rev_date}; override rate since revision: 0.0% across {post_audits_cnt} audit(s)"
    else:
        denom = max(post_v, post_o, 1)
        rate_val = round((float(post_o) / float(denom)) * 100.0, 1)
        disp = f"Revised {rev_date}; override rate since revision: {rate_val}% ({post_o}/{denom} findings across {post_audits_cnt} audit(s))"

    return {
        "revision_id": latest_approved["id"],
        "revised_at": decided_at,
        "revised_date": rev_date,
        "post_revision_audits_count": post_audits_cnt,
        "post_revision_violations": post_v,
        "post_revision_overrides": post_o,
        "override_rate_since_revision": rate_val,
        "display": disp,
    }


def _hydrate_revision_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row_dict)
    for k in ("do_examples", "dont_examples"):
        raw = out.get(k)
        if isinstance(raw, str):
            try:
                out[k] = json.loads(raw)
            except Exception:
                out[k] = []
        elif not isinstance(raw, list):
            out[k] = []
    return out


@app.get("/api/ambiguity-radar/{brand_id}")
def get_ambiguity_radar(brand_id: str, min_sample: Optional[int] = None):
    vault = get_brand_vault_bundle(brand_id)
    effective_min_sample = (
        int(min_sample)
        if min_sample is not None
        else int(os.environ.get("LOOMSHIELD_AMBIGUITY_MIN_SAMPLE", "5"))
    )
    effective_min_sample = max(1, effective_min_sample)

    lexicon = load_vague_lexicon()
    conn = get_connection()
    cur = conn.cursor()

    DEMO_EXTRA_AUDIT_IDS = ("AUD-1003", "AUD-1004", "AUD-1005", "AUD-1006")
    demo_filter = "" if is_demo_mode() else f" AND id NOT IN {DEMO_EXTRA_AUDIT_IDS}"
    demo_join_filter = "" if is_demo_mode() else f" AND a.id NOT IN {DEMO_EXTRA_AUDIT_IDS}"
    demo_fb_filter = "" if is_demo_mode() else f" AND audit_id NOT IN {DEMO_EXTRA_AUDIT_IDS}"

    cur.execute(f"SELECT COUNT(*) AS cnt FROM audits WHERE brand_id = ?{demo_filter}", (brand_id,))
    total_brand_audits = int(cur.fetchone()["cnt"] or 0)

    radar_rows = []
    for r in vault["rules"]:
        cur.execute(
            f"""
            SELECT f.* FROM findings f
            JOIN audits a ON f.audit_id = a.id
            WHERE a.brand_id = ? AND f.rule_or_fact_id LIKE ?{demo_join_filter}
            ORDER BY f.updated_at DESC, f.id DESC
            """,
            (brand_id, f"%{r['id']}%"),
        )
        rule_findings = [dict(x) for x in cur.fetchall()]
        v_cnt = len(rule_findings)

        cur.execute(
            f"SELECT * FROM guideline_feedback WHERE brand_id = ? AND rule_id = ?{demo_fb_filter} ORDER BY id DESC",
            (brand_id, r["id"]),
        )
        fb_rows = [dict(x) for x in cur.fetchall()]
        o_cnt = len(fb_rows)

        # B1: Deterministic ambiguity scorer (0-100) using editable lexicon + structural checks
        amb = score_rule_ambiguity(
            rule_text=str(r.get("description") or ""),
            do_example=str(r.get("do_example") or ""),
            dont_example=str(r.get("dont_example") or ""),
            lexicon=lexicon,
        )

        # B2: Correlation with override rate above minimum sample
        corr = correlate_ambiguity_and_overrides(
            ambiguity_score=amb["score"],
            is_vague=amb["is_vague"],
            audits_sample_count=total_brand_audits,
            violations_count=v_cnt,
            overrides_count=o_cnt,
            min_sample=effective_min_sample,
        )

        # B3: Candidate rewrite without ever inventing numbers
        candidate = generate_candidate_rewrite(
            rule=r,
            verified_facts=vault["verified_facts"],
            past_findings=rule_findings,
            lexicon=lexicon,
        )

        # B4 & B5: Revision history and loop closure after approval
        cur.execute(
            "SELECT * FROM guideline_revisions WHERE brand_id = ? AND rule_id = ? ORDER BY id DESC",
            (brand_id, r["id"]),
        )
        revisions = [_hydrate_revision_row(dict(x)) for x in cur.fetchall()]
        latest_approved = next((rv for rv in revisions if rv.get("status") == "approved"), None)
        loop_closure = _compute_rule_loop_closure(cur, brand_id, r["id"], latest_approved)

        vague_matches = [sp["phrase"] for sp in amb["matched_spans"]]
        potential_causes = list(amb["reasons"])
        for fb in fb_rows[:3]:
            if fb["suspected_cause"] not in potential_causes:
                potential_causes.append(fb["suspected_cause"])

        recommendation_status = (
            "Recommended for Review"
            if (o_cnt >= 2 or amb["is_vague"])
            else ("Monitor" if o_cnt == 1 else "No Action Needed")
        )

        likely_signal = (
            "Subjective qualifier & recurring overrides"
            if (o_cnt >= 2 and len(vague_matches) > 0)
            else (
                "Recurring reviewer overrides"
                if o_cnt >= 2
                else (
                    "Channel-length exception logged"
                    if o_cnt == 1
                    else ("Subjective qualifier detected" if amb["is_vague"] else "Consistent enforcement")
                )
            )
        )
        next_action = (
            "Review wording in Brand Vault"
            if recommendation_status == "Recommended for Review"
            else ("Monitor channel exceptions" if recommendation_status == "Monitor" else "Keep current rule")
        )

        suggested_clarification = (
            candidate["new_text"]
            if candidate.get("improved")
            else ""
        )

        radar_rows.append({
            "rule_id": r["id"],
            "pillar": r["pillar"],
            "title": r["title"],
            "description": r["description"],
            "do_example": r.get("do_example", ""),
            "dont_example": r.get("dont_example", ""),
            "version": r["version"],
            "violations_recorded": v_cnt,
            "overrides_recorded": o_cnt,
            "likely_signal": likely_signal,
            "next_action": next_action,
            "potential_causes": potential_causes or ["No recurring override pattern observed yet"],
            "recorded_feedback": fb_rows,
            "recommendation_status": recommendation_status,
            "suggested_clarification": suggested_clarification,
            # B1 fields
            "ambiguity_score": amb["score"],
            "ambiguity_reasons": amb["reasons"],
            "matched_spans": amb["matched_spans"],
            "ambiguity_formula": amb["formula"],
            "ambiguity_breakdown": amb["breakdown"],
            "is_vague": amb["is_vague"],
            # B2 fields
            "priority": corr["priority"],
            "priority_rank": corr["priority_rank"],
            "classification_label": corr["classification_label"],
            "override_rate": corr["override_rate"],
            "override_rate_display": corr["override_rate_display"],
            "sufficient_sample": corr["sufficient_sample"],
            "sample_audits_count": corr["sample_audits_count"],
            "min_sample_required": corr["min_sample_required"],
            # B3 fields
            "candidate_rewrite": candidate,
            # B4 & B5 fields
            "revisions": revisions,
            "latest_approved_revision": latest_approved,
            "loop_closure": loop_closure,
        })

    # B6: Sort rules by priority (High -> Medium -> Low), then descending ambiguity_score, then overrides
    radar_rows.sort(
        key=lambda item: (
            -int(item.get("priority_rank", 1)),
            -int(item.get("ambiguity_score", 0)),
            -int(item.get("overrides_recorded", 0)),
            str(item.get("rule_id", "")),
        )
    )

    conn.close()
    return {
        "brand_id": brand_id,
        "brand_version": int(vault["brand"].get("version", 1)),
        "min_sample_required": effective_min_sample,
        "sample_audits_count": total_brand_audits,
        "sample_audits_note": f"Includes {total_brand_audits} seeded sample audits" if (is_demo_mode() and total_brand_audits > 0) else "",
        "sufficient_sample": total_brand_audits >= effective_min_sample,
        "concise_info_note": "Frequent overrides are a signal to review a rule, not proof it is incorrect.",
        "honest_scope_note": (
            "Frequent overrides do not automatically prove a rule is defective; potential causes include "
            "missing channel context, legitimate exceptions, or overly broad detection patterns. "
            "All rule revisions are a suggestion for human sign-off and require explicit Brand Administrator inspection."
        ),
        "rules_analysis": radar_rows,
    }


@app.post("/api/ambiguity-radar/{brand_id}/rules/{rule_id}/propose")
def propose_guideline_revision(
    brand_id: str,
    rule_id: str,
    req: Optional[ProposeGuidelineRevisionRequest] = None,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "edit_brand_vault", "Your role is not authorized to propose guideline revisions")
    vault = get_brand_vault_bundle(brand_id)
    rule = next((r for r in vault["rules"] if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found in brand '{brand_id}'.")

    lexicon = load_vague_lexicon()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.* FROM findings f
        JOIN audits a ON f.audit_id = a.id
        WHERE a.brand_id = ? AND f.rule_or_fact_id LIKE ?
        ORDER BY f.updated_at DESC
        """,
        (brand_id, f"%{rule_id}%"),
    )
    rule_findings = [dict(x) for x in cur.fetchall()]
    conn.close()

    candidate = generate_candidate_rewrite(
        rule=rule,
        verified_facts=vault["verified_facts"],
        past_findings=rule_findings,
        lexicon=lexicon,
    )

    old_text = str(rule.get("description") or "").strip()
    before_eval = score_rule_ambiguity(
        old_text,
        str(rule.get("do_example") or ""),
        str(rule.get("dont_example") or ""),
        lexicon=lexicon,
    )

    custom_new = (req.new_text.strip() if (req and req.new_text and req.new_text.strip()) else None)
    new_text = custom_new or candidate["new_text"]
    do_ex = (req.do_examples if (req and req.do_examples is not None) else candidate["do_examples"])
    dont_ex = (req.dont_examples if (req and req.dont_examples is not None) else candidate["dont_examples"])

    primary_do = do_ex[0]["text"] if (do_ex and isinstance(do_ex[0], dict)) else (str(do_ex[0]) if do_ex else "")
    primary_dont = dont_ex[0]["text"] if (dont_ex and isinstance(dont_ex[0], dict)) else (str(dont_ex[0]) if dont_ex else "")
    after_eval = score_rule_ambiguity(new_text, primary_do, primary_dont, lexicon=lexicon)

    if after_eval["score"] >= before_eval["score"]:
        raise HTTPException(
            status_code=400,
            detail=f"no improvement found: candidate ambiguity score ({after_eval['score']}) is not strictly lower than original ({before_eval['score']}).",
        )

    now = datetime.now(timezone.utc).isoformat()
    brand_ver_before = int(vault["brand"].get("version", 1))
    creator_str = actor.get("user_name") or configured_user_name()

    with db_session() as s_conn:
        s_cur = s_conn.cursor()
        rev_id = allocate_guideline_revision_id(s_cur)
        s_cur.execute(
            """
            INSERT INTO guideline_revisions (
                id, brand_id, rule_id, old_text, new_text, do_examples, dont_examples,
                ambiguity_before, ambiguity_after, status, rejection_reason,
                created_by, created_at, decided_by, decided_at,
                brand_version_before, brand_version_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', '', ?, ?, '', '', ?, NULL)
            """,
            (
                rev_id,
                brand_id,
                rule_id,
                old_text,
                new_text,
                json.dumps(do_ex),
                json.dumps(dont_ex),
                int(before_eval["score"]),
                int(after_eval["score"]),
                creator_str,
                now,
                brand_ver_before,
            ),
        )
        s_cur.execute("SELECT * FROM guideline_revisions WHERE id = ?", (rev_id,))
        created_row = _hydrate_revision_row(dict(s_cur.fetchone()))

    return created_row


def _execute_approve_revision(
    brand_id: str,
    revision_id: str,
    actor: Dict[str, str],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    decider_name = actor.get("user_name") or configured_user_name()
    decider_role = actor["role"]
    decider_uid = actor.get("user_id") or ""

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM guideline_revisions WHERE id = ? AND (brand_id = ? OR brand_id = '')",
            (revision_id, brand_id),
        )
        rev_row = cur.fetchone()
        if not rev_row:
            raise HTTPException(status_code=404, detail=f"Guideline revision '{revision_id}' not found.")
        rev = _hydrate_revision_row(dict(rev_row))
        if rev["status"] != "proposed":
            raise HTTPException(
                status_code=409,
                detail=f"Guideline revision '{revision_id}' is already '{rev['status']}' and cannot be approved again.",
            )

        rule_id = rev["rule_id"]
        cur.execute("SELECT * FROM rules WHERE id = ? AND brand_id = ?", (rule_id, brand_id))
        r_row = cur.fetchone()
        if not r_row:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found in brand '{brand_id}'.")

        # F5: Stale-proposal guard. If the rule wording changed after this revision was proposed,
        # approving would silently overwrite a newer edit.
        current_desc = str(r_row["description"] or "").strip()
        proposed_old = str(rev.get("old_text") or "").strip()
        if current_desc != proposed_old:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Rule '{rule_id}' has changed since revision '{revision_id}' was proposed. "
                    "Reject this revision and propose a new one against the current wording."
                ),
            )

        cur.execute("SELECT version FROM brands WHERE id = ?", (brand_id,))
        b_row = cur.fetchone()
        old_brand_ver = int(b_row["version"]) if b_row else 1

        # F5: Atomic status transition. Only one caller can move a revision out of 'proposed';
        # a concurrent or repeated approval sees rowcount 0 and gets a 409 (transaction rolls back).
        cur.execute(
            """
            UPDATE guideline_revisions
            SET brand_id = ?, status = 'approved', decided_by = ?, decided_at = ?
            WHERE id = ? AND status = 'proposed'
            """,
            (brand_id, decider_name, now, revision_id),
        )
        if cur.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail=f"Guideline revision '{revision_id}' is no longer 'proposed' and cannot be approved.",
            )

        do_list = rev.get("do_examples") or []
        dont_list = rev.get("dont_examples") or []
        primary_do = do_list[0].get("text", "") if (do_list and isinstance(do_list[0], dict)) else (str(do_list[0]) if do_list else str(r_row["do_example"] or ""))
        primary_dont = dont_list[0].get("text", "") if (dont_list and isinstance(dont_list[0], dict)) else (str(dont_list[0]) if dont_list else str(r_row["dont_example"] or ""))

        cur.execute(
            """
            UPDATE rules
            SET description = ?, do_example = ?, dont_example = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND brand_id = ?
            """,
            (rev["new_text"], primary_do, primary_dont, now, rule_id, brand_id),
        )
        new_brand_ver = bump_brand_version(cur, brand_id)

        cur.execute(
            """
            UPDATE guideline_revisions
            SET brand_version_before = ?, brand_version_after = ?
            WHERE id = ? AND status = 'approved'
            """,
            (old_brand_ver, new_brand_ver, revision_id),
        )

        cur.execute(
            """
            UPDATE guideline_feedback
            SET admin_review_state = 'Resolved via Rule Revision'
            WHERE brand_id = ? AND rule_id = ?
            """,
            (brand_id, rule_id),
        )

        # Locate an audit for this brand to attach the audit_event to (ensures FK integrity on existing DBs)
        cur.execute(
            "SELECT audit_id FROM guideline_feedback WHERE brand_id = ? AND rule_id = ? ORDER BY id DESC LIMIT 1",
            (brand_id, rule_id),
        )
        fb_aud = cur.fetchone()
        target_audit_id = str(fb_aud["audit_id"]) if fb_aud else ""
        if not target_audit_id:
            cur.execute("SELECT id FROM audits WHERE brand_id = ? ORDER BY created_at DESC LIMIT 1", (brand_id,))
            any_aud = cur.fetchone()
            target_audit_id = str(any_aud["id"]) if any_aud else ""

        event_summary = (
            f"Approved guideline revision {revision_id} for {rule_id}: "
            f"ambiguity reduced from {rev['ambiguity_before']} to {rev['ambiguity_after']} "
            f"(Brand Vault v{old_brand_ver} -> v{new_brand_ver})."
        )
        event_detail = {
            "revision_id": revision_id,
            "brand_id": brand_id,
            "rule_id": rule_id,
            "old_text": rev["old_text"],
            "new_text": rev["new_text"],
            "ambiguity_before": rev["ambiguity_before"],
            "ambiguity_after": rev["ambiguity_after"],
            "brand_version_before": old_brand_ver,
            "brand_version_after": new_brand_ver,
        }
        if target_audit_id:
            record_audit_event(
                cur,
                target_audit_id,
                "guideline_revision_approved",
                decider_name,
                decider_role,
                event_summary,
                event_detail,
                new_brand_ver,
                now,
                actor_user_id=decider_uid,
            )

        cur.execute("SELECT * FROM guideline_revisions WHERE id = ?", (revision_id,))
        updated_rev = _hydrate_revision_row(dict(cur.fetchone()))

    return {
        "status": "approved",
        "revision": updated_rev,
        "brand_version_before": old_brand_ver,
        "brand_version_after": new_brand_ver,
        "audit_event": {
            "audit_id": target_audit_id or f"VAULT-{brand_id}",
            "event_type": "guideline_revision_approved",
            "actor_name": decider_name,
            "actor_role": decider_role,
            "summary": event_summary,
            "detail": event_detail,
            "created_at": now,
        },
    }


@app.post("/api/ambiguity-radar/{brand_id}/revisions/{revision_id}/approve")
def approve_guideline_revision(
    brand_id: str,
    revision_id: str,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "edit_brand_vault", "Your role is not authorized to approve guideline revisions")
    return _execute_approve_revision(brand_id, revision_id, actor)


@app.post("/api/ambiguity-radar/{brand_id}/rules/{rule_id}/approve")
def propose_and_approve_guideline_revision(
    brand_id: str,
    rule_id: str,
    req: Optional[ProposeGuidelineRevisionRequest] = None,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "edit_brand_vault", "Your role is not authorized to approve guideline revisions")
    proposed = propose_guideline_revision(brand_id=brand_id, rule_id=rule_id, req=req, actor=actor)
    return _execute_approve_revision(brand_id, proposed["id"], actor)


@app.post("/api/ambiguity-radar/{brand_id}/revisions/{revision_id}/reject")
def reject_guideline_revision(
    brand_id: str,
    revision_id: str,
    req: Optional[RejectGuidelineRevisionRequest] = None,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "edit_brand_vault", "Your role is not authorized to reject guideline revisions")
    reason_str = (req.reason.strip() if (req and req.reason and req.reason.strip()) else "Rejected during Brand Administrator review.")
    now = datetime.now(timezone.utc).isoformat()
    decider_name = actor.get("user_name") or configured_user_name()

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM guideline_revisions WHERE id = ? AND (brand_id = ? OR brand_id = '')",
            (revision_id, brand_id),
        )
        rev_row = cur.fetchone()
        if not rev_row:
            raise HTTPException(status_code=404, detail=f"Guideline revision '{revision_id}' not found.")
        rev = _hydrate_revision_row(dict(rev_row))
        if rev["status"] != "proposed":
            raise HTTPException(
                status_code=409,
                detail=f"Guideline revision '{revision_id}' is already '{rev['status']}'.",
            )

        cur.execute("SELECT version FROM brands WHERE id = ?", (brand_id,))
        b_row = cur.fetchone()
        curr_brand_ver = int(b_row["version"]) if b_row else int(rev.get("brand_version_before") or 1)

        cur.execute(
            """
            UPDATE guideline_revisions
            SET brand_id = ?, status = 'rejected', rejection_reason = ?, decided_by = ?, decided_at = ?,
                brand_version_after = ?
            WHERE id = ? AND status = 'proposed'
            """,
            (brand_id, reason_str, decider_name, now, curr_brand_ver, revision_id),
        )
        if cur.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail=f"Guideline revision '{revision_id}' is no longer 'proposed' and cannot be rejected.",
            )
        cur.execute("SELECT * FROM guideline_revisions WHERE id = ?", (revision_id,))
        updated_rev = _hydrate_revision_row(dict(cur.fetchone()))

    return {
        "status": "rejected",
        "revision": updated_rev,
        "brand_version_before": curr_brand_ver,
        "brand_version_after": curr_brand_ver,
        "rejection_reason": reason_str,
    }


@app.post("/api/audits/{audit_id}/heatmap")
def update_audit_heatmap_inspector(
    request: Request,
    audit_id: str,
    req: HeatmapInspectUpdateRequest,
    actor: Dict[str, str] = Depends(current_actor),
):
    require_permission(actor["role"], "run_audits", "Your role is not authorized to run heatmap inspections")
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before running another inspection.")
    detail = get_audit_detail(audit_id)
    vault = get_brand_vault_bundle(detail["brand_id"])

    asset_b64 = str(detail.get("visual_asset_b64") or "")
    raw_bytes = b""
    fname = detail.get("document_name") or f"asset.{detail.get('input_format', 'png')}"

    if asset_b64 and "," in asset_b64:
        try:
            raw_bytes = base64.b64decode(asset_b64.split(",", 1)[1])
        except Exception:
            raw_bytes = b""
    elif detail.get("input_format") == "svg" and detail.get("visual_metadata", {}).get("sanitized_svg"):
        raw_bytes = str(detail["visual_metadata"]["sanitized_svg"]).encode("utf-8")

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="No visual raster or SVG asset is stored on this audit for heatmap inspection.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds the 5 MB safety limit.")

    hm_vis = inspect_visual_heatmap(
        raw_bytes=raw_bytes,
        brand_colors=vault["colors"],
        brand=vault["brand"],
        filename=fname,
        grid_size=req.grid_size,
        logo_only=req.logo_only,
        logo_rect=req.logo_rect,
        text_regions=req.text_regions,
    )
    if hm_vis.get("too_large"):
        raise HTTPException(status_code=400, detail=hm_vis.get("error", "Image exceeds the 25 megapixel limit."))
    old_meta = detail.get("visual_metadata") or {}
    for k in ("swatches", "off_palette_swatches", "has_transparency", "all_transparent", "limitation_note"):
        if k in old_meta and k not in hm_vis:
            hm_vis[k] = old_meta[k]

    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE audits SET visual_metadata_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(hm_vis), now, audit_id),
        )

    return {
        "audit_id": audit_id,
        "heatmap": hm_vis,
        "audit": get_audit_detail(audit_id),
    }


# F3: The standalone POST /api/heatmap/inspect route was removed. The UI never called it (heatmap
# inspection runs through POST /api/audits/upload and POST /api/audits/{audit_id}/heatmap), and it had
# no permission check or rate limit.
# F11: _legacy_get_ambiguity_radar_unused was deleted (superseded by get_ambiguity_radar).


# ============================================================================
# STATIC FRONTEND MOUNT
# ============================================================================

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
FONTS_DIR = os.path.join(FRONTEND_DIR, "fonts")
if os.path.exists(FONTS_DIR):
    app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_workspace():
    idx = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(idx):
        return FileResponse(idx)
    return {"service": "LoomShield API", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
def get_favicon_ico():
    fav = os.path.join(FRONTEND_DIR, "favicon.ico")
    if os.path.exists(fav):
        return FileResponse(fav, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.ico not found")


@app.get("/favicon.svg", include_in_schema=False)
def get_favicon_svg():
    fav = os.path.join(FRONTEND_DIR, "favicon.svg")
    if os.path.exists(fav):
        return FileResponse(fav, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="favicon.svg not found")


@app.get("/apple-touch-icon.png", include_in_schema=False)
def get_apple_touch_icon():
    fav = os.path.join(FRONTEND_DIR, "apple-touch-icon.png")
    if os.path.exists(fav):
        return FileResponse(fav, media_type="image/png")
    raise HTTPException(status_code=404, detail="apple-touch-icon.png not found")
