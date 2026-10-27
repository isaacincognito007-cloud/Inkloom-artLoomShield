import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

DB_PATH = os.path.join(os.path.dirname(__file__), "loomshield.db")
DEMO_DB_PATH = os.path.join(os.path.dirname(__file__), "loomshield_demo.db")


def _is_demo_mode() -> bool:
    return os.environ.get("LOOMSHIELD_WORKSPACE_MODE", "production").strip().lower() == "demo"


def _should_seed_workspace() -> bool:
    return _is_demo_mode() or "test" in os.path.basename(get_db_path()).lower() or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def get_db_path() -> str:
    """Production and the sample (demo) workspace always use separate database files."""
    override = os.environ.get("LOOMSHIELD_DB_PATH")
    if override:
        return override
    return DEMO_DB_PATH if _is_demo_mode() else DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
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


def _ensure_column(cur: sqlite3.Cursor, table: str, column: str, col_def: str) -> None:
    """Idempotent migration helper: add column to table if it does not already exist."""
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")



def init_db() -> None:
    conn = get_connection()
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
    _ensure_column(cur, "audits", "submitted_by_user_id", "TEXT DEFAULT ''")
    _ensure_column(cur, "audits", "submitted_by_name", "TEXT DEFAULT ''")
    _ensure_column(cur, "approvals", "approver_user_id", "TEXT DEFAULT ''")
    _ensure_column(cur, "approvals", "approver_name", "TEXT DEFAULT ''")
    _ensure_column(cur, "audit_events", "actor_user_id", "TEXT DEFAULT ''")

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

    # Only the isolated sample workspace or test runs are pre-populated. Production starts empty.
    cur.execute("SELECT COUNT(*) AS cnt FROM brands")
    if cur.fetchone()["cnt"] == 0 and _should_seed_workspace():
        seed_default_workspace(cur)

    conn.commit()
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
            "Q4 Settlement Launch Brief (Demo)",
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
            "Q3 Institutional Performance Note (Demo)",
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
            "Local NLP (TF-IDF Fact Retrieval + Numerical Comparison)",
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
            "Exact Lexicon & Case-Sensitivity Dictionary Match",
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
            "Exact Lexicon & Case-Sensitivity Dictionary Match",
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


def reset_demo_workspace() -> None:
    """Restore the sample workspace. Refuses to run against a production workspace."""
    if not _is_demo_mode() and "test" not in os.path.basename(get_db_path()).lower() and not os.environ.get("PYTEST_CURRENT_TEST"):
        raise PermissionError("Sample data can only be reset inside the isolated demo workspace.")
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
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
