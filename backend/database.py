import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
import contextvars
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "loomshield.db")
DEMO_DB_PATH = os.path.join(os.path.dirname(__file__), "loomshield_demo.db")


def _is_demo_mode() -> bool:
    return os.environ.get("LOOMSHIELD_WORKSPACE_MODE", "production").strip().lower() == "demo"


def _should_seed_workspace() -> bool:
    return _is_demo_mode() or "test" in os.path.basename(get_db_path()).lower() or bool(os.environ.get("PYTEST_CURRENT_TEST"))


_SESSION_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("loomshield_session_id", default=None)


def set_current_session_id(session_id: Optional[str]) -> None:
    """Set the active per-visitor session identifier for SQLite isolation."""
    _SESSION_ID_CTX.set(session_id)


def get_current_session_id() -> Optional[str]:
    """Get the active per-visitor session identifier."""
    return _SESSION_ID_CTX.get()


def _init_isolated_session_db(sess_db_path: str) -> None:
    """Initialize an isolated per-visitor demo database with complete tables and sample workspace."""
    conn = sqlite3.connect(sess_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn=conn)
    conn.close()


def get_db_path(session_id: Optional[str] = None) -> str:
    """Production and the sample (demo) workspace always use separate database files.
    
    In demo workspace mode, requests carrying a visitor session ID (via X-LoomShield-Session
    or session_id query param) are dynamically routed to isolated session databases.
    """
    target_sess = session_id or get_current_session_id()
    if target_sess and (_is_demo_mode() or bool(os.environ.get("PYTEST_CURRENT_TEST"))):
        safe_sess = re.sub(r"[^a-zA-Z0-9_\-]", "", target_sess)[:64]
        if safe_sess:
            override = os.environ.get("LOOMSHIELD_DB_PATH")
            base_dir = os.path.dirname(override) if override else os.path.join(os.path.dirname(__file__), "sessions")
            os.makedirs(base_dir, exist_ok=True)
            sess_db = os.path.join(base_dir, f"sess_{safe_sess}.db")
            if not os.path.exists(sess_db):
                _init_isolated_session_db(sess_db)
            return sess_db

    override = os.environ.get("LOOMSHIELD_DB_PATH")
    if override:
        return override

    return DEMO_DB_PATH if _is_demo_mode() else DB_PATH


def get_connection(session_id: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(session_id=session_id))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections ensuring transactional integrity with BEGIN IMMEDIATE."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bump_brand_version(cur: sqlite3.Cursor, brand_id: str) -> int:
    """Increment brand version by 1 and update updated_at timestamp atomically."""
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "UPDATE brands SET version = version + 1, updated_at = ? WHERE id = ?",
        (now, brand_id),
    )
    cur.execute("SELECT version FROM brands WHERE id = ?", (brand_id,))
    row = cur.fetchone()
    return int(row["version"]) if row else 1


def allocate_audit_id(cur: sqlite3.Cursor) -> str:
    """Allocate next AUD-XXXX ID sequentially inside the transaction."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) AS max_id FROM audits WHERE id LIKE 'AUD-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 1000) + 1 if row else 1001
    return f"AUD-{next_num}"


def allocate_rule_id(cur: sqlite3.Cursor, brand_id: str = "") -> str:
    """Allocate next monotonic RULE-CUSTOM-XXX ID."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 13) AS INTEGER)) AS max_id FROM rules WHERE id LIKE 'RULE-CUSTOM-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 0) + 1 if row else 1
    return f"RULE-CUSTOM-{next_num:03d}"


def allocate_term_id(cur: sqlite3.Cursor, brand_id: str = "") -> str:
    """Allocate next monotonic TERM-CUSTOM-XXX ID."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 13) AS INTEGER)) AS max_id FROM terminology WHERE id LIKE 'TERM-CUSTOM-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 0) + 1 if row else 1
    return f"TERM-CUSTOM-{next_num:03d}"


def allocate_fact_id(cur: sqlite3.Cursor, brand_id: str = "") -> str:
    """Allocate next monotonic FACT-CUSTOM-XXX ID."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 13) AS INTEGER)) AS max_id FROM verified_facts WHERE id LIKE 'FACT-CUSTOM-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 0) + 1 if row else 1
    return f"FACT-CUSTOM-{next_num:03d}"


def allocate_color_id(cur: sqlite3.Cursor, brand_id: str = "") -> str:
    """Allocate next monotonic CLR-CUSTOM-XXX ID."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 12) AS INTEGER)) AS max_id FROM brand_colors WHERE id LIKE 'CLR-CUSTOM-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 0) + 1 if row else 1
    return f"CLR-CUSTOM-{next_num:03d}"


def allocate_certificate_id(cur: sqlite3.Cursor) -> str:
    """Allocate next monotonic CERT-XXXX ID sequentially inside the transaction."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) AS max_id FROM certificates WHERE id LIKE 'CERT-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 1000) + 1 if row else 1001
    return f"CERT-{next_num}"


def allocate_guideline_revision_id(cur: sqlite3.Cursor) -> str:
    """Allocate next monotonic GREV-XXXX ID sequentially inside the transaction."""
    cur.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) AS max_id FROM guideline_revisions WHERE id LIKE 'GREV-%'")
    row = cur.fetchone()
    next_num = (row["max_id"] or 1000) + 1 if row else 1001
    return f"GREV-{next_num}"


def _ensure_column(cur: sqlite3.Cursor, table: str, column: str, col_def: str) -> None:
    """Idempotent migration helper: add column to table if it does not already exist."""
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")



def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS brands (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT NOT NULL,
            description TEXT NOT NULL,
            tone_principles TEXT NOT NULL,
            writing_style TEXT NOT NULL,
            messaging_principles TEXT NOT NULL,
            do_examples TEXT NOT NULL,
            dont_examples TEXT NOT NULL,
            typography_specs TEXT NOT NULL,
            spacing_rules TEXT NOT NULL,
            logo_placement_constraints TEXT NOT NULL,
            min_contrast_normal REAL DEFAULT 4.5,
            min_contrast_large REAL DEFAULT 3.0,
            require_alt_text INTEGER DEFAULT 1,
            enforce_heading_order INTEGER DEFAULT 1,
            target_reading_ease REAL DEFAULT 50.0,
            version INTEGER DEFAULT 1,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            pillar TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            rule_config_json TEXT NOT NULL,
            severity TEXT NOT NULL,
            do_example TEXT DEFAULT '',
            dont_example TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            version INTEGER DEFAULT 1,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS terminology (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            preferred_term TEXT NOT NULL,
            prohibited_term TEXT NOT NULL,
            replacement_term TEXT NOT NULL,
            case_sensitive INTEGER DEFAULT 0,
            notes TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS verified_facts (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            statement TEXT NOT NULL,
            numeric_value TEXT DEFAULT '',
            numeric_units TEXT DEFAULT '',
            product_context TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            applicable_conditions TEXT NOT NULL,
            date_version TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'Verified',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS brand_colors (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            name TEXT NOT NULL,
            hex_code TEXT NOT NULL,
            usage_role TEXT NOT NULL,
            max_delta_e REAL DEFAULT 14.0,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audits (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            brand_version INTEGER NOT NULL,
            document_name TEXT NOT NULL,
            input_format TEXT NOT NULL,
            original_content TEXT NOT NULL,
            current_content TEXT NOT NULL,
            fg_color TEXT DEFAULT '',
            bg_color TEXT DEFAULT '',
            image_alt_text TEXT DEFAULT '',
            has_visual_asset INTEGER DEFAULT 0,
            visual_metadata_json TEXT DEFAULT '{}',
            confidential_mode INTEGER DEFAULT 1,
            overall_status TEXT NOT NULL DEFAULT 'Draft',
            assigned_reviewer TEXT DEFAULT 'Editorial & Brand Reviewer',
            pillar_states_json TEXT NOT NULL DEFAULT '{}',
            runtime_ms REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL,
            pillar TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            flagged_text TEXT NOT NULL,
            paragraph_ref TEXT DEFAULT 'P1',
            start_index INTEGER DEFAULT -1,
            end_index INTEGER DEFAULT -1,
            rule_or_fact_id TEXT NOT NULL,
            source_evidence TEXT NOT NULL,
            explanation TEXT NOT NULL,
            suggested_correction TEXT DEFAULT '',
            detection_method TEXT NOT NULL,
            engine_source TEXT NOT NULL,
            similarity_score REAL DEFAULT NULL,
            review_state TEXT NOT NULL DEFAULT 'open',
            decision_note TEXT DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            previous_content TEXT NOT NULL,
            revised_content TEXT NOT NULL,
            editor_role TEXT NOT NULL,
            change_summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS review_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            finding_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            replacement_applied TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            reviewer_role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            approver_role TEXT NOT NULL,
            version_reviewed INTEGER NOT NULL,
            unresolved_findings_count INTEGER NOT NULL,
            override_acknowledged INTEGER DEFAULT 0,
            comment TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS guideline_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            audit_id TEXT NOT NULL,
            finding_id TEXT NOT NULL,
            override_reason TEXT NOT NULL,
            suspected_cause TEXT NOT NULL DEFAULT 'Needs Administrative Review',
            admin_review_state TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_name TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            actor_user_id TEXT DEFAULT '',
            summary TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            version_number INTEGER DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            signature TEXT NOT NULL,
            kid TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            issued_by TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS demo_users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initials TEXT NOT NULL,
            role TEXT NOT NULL,
            title TEXT NOT NULL
        );
        """
    )

    # Idempotent schema migrations for existing SQLite files
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guideline_revisions (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL DEFAULT '',
            rule_id TEXT NOT NULL,
            old_text TEXT NOT NULL,
            new_text TEXT NOT NULL,
            do_examples TEXT NOT NULL DEFAULT '[]',
            dont_examples TEXT NOT NULL DEFAULT '[]',
            ambiguity_before INTEGER NOT NULL DEFAULT 0,
            ambiguity_after INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'proposed',
            rejection_reason TEXT DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            decided_by TEXT DEFAULT '',
            decided_at TEXT DEFAULT '',
            brand_version_before INTEGER DEFAULT 1,
            brand_version_after INTEGER DEFAULT NULL
        )
        """
    )
    _ensure_column(cur, "brands", "min_clear_space_ratio", "REAL DEFAULT 0.25")
    _ensure_column(cur, "brands", "min_clear_space_px", "INTEGER DEFAULT 16")
    _ensure_column(cur, "brands", "approved_logo_b64", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_format", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_filename", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_updated_at", "TEXT DEFAULT ''")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS certificate_revocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id TEXT NOT NULL UNIQUE,
            audit_id TEXT NOT NULL,
            brand_id TEXT NOT NULL,
            revoked_by TEXT NOT NULL,
            revoked_by_user_id TEXT DEFAULT '',
            revocation_reason TEXT NOT NULL,
            revoked_at TEXT NOT NULL
        );
        """
    )
    _ensure_column(cur, "audits", "visual_asset_b64", "TEXT DEFAULT ''")
    _ensure_column(cur, "audits", "submitted_by_user_id", "TEXT DEFAULT ''")
    _ensure_column(cur, "audits", "submitted_by_name", "TEXT DEFAULT ''")
    _ensure_column(cur, "approvals", "approver_user_id", "TEXT DEFAULT ''")
    _ensure_column(cur, "approvals", "approver_name", "TEXT DEFAULT ''")
    _ensure_column(cur, "audit_events", "actor_user_id", "TEXT DEFAULT ''")

    # G5: Ensure every finding detection_method strictly reflects its underlying detection tier:
    # Tier 1: regex, dictionary, math, image formats
    # Tier 2: TF-IDF retrieval, polarity classifier, administrative status
    # Tier 1 + Tier 2: superlative pattern + TF-IDF retrieval / vault search
    cur.execute(
        """
        UPDATE findings
        SET detection_method = CASE
            WHEN detection_method LIKE '%Superlative Pattern%' THEN 'Tier 1 + Tier 2: ' || REPLACE(REPLACE(REPLACE(detection_method, 'Tier 1 + Tier 2: ', ''), 'Tier 1: ', ''), 'Tier 2: ', '')
            WHEN detection_method LIKE '%NLP%' OR detection_method LIKE '%Polarity%' OR detection_method LIKE '%TF-IDF%' OR detection_method LIKE '%Messaging Principle%' OR detection_method LIKE '%Administrative Status%' THEN 'Tier 2: ' || REPLACE(REPLACE(REPLACE(detection_method, 'Tier 1 + Tier 2: ', ''), 'Tier 1: ', ''), 'Tier 2: ', '')
            ELSE 'Tier 1: ' || REPLACE(REPLACE(REPLACE(detection_method, 'Tier 1 + Tier 2: ', ''), 'Tier 1: ', ''), 'Tier 2: ', '')
        END
        WHERE (detection_method NOT LIKE 'Tier 1: %' AND detection_method NOT LIKE 'Tier 2: %' AND detection_method NOT LIKE 'Tier 1 + Tier 2: %')
           OR detection_method LIKE 'Tier 1: Configured Tone Pattern%'
           OR detection_method LIKE 'Tier 2: Superlative Pattern%'
           OR detection_method LIKE 'Tier 1: Superlative Pattern%'
        """
    )

    # Ensure demo_users are seeded when in demo or test workspace
    if _should_seed_workspace():
        cur.executemany(
            """
            INSERT OR REPLACE INTO demo_users (user_id, name, initials, role, title)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("usr_priya", "Priya Nair", "PN", "Content Creator", "Product Marketing Writer"),
                ("usr_marcus", "Marcus Lee", "ML", "Reviewer", "Editorial & Brand Reviewer"),
                ("usr_ava", "Ava Chen", "AC", "Brand Administrator", "Head of Brand Governance"),
            ],
        )

    # G1: A fresh clone creates and seeds the default Brand Vault workspace on first start in demo and production mode.
    cur.execute("SELECT COUNT(*) AS cnt FROM brands")
    if cur.fetchone()["cnt"] == 0:
        if not restore_database_snapshot(conn=conn):
            seed_default_workspace(cur)
    if _is_demo_mode():
        # F6: idempotent top-up of demo-only sample data (INSERT OR IGNORE).
        ensure_demo_sample_data(cur)

    conn.commit()
    if should_close:
        conn.close()


def record_audit_event(
    cur: sqlite3.Cursor,
    audit_id: str,
    event_type: str,
    actor_name: str,
    actor_role: str,
    summary: str,
    detail: dict = None,
    version_number: int = None,
    created_at: str = None,
    actor_user_id: str = "",
) -> None:
    cur.execute(
        """
        INSERT INTO audit_events
        (audit_id, event_type, actor_name, actor_role, actor_user_id, summary, detail_json, version_number, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            event_type,
            actor_name,
            actor_role,
            actor_user_id or "",
            summary,
            json.dumps(detail or {}),
            version_number,
            created_at or datetime.now(timezone.utc).isoformat(),
        ),
    )


def seed_default_workspace(cur: sqlite3.Cursor) -> None:
    now = datetime.now(timezone.utc).isoformat()

    # 1. Seed Brands
    brands = [
        (
            "novapay",
            "NovaPay Enterprise",
            "B2B Treasury & Cross-Border Settlement",
            "Institutional settlement and treasury automation platform for regulated enterprises.",
            "Calm, evidence-backed, precise, and transparent. Avoid alarmist urgency, panic-inducing claims, or unverified superlatives.",
            "Use clear active prose. Define technical terms on first use. Keep sentences direct and accessible.",
            "Every automation claim must acknowledge configurable human approval controls and institutional compliance boundaries.",
            json.dumps([
                "NovaPay Core delivers up to 64% faster settlement under the conditions stated in the Q3 benchmark report.",
                "Automate recurring vendor payouts with role-based CFO sign-off above configured thresholds."
            ]),
            json.dumps([
                "Our platform guarantees 95% faster processing with zero latency!",
                "Legacy banks are destroying your margins—fire your finance ops team today!"
            ]),
            "Primary UI & Headings: Inter / Geist (600-700 weight). Body: Inter (400-500 weight, 14-16px).",
            "Maintain minimum 16px clear space around the primary wordmark on digital banners and 8px base grid alignment.",
            "Place primary wordmark in top-left or bottom-left lockup zones; never stretch, skew, or place over low-contrast busy imagery.",
            4.5,
            3.0,
            1,
            1,
            50.0,
            2,
            now,
        ),
        (
            "verdant",
            "Verdant Clinical Systems",
            "Healthcare Diagnostic Decision Support",
            "Clinician-assisted radiology triage and workflow prioritization software.",
            "Empathetic, clinically objective, cautious, and human-centered. Never imply autonomous medical diagnosis.",
            "Plain clinical English with explicit study citations and sample conditions.",
            "Always emphasize that software outputs assist board-certified clinicians rather than replacing medical judgment.",
            json.dumps([
                "Verdant Triage Assist demonstrated 94.2% sensitivity in assisting radiologists across 18,400 chest radiographs."
            ]),
            json.dumps([
                "Verdant AI guarantees 100% diagnostic accuracy and replaces radiologists."
            ]),
            "Headings: Inter SemiBold. Body: Inter Regular (minimum 14px).",
            "Minimum clear space equal to the cap-height of the 'V' mark around all sides.",
            "Use horizontal lockup on clinical reports; never overlay on low-contrast scan regions.",
            4.5,
            3.0,
            1,
            1,
            55.0,
            1,
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO brands (
            id, name, industry, description, tone_principles, writing_style,
            messaging_principles, do_examples, dont_examples, typography_specs,
            spacing_rules, logo_placement_constraints, min_contrast_normal,
            min_contrast_large, require_alt_text, enforce_heading_order,
            target_reading_ease, version, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        brands,
    )

    # 2. Seed Brand Rules
    rules = [
        (
            "RULE-TONE-01",
            "novapay",
            "Tone and Voice",
            "Prohibit Alarmist or Fear-Mongering Language",
            "Marketing content must not use alarmist phrasing, panic-inducing rhetoric, or sensationalist exclamations to pressure buyers.",
            json.dumps({
                "patterns": [
                    r"Stop\s+Legacy\s+Banks\s+From\s+Destroying\s+Your\s+Treasury!?",
                    r"Are\s+slow\s+wire\s+transfers\s+killing\s+your\s+quarter\?",
                    r"\b(?:destroying\s+your\s+margins|secretly\s+destroying|before\s+your\s+treasury\s+collapses)\b"
                ],
                "suggested_replacements": {
                    "Stop Legacy Banks From Destroying Your Treasury!": "Modernize Cross-Border Treasury Operations with Predictable Settlement.",
                    "Are slow wire transfers killing your quarter?": "Are correspondent wire delays affecting quarterly cash-flow predictability?"
                }
            }),
            "high",
            "Modernize cross-border treasury operations with predictable settlement timelines.",
            "Stop Legacy Banks From Destroying Your Treasury!",
            1,
            2,
            now,
        ),
        (
            "RULE-TONE-02",
            "novapay",
            "Tone and Voice",
            "Use an Appropriate Amount of Technical Detail",
            "Use an appropriate amount of technical detail when explaining treasury APIs and settlement workflows.",
            json.dumps({
                "patterns": [r"\b(?:slaps\s+hard|crushes\s+legacy\s+wires|crypto-bro)\b"],
                "note": "Frequently overridden when writers balance developer vs executive tone."
            }),
            "medium",
            "Explain the primary business benefit in plain language before introducing ISO 20022 message specifications.",
            "Yo CFOs, our payout API slaps hard and crushes legacy wires.",
            1,
            1,
            now,
        ),
        (
            "RULE-TERM-01",
            "novapay",
            "Terminology",
            "Enforce Approved Product Naming, Capitalization & Prohibited Terms",
            "Use approved product names ('NovaPay Core', 'NovaPay') and avoid deprecated names ('NovaWallet') or prohibited buzzwords ('unhackable', 'blitz-scale', 'synergy').",
            json.dumps({"source": "terminology_table"}),
            "high",
            "Connect your ERP directly to NovaPay Core for SOC 2 Type II certified settlement.",
            "Use Novapay NovaWallet to blitz-scale your unhackable payment synergy.",
            1,
            2,
            now,
        ),
        (
            "RULE-MSG-01",
            "novapay",
            "Messaging",
            "Pair Automation Messaging with Human Approval Controls",
            "Content must not claim that autonomous AI replaces finance teams or operates without human oversight. Emphasize configurable human approval workflows.",
            json.dumps({
                "prohibited_patterns": [
                    r"fire\s+your\s+finance\s+ops\s+team\s+and\s+let\s+autonomous\s+AI\s+run\s+every\s+wire\s+without\s+human\s+intervention",
                    r"\b(?:zero\s+human\s+oversight|without\s+human\s+intervention|replace\s+your\s+finance\s+team)\b"
                ],
                "replacement": "equip your finance operations team with automated routing and configurable role-based approval controls"
            }),
            "high",
            "Equip your finance operations team with automated routing and configurable role-based approval controls.",
            "Fire your finance ops team and let autonomous AI run every wire without human intervention.",
            1,
            2,
            now,
        ),
        (
            "RULE-CLAIM-01",
            "novapay",
            "Promotional Claims",
            "Substantiate Promotional, Superlative & Numerical Claims Against Verified Facts",
            "All numerical claims, speed comparisons, uptime figures, and fee statements must match a Verified Fact in the Brand Vault and include applicable conditions. Unsupported superlatives ('#1 in the world', '100% guaranteed') are prohibited.",
            json.dumps({"source": "verified_facts_and_claim_engine"}),
            "critical",
            "Our platform delivers up to 64% faster processing under the conditions stated in the approved performance report.",
            "Our platform guarantees 95% faster processing with 100% guaranteed savings.",
            1,
            2,
            now,
        ),
        (
            "RULE-VIS-01",
            "novapay",
            "Visual and Logo Consistency",
            "Approved Brand Colour Palette & Clear-Space Specifications",
            "Visual assets and configured text/surface colours must align with approved NovaPay hexadecimal colours within CIE Delta-E <= 14.0 and preserve minimum 16px logo clear space.",
            json.dumps({"max_delta_e": 14.0, "min_clear_space_px": 16}),
            "medium",
            "Primary Charcoal #17191C on #FFFFFF surface with #EA633F accent.",
            "Off-brand neon magenta #FF00FF or unapproved lime backgrounds.",
            1,
            1,
            now,
        ),
        (
            "RULE-A11Y-01",
            "novapay",
            "Accessibility",
            "WCAG 2.1 AA Contrast, Heading Hierarchy & Alternative Text",
            "Normal text must achieve at least 4.5:1 contrast ratio (3.0:1 for large text), HTML documents must not skip heading levels, and visual assets require descriptive alternative text.",
            json.dumps({"min_contrast_normal": 4.5, "min_contrast_large": 3.0}),
            "high",
            "Foreground #202124 on #FFFFFF (16.1:1 contrast) with sequential H1->H2 headings and descriptive alt-text.",
            "Low-contrast #94A3B8 text on #FFFFFF (2.56:1 contrast) or missing alt attributes.",
            1,
            1,
            now,
        ),
        (
            "RULE-VER-CLAIM-01",
            "verdant",
            "Promotional Claims",
            "Clinical Sensitivity & Non-Autonomous Framing",
            "All clinical performance claims must cite the multi-site validation study and state clinician-assisted operation.",
            json.dumps({"source": "verified_facts_and_claim_engine"}),
            "critical",
            "Verdant Triage Assist achieved 94.2% sensitivity in assisting radiologists under the validated study protocol.",
            "Verdant AI guarantees 100% diagnostic accuracy and replaces radiologists.",
            1,
            1,
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO rules (
            id, brand_id, pillar, title, description, rule_config_json,
            severity, do_example, dont_example, active, version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rules,
    )

    # 3. Seed Terminology Table
    terms = [
        (
            "TERM-01",
            "novapay",
            "NovaPay Core",
            "NovaWallet",
            "NovaPay Core",
            0,
            "'NovaWallet' is a deprecated 2024 product name; replace with 'NovaPay Core'.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-02",
            "novapay",
            "NovaPay",
            "Novapay",
            "NovaPay",
            1,
            "Brand spelling requires capital 'N' and capital 'P' ('NovaPay').",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-03",
            "novapay",
            "SOC 2 Type II certified",
            "unhackable",
            "SOC 2 Type II certified",
            0,
            "Absolute security claims ('unhackable') are prohibited by legal compliance; state actual certification.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-04",
            "novapay",
            "scale predictably",
            "blitz-scale",
            "scale predictably",
            0,
            "Avoid speculative startup slang ('blitz-scale') in enterprise treasury materials.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-05",
            "novapay",
            "operational alignment",
            "synergy",
            "operational alignment",
            0,
            "Replace vague buzzword 'synergy' with specific operational phrasing.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-06",
            "novapay",
            "Local Governance Engine",
            "AI Engine",
            "Local Governance Engine",
            0,
            "Never refer to the deterministic + embedded NLP system as a generic 'AI Engine'; use 'Local Governance Engine'.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-07",
            "novapay",
            "streamlined operational workflow",
            "synergetic paradigm shift",
            "streamlined operational workflow",
            0,
            "Replace vague promotional buzzwords ('synergetic paradigm shift') with concrete operational terms.",
            "RULE-TERM-01",
            now,
        ),
        (
            "TERM-08",
            "verdant",
            "clinician-assisted decision support",
            "autonomous doctor",
            "clinician-assisted decision support",
            0,
            "Cleared under FDA Class II as clinician decision support, never autonomous diagnosis.",
            "RULE-VER-CLAIM-01",
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO terminology (
            id, brand_id, preferred_term, prohibited_term, replacement_term,
            case_sensitive, notes, rule_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        terms,
    )

    # 4. Seed Verified Facts Table (with explicit verification_status)
    facts = [
        (
            "FACT-101",
            "novapay",
            "Processing and cross-border settlement is up to 64% faster under the conditions stated in the approved performance report.",
            "64",
            "% faster",
            "NovaPay Core settlement & processing speed",
            "NovaPay Q3 2026 Institutional Performance Report, Section 2.4",
            "Measured across 42 supported clearing corridors compared to legacy correspondent SWIFT baselines.",
            "2026-Q3 (v2.4)",
            "Verified",
            now,
        ),
        (
            "FACT-102",
            "novapay",
            "NovaPay Core supports direct clearing in 42 currencies across 68 countries.",
            "42",
            "currencies",
            "Global currency and corridor coverage",
            "NovaPay Product Specification Sheet v4.2",
            "Requires active multi-currency treasury account configuration.",
            "2026-10 (v4.2)",
            "Verified",
            now,
        ),
        (
            "FACT-103",
            "novapay",
            "NovaPay Core provides a 99.99% contractual uptime SLA across active-active regions.",
            "99.99",
            "% uptime SLA",
            "Platform availability & reliability SLA",
            "NovaPay Master Enterprise Service Level Agreement (SLA-2026-v3)",
            "Excludes scheduled maintenance windows notified 14 days in advance.",
            "2026-09 (v3.0)",
            "Verified",
            now,
        ),
        (
            "FACT-104",
            "novapay",
            "Enterprise customers reduce cross-border FX spread costs by an average of 38 basis points (0.38%).",
            "38",
            "basis points (0.38%)",
            "Foreign exchange fee & spread reduction",
            "NovaPay 2026 Cohort Benchmark Study (n=310 enterprise treasuries)",
            "Observed across G10 and major emerging market currency pairs.",
            "2026-08 (v1.1)",
            "Verified",
            now,
        ),
        (
            "FACT-105",
            "novapay",
            "Draft preliminary internal test showing 78% reduction in manual reconciliation time.",
            "78",
            "% reduction",
            "Reconciliation automation beta",
            "Internal Unaudited Engineering Sandbox Log",
            "Small sample size (n=12); not yet approved for public marketing claims.",
            "2026-10-Draft",
            "Pending Verification",
            now,
        ),
        (
            "FACT-201",
            "verdant",
            "Verdant Triage Assist demonstrated 94.2% sensitivity in prioritizing chest radiographs under clinician review.",
            "94.2",
            "% sensitivity",
            "Chest radiograph triage sensitivity",
            "Multi-Site Clinical Validation Study NCT-094821 (2026)",
            "Validated on adult inpatient chest radiographs reviewed by board-certified radiologists.",
            "2026-07 (v1.0)",
            "Verified",
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO verified_facts (
            id, brand_id, statement, numeric_value, numeric_units, product_context,
            source_reference, applicable_conditions, date_version, verification_status,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        facts,
    )

    # 5. Seed Approved Brand Colours
    colors = [
        ("COL-01", "novapay", "Primary Charcoal", "#17191C", "Primary Brand Surface & Typography", 12.0),
        ("COL-02", "novapay", "Signal Accent Orange", "#EA633F", "Primary Interactive Accent & Highlights", 14.0),
        ("COL-03", "novapay", "Compliance Emerald", "#188568", "Verified & Passed Status", 14.0),
        ("COL-04", "novapay", "Workspace Surface", "#F7F8FA", "Light Background Surface", 10.0),
        ("COL-05", "novapay", "Institutional Slate", "#202124", "Body Copy Typography", 12.0),
        ("COL-06", "verdant", "Clinical Teal", "#188568", "Primary Clinical Accent", 14.0),
        ("COL-07", "verdant", "Deep Charcoal", "#17191C", "Primary Text", 12.0),
    ]
    cur.executemany(
        """
        INSERT INTO brand_colors (
            id, brand_id, name, hex_code, usage_role, max_delta_e
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        colors,
    )

    # G1 / G4: In production mode, seed ONLY the Brand Vault workspace (brands, colors, rules, terminology, facts).
    # Sample audits AUD-1001..AUD-1006 are strictly isolated to demo mode and test workspaces.
    if not (_is_demo_mode() or _should_seed_workspace()):
        return

    # 6. Seed Consistent Demo Audits (AUD-1001 In Review with v1->v2 revision, AUD-1002 Approved)
    import hashlib

    aud1_orig = (
        "<h2>Launch Faster with Instant Payouts</h2>\n"
        "<p>Our platform guarantees 95% faster processing for cross-border treasury teams. "
        "Using our proprietary AI Engine, finance leaders can review settlement activity across 42 currencies.</p>"
    )
    aud1_rev = (
        "<h2>Launch Faster with Instant Payouts</h2>\n"
        "<p>Our platform guarantees 95% faster processing for cross-border treasury teams. "
        "Using our proprietary Local Governance Engine, finance leaders can review settlement activity across 42 currencies.</p>"
    )
    aud1_pillars = json.dumps({
        "Tone and Voice": "Passed",
        "Terminology": "Passed",
        "Messaging": "Passed",
        "Promotional Claims": "Findings",
        "Visual and Logo Consistency": "Not Checked",
        "Accessibility": "Passed",
    })

    aud2_orig = (
        "# NovaPay Q3 Institutional Settlement Update\n\n"
        "Novapay Core delivers up to 64% faster processing across 42 currencies under the conditions stated in the approved performance report."
    )
    aud2_rev = (
        "# NovaPay Q3 Institutional Settlement Update\n\n"
        "NovaPay Core delivers up to 64% faster processing across 42 currencies under the conditions stated in the approved performance report."
    )
    aud2_pillars = json.dumps({
        "Tone and Voice": "Passed",
        "Terminology": "Passed",
        "Messaging": "Passed",
        "Promotional Claims": "Passed",
        "Visual and Logo Consistency": "Not Checked",
        "Accessibility": "Passed",
    })

    seeded_audits = [
        (
            "AUD-1001",
            "novapay",
            2,
            "Q4 Settlement Launch Brief (Demo — sample data)",
            "html",
            aud1_orig,
            aud1_rev,
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.8, "nlp_retrieval_ms": 3.4}),
            1,
            "In Review",
            "Editorial & Brand Reviewer",
            aud1_pillars,
            5.2,
            now,
            now,
        ),
        (
            "AUD-1002",
            "novapay",
            2,
            "Q3 Institutional Performance Note (Demo — sample data)",
            "markdown",
            aud2_orig,
            aud2_rev,
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.4, "nlp_retrieval_ms": 2.9}),
            1,
            "Approved",
            "Editorial & Brand Reviewer",
            aud2_pillars,
            4.3,
            now,
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, fg_color, bg_color,
            image_alt_text, has_visual_asset, visual_metadata_json,
            confidential_mode, overall_status, assigned_reviewer,
            pillar_states_json, runtime_ms, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        seeded_audits,
    )

    claim_target = "Our platform guarantees 95% faster processing for cross-border treasury teams."
    c_start = aud1_rev.index(claim_target)
    c_end = c_start + len(claim_target)

    seeded_findings = [
        (
            "AUD-1001-F01",
            "AUD-1001",
            "Promotional Claims",
            "Numerical Claim Inconsistent with Verified Fact",
            "critical",
            claim_target,
            "P1",
            c_start,
            c_end,
            "FACT-101",
            "[FACT-101 — Verified] \"Processing and cross-border settlement is up to 64% faster under the conditions stated in the approved performance report.\" | Conditions: Measured across 42 supported clearing corridors compared to legacy correspondent SWIFT baselines. | Source: NovaPay Q3 2026 Institutional Performance Report, Section 2.4",
            "The submitted numerical claim ('95') is inconsistent with approved fact FACT-101 (approved value: '64% faster'). Ask the creator to verify or revise the claim.",
            "Our platform delivers up to 64% faster processing under the verified conditions.",
            "Tier 2: Local NLP (TF-IDF Fact Retrieval + Numerical Comparison)",
            "Tier 2: Embedded NLP Engine",
            0.38,
            "open",
            "",
            now,
        ),
        (
            "AUD-1001-F02",
            "AUD-1001",
            "Terminology",
            "Prohibited or Deprecated Terminology",
            "high",
            "AI Engine",
            "P1",
            -1,
            -1,
            "RULE-TERM-01",
            "Preferred term: 'Local Governance Engine' | Prohibited/Deprecated: 'AI Engine'. Note: Never refer to the deterministic + embedded NLP system as a generic 'AI Engine'; use 'Local Governance Engine'.",
            "Detected 'AI Engine'. Never refer to the deterministic + embedded NLP system as a generic 'AI Engine'; use 'Local Governance Engine'.",
            "Local Governance Engine",
            "Tier 1: Exact Lexicon & Case-Sensitivity Dictionary Match",
            "Tier 1: Deterministic Engine",
            None,
            "accepted",
            "Local Governance Engine",
            now,
        ),
        (
            "AUD-1002-F01",
            "AUD-1002",
            "Terminology",
            "Capitalization & Brand Spelling Mismatch",
            "high",
            "Novapay",
            "P2",
            -1,
            -1,
            "RULE-TERM-01",
            "Preferred term: 'NovaPay' | Prohibited/Deprecated: 'Novapay'. Note: Brand spelling requires capital 'N' and capital 'P' ('NovaPay').",
            "Detected 'Novapay'. Brand spelling requires capital 'N' and capital 'P' ('NovaPay').",
            "NovaPay",
            "Tier 1: Exact Lexicon & Case-Sensitivity Dictionary Match",
            "Tier 1: Deterministic Engine",
            None,
            "accepted",
            "NovaPay",
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO findings (
            id, audit_id, pillar, issue_type, severity, flagged_text,
            paragraph_ref, start_index, end_index, rule_or_fact_id,
            source_evidence, explanation, suggested_correction, detection_method,
            engine_source, similarity_score, review_state, decision_note, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        seeded_findings,
    )

    seeded_revisions = [
        (
            "AUD-1001",
            1,
            aud1_orig,
            aud1_orig,
            "Content Creator",
            "Initial content submitted for pre-publication brand audit.",
            now,
        ),
        (
            "AUD-1001",
            2,
            aud1_orig,
            aud1_rev,
            "Content Creator",
            "Accepted correction for AUD-1001-F02 (RULE-TERM-01): replaced 'AI Engine' with 'Local Governance Engine'.",
            now,
        ),
        (
            "AUD-1002",
            1,
            aud2_orig,
            aud2_orig,
            "Content Creator",
            "Initial content submitted for pre-publication brand audit.",
            now,
        ),
        (
            "AUD-1002",
            2,
            aud2_orig,
            aud2_rev,
            "Content Creator",
            "Accepted correction for AUD-1002-F01 (RULE-TERM-01): replaced 'Novapay' with 'NovaPay'.",
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO revisions
        (audit_id, version_number, previous_content, revised_content, editor_role, change_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        seeded_revisions,
    )

    cur.execute(
        "UPDATE audits SET submitted_by_user_id = 'usr_priya', submitted_by_name = 'Priya Nair' WHERE id IN ('AUD-1001', 'AUD-1002')"
    )
    aud2_sha = hashlib.sha256(aud2_rev.encode("utf-8")).hexdigest()
    cur.execute(
        """
        INSERT INTO approvals
        (audit_id, previous_state, new_state, approver_role, approver_user_id, approver_name, version_reviewed,
         unresolved_findings_count, override_acknowledged, comment, content_sha256, created_at)
        VALUES (?, 'Revised', 'Approved', 'Reviewer', 'usr_marcus', 'Marcus Lee', 2, 0, 0, 'All findings resolved and verified against Fact Sheet FACT-101.', ?, ?)
        """,
        ("AUD-1002", aud2_sha, now),
    )
    aud1_sha = hashlib.sha256(aud1_rev.encode("utf-8")).hexdigest()
    cur.execute(
        """
        INSERT INTO approvals
        (audit_id, previous_state, new_state, approver_role, approver_user_id, approver_name, version_reviewed,
         unresolved_findings_count, override_acknowledged, comment, content_sha256, created_at)
        VALUES (?, 'Draft', 'In Review', 'Content Creator', 'usr_priya', 'Priya Nair', 2, 1, 0, 'Submitted for review.', ?, ?)
        """,
        ("AUD-1001", aud1_sha, now),
    )

    sample_actor = "Sample workspace user"
    seeded_events = [
        ("AUD-1001", "submitted", "Content Creator", "Submitted for audit (v1).", {}, 1),
        (
            "AUD-1001", "correction_applied", "Content Creator",
            "Accepted correction: AI Engine → Local Governance Engine.",
            {"finding_id": "AUD-1001-F02", "rule_or_fact_id": "RULE-TERM-01", "from": "AI Engine", "to": "Local Governance Engine"},
            2,
        ),
        ("AUD-1001", "status_changed", "Content Creator", "Status changed: Draft → In review.", {"from": "Draft", "to": "In Review"}, 2),
        ("AUD-1002", "submitted", "Content Creator", "Submitted for audit (v1).", {}, 1),
        (
            "AUD-1002", "correction_applied", "Content Creator",
            "Accepted correction: Novapay → NovaPay.",
            {"finding_id": "AUD-1002-F01", "rule_or_fact_id": "RULE-TERM-01", "from": "Novapay", "to": "NovaPay"},
            2,
        ),
        (
            "AUD-1002", "approved", "Reviewer",
            "Approved for publication with 0 unresolved findings.",
            {"from": "Revised", "to": "Approved", "unresolved_findings": 0, "override": False},
            2,
        ),
    ]
    for audit_id, etype, role, summary, detail, ver in seeded_events:
        record_audit_event(cur, audit_id, etype, sample_actor, role, summary, detail, ver, now)

    # 7. Seed Guideline Feedback (for honest Baseline Ambiguity Radar telemetry)
    feedback_rows = [
        (
            "novapay",
            "RULE-TONE-02",
            "AUD-1001",
            "FND-HIST-01",
            "Rule says 'use an appropriate amount of technical detail', which is subjective when writing for both CFOs and API developers.",
            "Poorly written guideline (subjective qualifier 'appropriate amount')",
            "Recommended for Clarification",
            now,
        ),
        (
            "novapay",
            "RULE-TONE-02",
            "AUD-1002",
            "FND-HIST-02",
            "Overridden by reviewer because short social post cannot define every protocol acronym on first use.",
            "Missing channel-specific context in guideline",
            "Recommended for Clarification",
            now,
        ),
        (
            "novapay",
            "RULE-MSG-01",
            "AUD-1001",
            "FND-HIST-03",
            "Headline was only 8 words long; requiring full human-oversight disclaimer in short display titles feels overly strict.",
            "Legitimate exception for short display headlines (<15 words)",
            "Open",
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO guideline_feedback
        (brand_id, rule_id, audit_id, finding_id, override_reason, suspected_cause, admin_review_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        feedback_rows,
    )
    if _is_demo_mode():
        ensure_demo_sample_data(cur, now)


DEMO_EXTRA_AUDIT_IDS = ("AUD-1003", "AUD-1004", "AUD-1005", "AUD-1006")


def ensure_demo_sample_data(cur: sqlite3.Cursor, now: str = "") -> None:
    """
    F6: In demo mode only, seed 3 additional realistically vague NovaPay rules and 4 additional
    sample audits (bringing the total to 6 sample audits, all labelled 'sample data') with realistic
    findings and override feedback so Guideline insights demonstrates High/Medium/Low priorities and
    the >20% override correlation out of the box.
    """
    if not _is_demo_mode():
        return
    if not now:
        now = datetime.now(timezone.utc).isoformat()

    extra_vague_rules = [
        (
            "RULE-TONE-03",
            "novapay",
            "Tone and Voice",
            "Keep Executive Summaries Reasonably Concise and Intuitive",
            "Executive summaries should be reasonably concise, intuitive for non-technical stakeholders, and use suitable terminology where possible.",
            json.dumps({"patterns": [], "sample_data": True}),
            "medium",
            "",
            "",
            1,
            1,
            now,
        ),
        (
            "RULE-MSG-02",
            "novapay",
            "Messaging",
            "Provide Timely Corridor Maintenance Notices",
            "Operational status updates must be sent in a timely manner with an adequate explanation of settlement window changes when appropriate.",
            json.dumps({"prohibited_patterns": [], "sample_data": True}),
            "medium",
            "Notify treasury administrators at least 14 days before scheduled clearing window changes.",
            "",
            1,
            1,
            now,
        ),
        (
            "RULE-CLAIM-02",
            "novapay",
            "Promotional Claims",
            "Ensure Efficiency Comparisons Are Significantly Substantiated",
            "Cross-border fee and throughput comparisons must be significantly better than legacy banking baselines and sufficiently documented where suitable.",
            json.dumps({"source": "verified_facts_and_claim_engine", "sample_data": True}),
            "high",
            "",
            "",
            1,
            1,
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT OR IGNORE INTO rules (
            id, brand_id, pillar, title, description, rule_config_json,
            severity, do_example, dont_example, active, version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        extra_vague_rules,
    )

    default_pillars = json.dumps({
        "Tone and Voice": "Findings",
        "Terminology": "Passed",
        "Messaging": "Findings",
        "Promotional Claims": "Passed",
        "Visual and Logo Consistency": "Not Checked",
        "Accessibility": "Passed",
    })
    extra_audits = [
        (
            "AUD-1003",
            "novapay",
            2,
            "APAC Corridor Liquidity Playbook (Sample data)",
            "markdown",
            "# APAC Liquidity Playbook\n\nUse our payout API endpoints for T+0 multi-currency treasury sweeps across Singapore and Tokyo.",
            "# APAC Liquidity Playbook\n\nUse our payout API endpoints for T+0 multi-currency treasury sweeps across Singapore and Tokyo.",
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.5, "nlp_retrieval_ms": 2.6, "sample_data": True}),
            1,
            "Approved",
            "Editorial & Brand Reviewer",
            default_pillars,
            4.1,
            now,
            now,
        ),
        (
            "AUD-1004",
            "novapay",
            2,
            "ISO 20022 Migration Datasheet (Sample data)",
            "html",
            "<h1>ISO 20022 Migration Guide</h1><p>Configure pacs.008 and camt.053 message schemas with automated reconciliation rules.</p>",
            "<h1>ISO 20022 Migration Guide</h1><p>Configure pacs.008 and camt.053 message schemas with automated reconciliation rules.</p>",
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.6, "nlp_retrieval_ms": 2.8, "sample_data": True}),
            1,
            "In Review",
            "Editorial & Brand Reviewer",
            default_pillars,
            4.4,
            now,
            now,
        ),
        (
            "AUD-1005",
            "novapay",
            2,
            "EMEA SEPA Instant Maintenance Notice (Sample data)",
            "plain_text",
            "Scheduled SEPA Instant corridor maintenance will occur this Sunday with updated settlement cut-off windows.",
            "Scheduled SEPA Instant corridor maintenance will occur this Sunday with updated settlement cut-off windows.",
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.2, "nlp_retrieval_ms": 2.1, "sample_data": True}),
            1,
            "Approved",
            "Editorial & Brand Reviewer",
            default_pillars,
            3.3,
            now,
            now,
        ),
        (
            "AUD-1006",
            "novapay",
            2,
            "CFO Quarterly Automation Executive Brief (Sample data)",
            "markdown",
            "# Quarterly Treasury Brief\n\nNovaPay Core streamlines multi-subsidiary cash pooling with role-based CFO sign-off.",
            "# Quarterly Treasury Brief\n\nNovaPay Core streamlines multi-subsidiary cash pooling with role-based CFO sign-off.",
            "",
            "",
            "",
            0,
            json.dumps({"deterministic_ms": 1.3, "nlp_retrieval_ms": 2.4, "sample_data": True}),
            1,
            "Approved",
            "Editorial & Brand Reviewer",
            default_pillars,
            3.7,
            now,
            now,
        ),
    ]
    cur.executemany(
        """
        INSERT OR IGNORE INTO audits (
            id, brand_id, brand_version, document_name, input_format,
            original_content, current_content, fg_color, bg_color,
            image_alt_text, has_visual_asset, visual_metadata_json,
            confidential_mode, overall_status, assigned_reviewer,
            pillar_states_json, runtime_ms, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        extra_audits,
    )

    extra_findings = [
        # RULE-TONE-02 findings (3 findings across sample audits, 2 overrides -> 66.7% > 20% -> High Priority)
        (
            "AUD-1003-F01", "AUD-1003", "Tone and Voice",
            "Use an Appropriate Amount of Technical Detail", "medium",
            "Use our payout API endpoints for T+0 multi-currency treasury sweeps",
            "P1", 0, 66, "RULE-TONE-02",
            "Rule RULE-TONE-02 requires an appropriate amount of technical detail.",
            "Flagged under subjective technical-detail threshold in RULE-TONE-02.",
            "Explain the primary business benefit in plain language before introducing API endpoint names.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "dismissed", "Dismissed (sample data): API playbook targets integration engineers.", now,
        ),
        (
            "AUD-1004-F01", "AUD-1004", "Tone and Voice",
            "Use an Appropriate Amount of Technical Detail", "medium",
            "Configure pacs.008 and camt.053 message schemas",
            "P1", 0, 47, "RULE-TONE-02",
            "Rule RULE-TONE-02 requires an appropriate amount of technical detail.",
            "Flagged ISO 20022 schema identifiers as high technical density.",
            "Define pacs.008 (Customer Credit Transfer) and camt.053 (Bank-to-Customer Statement) on first use.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "accepted", "Define pacs.008 (Customer Credit Transfer) and camt.053 on first use.", now,
        ),
        (
            "AUD-1005-F01", "AUD-1005", "Tone and Voice",
            "Use an Appropriate Amount of Technical Detail", "medium",
            "updated settlement cut-off windows",
            "P1", 0, 34, "RULE-TONE-02",
            "Rule RULE-TONE-02 requires an appropriate amount of technical detail.",
            "Flagged under subjective technical-detail wording.",
            "Specify exact UTC cut-off timestamps for each clearing corridor.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "dismissed", "Dismissed (sample data): maintenance alert links to status table.", now,
        ),
        # RULE-TONE-03 findings (3 findings, 2 overrides -> 66.7% > 20% -> High Priority)
        (
            "AUD-1003-F02", "AUD-1003", "Tone and Voice",
            "Keep Executive Summaries Reasonably Concise and Intuitive", "medium",
            "multi-currency treasury sweeps across Singapore and Tokyo",
            "P1", 0, 57, "RULE-TONE-03",
            "Rule RULE-TONE-03 requires summaries to be reasonably concise and intuitive.",
            "Subjective conciseness trigger on executive summary paragraph.",
            "Keep executive summary paragraphs under 40 words with a 1-sentence takeaway.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "dismissed", "Dismissed (sample data): 'reasonably concise' has no word count threshold.", now,
        ),
        (
            "AUD-1004-F02", "AUD-1004", "Tone and Voice",
            "Keep Executive Summaries Reasonably Concise and Intuitive", "medium",
            "automated reconciliation rules",
            "P1", 0, 30, "RULE-TONE-03",
            "Rule RULE-TONE-03 requires summaries to be reasonably concise and intuitive.",
            "Subjective intuitiveness check triggered.",
            "State the reconciliation workflow in plain language before listing schema tags.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "dismissed", "Dismissed (sample data): 'intuitive' is interpreted differently by reviewers.", now,
        ),
        (
            "AUD-1006-F01", "AUD-1006", "Tone and Voice",
            "Keep Executive Summaries Reasonably Concise and Intuitive", "medium",
            "NovaPay Core streamlines multi-subsidiary cash pooling",
            "P1", 0, 54, "RULE-TONE-03",
            "Rule RULE-TONE-03 requires summaries to be reasonably concise and intuitive.",
            "Summary phrasing reviewed for executive clarity.",
            "Lead with measurable cash-visibility benefits for CFOs.",
            "Tier 2: Configured Tone Pattern & Polarity Heuristic", "Tier 1: Deterministic Engine",
            None, "accepted", "Lead with measurable cash-visibility benefits for CFOs.", now,
        ),
        # RULE-MSG-02 findings (5 findings, 1 override -> 20.0% <= 20% -> Medium Priority: Vague (low override rate))
        (
            "AUD-1003-F03", "AUD-1003", "Messaging",
            "Provide Timely Corridor Maintenance Notices", "medium",
            "T+0 multi-currency treasury sweeps",
            "P1", 0, 34, "RULE-MSG-02",
            "Rule RULE-MSG-02 requires timely notification and adequate explanation.",
            "Maintenance notice lead-time not quantified in notice copy.",
            "State explicit notice window (at least 14 calendar days prior to maintenance).",
            "Tier 2: Messaging Principle Contradiction Check", "Tier 2: Embedded NLP Engine",
            None, "accepted", "State 14-day advance notice window.", now,
        ),
        (
            "AUD-1004-F03", "AUD-1004", "Messaging",
            "Provide Timely Corridor Maintenance Notices", "medium",
            "automated reconciliation rules",
            "P1", 0, 30, "RULE-MSG-02",
            "Rule RULE-MSG-02 requires timely notification and adequate explanation.",
            "Cut-off schedule delta not specified.",
            "Include UTC start/end timestamps for scheduled maintenance.",
            "Tier 2: Messaging Principle Contradiction Check", "Tier 2: Embedded NLP Engine",
            None, "accepted", "Include UTC start/end timestamps.", now,
        ),
        (
            "AUD-1005-F02", "AUD-1005", "Messaging",
            "Provide Timely Corridor Maintenance Notices", "medium",
            "Scheduled SEPA Instant corridor maintenance will occur this Sunday",
            "P1", 0, 66, "RULE-MSG-02",
            "Rule RULE-MSG-02 requires timely notification and adequate explanation.",
            "Phrase 'this Sunday' does not state how many days in advance notice was issued.",
            "Provide notice at least 14 days in advance per SLA-2026-v3.",
            "Tier 2: Messaging Principle Contradiction Check", "Tier 2: Embedded NLP Engine",
            None, "dismissed", "Dismissed (sample data): 'timely' is not quantified in RULE-MSG-02.", now,
        ),
        (
            "AUD-1005-F03", "AUD-1005", "Messaging",
            "Provide Timely Corridor Maintenance Notices", "medium",
            "updated settlement cut-off windows",
            "P1", 0, 34, "RULE-MSG-02",
            "Rule RULE-MSG-02 requires timely notification and adequate explanation.",
            "Fee impact statement omitted.",
            "Confirm that standard SEPA Instant fee schedules remain unchanged during maintenance.",
            "Tier 2: Messaging Principle Contradiction Check", "Tier 2: Embedded NLP Engine",
            None, "accepted", "Confirm fee schedules remain unchanged.", now,
        ),
        (
            "AUD-1006-F02", "AUD-1006", "Messaging",
            "Provide Timely Corridor Maintenance Notices", "medium",
            "multi-subsidiary cash pooling",
            "P1", 0, 29, "RULE-MSG-02",
            "Rule RULE-MSG-02 requires timely notification and adequate explanation.",
            "Settlement window notice period unspecified.",
            "Reference the 14-day advance maintenance notification SLA.",
            "Tier 2: Messaging Principle Contradiction Check", "Tier 2: Embedded NLP Engine",
            None, "accepted", "Reference 14-day advance maintenance notification SLA.", now,
        ),
    ]
    cur.executemany(
        """
        INSERT OR IGNORE INTO findings (
            id, audit_id, pillar, issue_type, severity, flagged_text,
            paragraph_ref, start_index, end_index, rule_or_fact_id,
            source_evidence, explanation, suggested_correction, detection_method,
            engine_source, similarity_score, review_state, decision_note, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        extra_findings,
    )

    # Ensure demo feedback rows exist without duplicating on repeated calls
    cur.execute("SELECT COUNT(*) AS cnt FROM guideline_feedback WHERE finding_id LIKE 'AUD-100%-F%'")
    if int(cur.fetchone()["cnt"] or 0) == 0:
        extra_feedback = [
            (
                "novapay",
                "RULE-TONE-03",
                "AUD-1003",
                "AUD-1003-F02",
                "Sample data: 'reasonably concise' and 'intuitive' have no word-count or grade-level threshold, leading to inconsistent reviewer overrides.",
                "Subjective qualifier ('reasonably concise', 'intuitive') without numeric limit",
                "Recommended for Clarification",
                now,
            ),
            (
                "novapay",
                "RULE-TONE-03",
                "AUD-1004",
                "AUD-1004-F02",
                "Sample data: Technical datasheet readers expect protocol identifiers; 'suitable terminology where possible' is too vague to enforce consistently.",
                "Subjective qualifier ('suitable', 'where possible') without channel threshold",
                "Recommended for Clarification",
                now,
            ),
            (
                "novapay",
                "RULE-MSG-02",
                "AUD-1005",
                "AUD-1005-F02",
                "Sample data: Rule requires 'timely' notification and 'adequate' explanation without citing the 14-day SLA window.",
                "Missing numeric lead-time threshold in guideline wording",
                "Open",
                now,
            ),
        ]
        cur.executemany(
            """
            INSERT INTO guideline_feedback
            (brand_id, rule_id, audit_id, finding_id, override_reason, suspected_cause, admin_review_state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            extra_feedback,
        )


def reset_demo_workspace() -> None:
    """Restore the sample workspace. Refuses to run against a production workspace."""
    if not _is_demo_mode() and "test" not in os.path.basename(get_db_path()).lower() and not os.environ.get("PYTEST_CURRENT_TEST"):
        raise PermissionError("Sample data can only be reset inside the isolated demo workspace.")
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
        DELETE FROM guideline_revisions;
        DELETE FROM certificates;
        DELETE FROM audit_events;
        DELETE FROM guideline_feedback;
        DELETE FROM approvals;
        DELETE FROM review_decisions;
        DELETE FROM revisions;
        DELETE FROM findings;
        DELETE FROM audits;
        DELETE FROM brand_colors;
        DELETE FROM verified_facts;
        DELETE FROM terminology;
        DELETE FROM rules;
        DELETE FROM brands;
        """
    )
    seed_default_workspace(cur)
    conn.commit()
    conn.close()


TABLES_FOR_SNAPSHOT = [
    "brands",
    "brand_colors",
    "rules",
    "guideline_revisions",
    "terminology",
    "verified_facts",
    "audits",
    "findings",
    "revisions",
    "review_decisions",
    "approvals",
    "guideline_feedback",
    "certificates",
    "certificate_revocations",
    "audit_events",
]


def export_database_snapshot(snapshot_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Serializes core database tables to JSON to survive redeploys on ephemeral hosting."""
    path = snapshot_path or os.path.join(os.path.dirname(__file__), "db_snapshot.json")
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        snapshot_data: Dict[str, Any] = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": {},
        }
        for tbl in TABLES_FOR_SNAPSHOT:
            try:
                cur.execute(f"SELECT * FROM {tbl}")
                cols = [desc[0] for desc in cur.description] if cur.description else []
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                snapshot_data["tables"][tbl] = rows
            except sqlite3.OperationalError:
                snapshot_data["tables"][tbl] = []
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2, sort_keys=True)
        return snapshot_data
    finally:
        if should_close:
            conn.close()


def restore_database_snapshot(snapshot_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> bool:
    """Restores database tables from JSON snapshot if database is empty on container startup."""
    path = snapshot_path or os.path.join(os.path.dirname(__file__), "db_snapshot.json")
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            snapshot_data = json.load(f)
    except Exception as exc:
        print("RESTORE ERROR:", repr(exc))
        return False

    tables = snapshot_data.get("tables", {})
    if not tables:
        return False

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        conn.execute("PRAGMA foreign_keys = OFF;")
        for tbl in TABLES_FOR_SNAPSHOT:
            rows = tables.get(tbl, [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            sql = f"INSERT OR REPLACE INTO {tbl} ({col_names}) VALUES ({placeholders})"
            for r in rows:
                cur.execute(sql, [r[c] for c in cols])
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON;")
        return True
    except Exception as exc:
        return False
    finally:
        if should_close:
            conn.close()


# ============================================================================
# PRE-BAKED BRAND PRESETS (Round 1 Commitment Taxonomy)
# ============================================================================

BRAND_PRESETS: Dict[str, Dict[str, Any]] = {
    "novapay": {
        "brand": {
            "id": "novapay",
            "name": "NovaPay Enterprise",
            "industry": "B2B Treasury & Cross-Border Settlement",
            "description": "Institutional settlement and treasury automation platform for regulated enterprises.",
            "tone_principles": "Calm, evidence-backed, precise, and transparent. Avoid alarmist urgency, panic-inducing claims, or unverified superlatives.",
            "writing_style": "Use clear active prose. Define technical terms on first use. Keep sentences direct and accessible.",
            "messaging_principles": "Every automation claim must acknowledge configurable human approval controls and institutional compliance boundaries.",
            "do_examples": json.dumps([
                "NovaPay Core delivers up to 64% faster settlement under the conditions stated in the Q3 benchmark report.",
                "Automate recurring vendor payouts with role-based CFO sign-off above configured thresholds."
            ]),
            "dont_examples": json.dumps([
                "Our platform guarantees 95% faster processing with zero latency!",
                "Legacy banks are destroying your margins—fire your finance ops team today!"
            ]),
            "typography_specs": "Primary UI & Headings: Inter / Geist (600-700 weight). Body: Inter (400-500 weight, 14-16px).",
            "spacing_rules": "Maintain minimum 16px clear space around the primary wordmark on digital banners and 8px base grid alignment.",
            "logo_placement_constraints": "Place primary wordmark in top-left or bottom-left lockup zones; never stretch, skew, or place over low-contrast busy imagery.",
            "min_contrast_normal": 4.5,
            "min_contrast_large": 3.0,
            "require_alt_text": 1,
            "enforce_heading_order": 1,
            "target_reading_ease": 50.0,
            "version": 2,
        },
        "colors": [
            ("COL-01", "novapay", "Primary Charcoal", "#17191C", "Primary Brand Surface & Typography", 12.0),
            ("COL-02", "novapay", "Signal Accent Orange", "#EA633F", "Primary Interactive Accent & Highlights", 14.0),
            ("COL-03", "novapay", "Compliance Emerald", "#188568", "Verified & Passed Status", 14.0),
            ("COL-04", "novapay", "Workspace Surface", "#F7F8FA", "Light Background Surface", 10.0),
            ("COL-05", "novapay", "Institutional Slate", "#202124", "Body Copy Typography", 12.0),
        ],
        "rules": [
            ("RULE-TONE-01", "novapay", "Tone and Voice", "Prohibit Alarmist or Fear-Mongering Language", "Marketing content must not use alarmist phrasing, panic-inducing rhetoric, or sensationalist exclamations to pressure buyers.", json.dumps({"patterns": [r"\b(?:crush(?:ing|es)?|destroy(?:ing|s)?|catastroph(?:e|ic)|disaster|panic|obsolete|death sentence)\b"]}), "high", "Transition legacy systems predictably with managed cutover schedules.", "Legacy payment infrastructure will destroy your business within six months!", 1, 1, "2026-01-01T00:00:00Z"),
            ("RULE-CLAIM-01", "novapay", "Promotional Claims", "Substantiate Promotional, Superlative & Numerical Claims Against Verified Facts", "All numerical claims, speed comparisons, uptime figures, and fee statements must match a Verified Fact in the Brand Vault and include applicable conditions.", json.dumps({"source": "verified_facts"}), "high", "NovaPay Core achieves up to 64% faster settlement for EUR/USD corridors under standard SLA terms.", "Our platform delivers 10x faster settlement with zero latency or fees across the globe!", 1, 1, "2026-01-01T00:00:00Z"),
        ],
        "facts": [
            ("FACT-101", "novapay", "Processing and cross-border settlement is up to 64% faster under the conditions stated in the approved performance report.", "64", "% faster", "NovaPay Core settlement & processing speed", "NovaPay Q3 2026 Institutional Performance Report, Section 2.4", "Measured across 42 supported clearing corridors compared to legacy correspondent SWIFT baselines.", "2026-Q3", "Verified", "2026-01-01T00:00:00Z"),
        ],
    },
    "verdant": {
        "brand": {
            "id": "verdant",
            "name": "Verdant Clinical Systems",
            "industry": "Healthcare Diagnostic Decision Support",
            "description": "Clinician-assisted radiology triage and workflow prioritization software.",
            "tone_principles": "Empathetic, clinically objective, cautious, and human-centered. Never imply autonomous medical diagnosis.",
            "writing_style": "Plain clinical English with explicit study citations and sample conditions.",
            "messaging_principles": "Always emphasize that software outputs assist board-certified clinicians rather than replacing medical judgment.",
            "do_examples": json.dumps([
                "Verdant Triage Assist demonstrated 94.2% sensitivity in assisting radiologists across 18,400 chest radiographs."
            ]),
            "dont_examples": json.dumps([
                "Verdant AI guarantees 100% diagnostic accuracy and replaces radiologists."
            ]),
            "typography_specs": "Headings: Inter SemiBold. Body: Inter Regular (minimum 14px).",
            "spacing_rules": "Minimum clear space equal to the cap-height of the 'V' mark around all sides.",
            "logo_placement_constraints": "Use horizontal lockup on clinical reports; never overlay on low-contrast scan regions.",
            "min_contrast_normal": 4.5,
            "min_contrast_large": 3.0,
            "require_alt_text": 1,
            "enforce_heading_order": 1,
            "target_reading_ease": 45.0,
            "version": 1,
        },
        "colors": [
            ("COL-06", "verdant", "Clinical Teal", "#188568", "Primary Clinical Accent", 14.0),
            ("COL-07", "verdant", "Deep Charcoal", "#17191C", "Primary Text", 12.0),
        ],
        "rules": [
            ("RULE-VRD-TONE-01", "verdant", "Tone and Voice", "Prohibit Autonomous Diagnosis Assertions", "Never claim software autonomously diagnoses patient pathology without physician review.", json.dumps({"patterns": [r"\b(?:autonomous diagnosis|replaces radiologists|100% cure)\b"]}), "high", "Assists radiologists in prioritizing critical findings.", "Replaces hospital radiologists with automated instant diagnosis.", 1, 1, "2026-01-01T00:00:00Z"),
        ],
        "facts": [
            ("FACT-VRD-01", "verdant", "Verdant Triage Assist demonstrated 94.2% sensitivity in assisting radiologists across 18,400 chest radiographs under IRB study #8491.", "94.2", "% sensitivity", "Chest radiograph triage assist", "Journal of Clinical Imaging 2025, Vol 42", "Assisting board-certified radiologists", "2025-Q1", "Verified", "2026-01-01T00:00:00Z"),
        ],
    },
    "acmecorp": {
        "brand": {
            "id": "acmecorp",
            "name": "Acme Cloud Infrastructure",
            "industry": "Cloud Infrastructure & DevOps",
            "description": "High-reliability distributed container execution and serverless orchestration platform for enterprise engineering.",
            "tone_principles": "Engineering-first, precise, metrics-driven, and transparent. Avoid unbacked marketing superlatives.",
            "writing_style": "Concise technical English with benchmark parameters and reproducible system requirements.",
            "messaging_principles": "All SLA and latency claims must specify measurement percentiles and network topologies.",
            "do_examples": json.dumps([
                "Acme Mesh achieves sub-5ms packet routing under VPC benchmark conditions with 99.999% SLA on enterprise plans."
            ]),
            "dont_examples": json.dumps([
                "Acme is infinitely fast and cheaper than all other cloud providers combined!"
            ]),
            "typography_specs": "Headings: JetBrains Mono / Inter (600-700 weight). Body: Inter / system-ui (400-500 weight, 14-16px).",
            "spacing_rules": "Maintain minimum 24px clear space around Acme wordmark; minimum 12px padding between layout cards.",
            "logo_placement_constraints": "Top-left header navigation or centered footer banner. Never invert logo colors on dark backgrounds.",
            "min_contrast_normal": 4.5,
            "min_contrast_large": 3.0,
            "require_alt_text": 1,
            "enforce_heading_order": 1,
            "target_reading_ease": 55.0,
            "version": 1,
        },
        "colors": [
            ("COL-ACM-01", "acmecorp", "Acme Slate Dark", "#0F172A", "Primary Text & Headers", 12.0),
            ("COL-ACM-02", "acmecorp", "Acme Blue Primary", "#2563EB", "Primary Interactive Brand Accent", 14.0),
            ("COL-ACM-03", "acmecorp", "Acme Sky Highlight", "#38BDF8", "System Status & Metrics", 14.0),
            ("COL-ACM-04", "acmecorp", "Acme Cloud Surface", "#F8FAFC", "Light Background Surface", 10.0),
        ],
        "rules": [
            ("RULE-ACM-CLAIM-01", "acmecorp", "Promotional Claims", "Substantiate Latency and SLA Claims", "Require benchmark parameters and SLA tier citations on all latency and uptime claims.", json.dumps({"source": "verified_facts"}), "high", "Acme Mesh achieves sub-5ms packet routing under VPC benchmark conditions.", "Acme is infinitely fast with zero latency!", 1, 1, "2026-01-01T00:00:00Z"),
            ("RULE-ACM-TONE-01", "acmecorp", "Tone and Voice", "Prohibit Exaggerated Superlatives", "Marketing content must use evidence-based technical descriptions rather than exaggerated adjectives.", json.dumps({"patterns": [r"\b(?:miraculous|infinitely|game-changer|flawless)\b"]}), "medium", "Acme Mesh scales horizontally across Kubernetes nodes.", "Acme is a miraculous game-changer that crushes other tools.", 1, 1, "2026-01-01T00:00:00Z"),
        ],
        "facts": [
            ("FACT-ACM-01", "acmecorp", "Acme Mesh achieves sub-5ms packet routing under VPC benchmark conditions with 99.999% SLA on enterprise plans.", "5", "ms", "Packet routing latency", "Engineering Benchmark Report Q4 2025, Section 3.2", "Measured on AWS VPC cross-AZ connections", "2025-Q4", "Verified", "2026-01-01T00:00:00Z"),
        ],
    },
    "finsafe": {
        "brand": {
            "id": "finsafe",
            "name": "FinSafe Wealth Management",
            "industry": "Consumer Wealth & Investment",
            "description": "Fiduciary automated portfolio rebalancing and retirement wealth management platform.",
            "tone_principles": "Prudent, fiduciary, transparent, and encouraging. Never promise guaranteed returns or risk-free profits.",
            "writing_style": "Clear financial literacy English. Define compound interest, expense ratios, and historical volatility.",
            "messaging_principles": "All performance projections must include past-performance disclaimers and explicit tax assumptions.",
            "do_examples": json.dumps([
                "FinSafe automated tax-loss harvesting improved simulated net returns by up to 1.8% annually across 10-year historical backtests."
            ]),
            "dont_examples": json.dumps([
                "Double your retirement savings risk-free in 12 months with FinSafe AI!"
            ]),
            "typography_specs": "Headings: Merriweather / Georgia (600-700 weight). Body: Source Sans 3 / Inter (400-500 weight, 15-18px).",
            "spacing_rules": "Generous breathing room: 32px clear space around primary crest logo and 16px section margins.",
            "logo_placement_constraints": "Center top on quarterly statements, upper left on mobile dashboard.",
            "min_contrast_normal": 4.5,
            "min_contrast_large": 3.0,
            "require_alt_text": 1,
            "enforce_heading_order": 1,
            "target_reading_ease": 60.0,
            "version": 1,
        },
        "colors": [
            ("COL-FIN-01", "finsafe", "FinSafe Emerald Dark", "#064E3B", "Primary Brand Tone & Headers", 12.0),
            ("COL-FIN-02", "finsafe", "FinSafe Mint Primary", "#10B981", "Interactive Buttons & Accents", 14.0),
            ("COL-FIN-03", "finsafe", "FinSafe Gold Accent", "#D97706", "Wealth Tier Highlights", 14.0),
            ("COL-FIN-04", "finsafe", "FinSafe Off-White", "#F9FAFB", "Document Background", 10.0),
        ],
        "rules": [
            ("RULE-FIN-CLAIM-01", "finsafe", "Promotional Claims", "Past Performance and Return Substantiation", "All returns and yield statements must carry past performance disclaimers and match verified facts.", json.dumps({"source": "verified_facts"}), "high", "Automated tax-loss harvesting improved simulated returns by up to 1.8% annually across 10-year backtests.", "Guaranteed 20% annual returns with zero risk!", 1, 1, "2026-01-01T00:00:00Z"),
            ("RULE-FIN-TONE-01", "finsafe", "Tone and Voice", "Prohibit Guaranteed Return Claims", "Fiduciary guidelines prohibit guaranteeing investment returns, profits, or capital preservation.", json.dumps({"patterns": [r"\b(?:guaranteed returns?|zero risk|risk-free profits?)\b"]}), "high", "Investment portfolios involve risk of capital loss.", "Earn guaranteed risk-free profits every month.", 1, 1, "2026-01-01T00:00:00Z"),
        ],
        "facts": [
            ("FACT-FIN-01", "finsafe", "FinSafe automated tax-loss harvesting improved simulated net returns by up to 1.8% annually across 10-year historical backtests.", "1.8", "% annually", "Automated tax-loss harvesting returns", "Quantitative Research Whitepaper 2025-Q2", "Based on 10-year historical backtests", "2025-Q2", "Verified", "2026-01-01T00:00:00Z"),
        ],
    },
}


def list_brand_presets() -> List[Dict[str, Any]]:
    """Returns available pre-baked brand presets."""
    return [
        {
            "id": p["brand"]["id"],
            "name": p["brand"]["name"],
            "industry": p["brand"]["industry"],
            "description": p["brand"]["description"],
            "rules_count": len(p.get("rules", [])),
            "facts_count": len(p.get("facts", [])),
            "colors_count": len(p.get("colors", [])),
        }
        for p in BRAND_PRESETS.values()
    ]


def apply_brand_preset(preset_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Applies a pre-configured brand preset into the database, creating brand profile, colors, rules and facts."""
    preset = BRAND_PRESETS.get(preset_id)
    if not preset:
        raise ValueError(f"Unknown preset_id '{preset_id}'. Available presets: {list(BRAND_PRESETS.keys())}")

    b = preset["brand"]
    now = datetime.now(timezone.utc).isoformat()
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO brands (
                id, name, industry, description, tone_principles, writing_style,
                messaging_principles, do_examples, dont_examples, typography_specs,
                spacing_rules, logo_placement_constraints, min_contrast_normal,
                min_contrast_large, require_alt_text, enforce_heading_order,
                target_reading_ease, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                b["id"], b["name"], b["industry"], b["description"],
                b["tone_principles"], b["writing_style"], b["messaging_principles"],
                b["do_examples"], b["dont_examples"], b["typography_specs"],
                b["spacing_rules"], b["logo_placement_constraints"],
                b["min_contrast_normal"], b["min_contrast_large"],
                b["require_alt_text"], b["enforce_heading_order"],
                b["target_reading_ease"], b.get("version", 1), now,
            ),
        )
        for col in preset.get("colors", []):
            cur.execute(
                """
                INSERT OR REPLACE INTO brand_colors (
                    id, brand_id, name, hex_code, usage_role, max_delta_e
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                col,
            )
        for rule in preset.get("rules", []):
            cur.execute(
                """
                INSERT OR REPLACE INTO rules (
                    id, brand_id, pillar, title, description, rule_config_json,
                    severity, do_example, dont_example, active, version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rule,
            )
        for fact in preset.get("facts", []):
            cur.execute(
                """
                INSERT OR REPLACE INTO verified_facts (
                    id, brand_id, statement, numeric_value, numeric_units, product_context,
                    source_reference, applicable_conditions, date_version, verification_status,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fact,
            )
        conn.commit()
        return b
    finally:
        if should_close:
            conn.close()
