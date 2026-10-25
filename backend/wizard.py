"""
Guided 'New Audit' profile composer, ruleset fragment manager, and validation engine.

Provides zero-setup brand governance by generating isolated, fully populated audit profiles
from simple user answers without altering existing workspace brand definitions.
"""

import glob
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import re._parser as sre_parser
except ImportError:
    import sre_parse as sre_parser

try:
    from re._constants import (
        MAX_REPEAT,
        MIN_REPEAT,
        SUBPATTERN,
        BRANCH,
        LITERAL,
        NOT_LITERAL,
        IN,
        ANY,
        AT,
        CATEGORY,
        RANGE,
        MAXREPEAT,
    )
except ImportError:
    from sre_constants import (
        MAX_REPEAT,
        MIN_REPEAT,
        SUBPATTERN,
        BRANCH,
        LITERAL,
        NOT_LITERAL,
        IN,
        ANY,
        AT,
        CATEGORY,
        RANGE,
        MAXREPEAT,
    )

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("loomshield.wizard")
RULESETS_DIR = os.path.join(os.path.dirname(__file__), "rulesets")

# ---------------------------------------------------------------------------
# Pydantic Schemas for Fragment Validation
# ---------------------------------------------------------------------------

class RuleDef(BaseModel):
    key: str
    pillar: str
    title: str
    description: str
    patterns: List[str] = Field(default_factory=list)
    suggested_replacements: Dict[str, str] = Field(default_factory=dict)
    severity: str = "medium"
    do_example: str = ""
    dont_example: str = ""


class TermDef(BaseModel):
    preferred: str
    prohibited: str
    replacement: str = ""
    case_sensitive: int = 0
    notes: str = ""
    rule_key: str = "RULE-TERM-01"


class ColorDef(BaseModel):
    name: str
    hex_code: str
    usage_role: str
    max_delta_e: float = 12.0


class RulesetFragment(BaseModel):
    id: str
    label: str
    kind: str  # 'industry', 'occasion', 'locale', 'tone'
    summary: List[str]
    tone_principles: Optional[str] = ""
    writing_style: Optional[str] = ""
    messaging_principles: Optional[str] = ""
    do_examples: List[str] = Field(default_factory=list)
    dont_examples: List[str] = Field(default_factory=list)
    rules: List[RuleDef] = Field(default_factory=list)
    terminology: List[TermDef] = Field(default_factory=list)
    colours: List[ColorDef] = Field(default_factory=list)
    min_contrast_normal: Optional[float] = None
    min_contrast_large: Optional[float] = None
    target_reading_ease: Optional[float] = None


class WizardAnswers(BaseModel):
    content_type: str = "webpage"
    industry: str = "general"
    occasion: str = "everyday"
    locale: str = "global"
    tone: str = "professional"
    company_name: Optional[str] = ""
    never_use_words: Optional[str] = ""


# In-memory fragment cache loaded and validated at startup
LOADED_FRAGMENTS: Dict[str, Dict[str, RulesetFragment]] = {
    "industry": {},
    "occasion": {},
    "locale": {},
    "tone": {},
}


def is_ast_nullable(items: Any) -> bool:
    """Check if an AST node sequence can match an empty string."""
    items_list = list(items) if items is not None else []
    if not items_list:
        return True
    for op, av in items_list:
        if op in (MAX_REPEAT, MIN_REPEAT):
            rmin, rmax, sub = av
            if rmin > 0 and not is_ast_nullable(sub):
                return False
        elif op == SUBPATTERN:
            if not is_ast_nullable(av[3]):
                return False
        elif op == BRANCH:
            if not any(is_ast_nullable(b) for b in av[1]):
                return False
        elif op == AT:
            continue
        else:
            return False
    return True


def _analyze_ast_safety(ast_nodes: Any, in_large_repeat: bool = False) -> Tuple[bool, str]:
    """
    Recursively inspect regular expression AST for ReDoS vulnerability characteristics.
    Rejects:
      - An unbounded or large (max >= 100) repeat whose body contains another such repeat.
      - Alternations with overlapping/duplicate/nullable branches inside such a repeat.
    """
    for op, av in ast_nodes:
        if op in (MAX_REPEAT, MIN_REPEAT):
            rmin, rmax, sub = av
            is_large = (rmax is not None and rmax >= 100)
            if is_large and in_large_repeat:
                return False, f"Nested unbounded or large repeats detected (inner max={rmax} >= 100)"
            ok, reason = _analyze_ast_safety(sub, in_large_repeat=(in_large_repeat or is_large))
            if not ok:
                return False, reason
        elif op == SUBPATTERN:
            ok, reason = _analyze_ast_safety(av[3], in_large_repeat=in_large_repeat)
            if not ok:
                return False, reason
        elif op == BRANCH:
            branches = [list(b) for b in av[1]]
            if in_large_repeat:
                for b in branches:
                    if is_ast_nullable(b):
                        return False, "Alternation with empty or nullable branch inside unbounded/large repeat"
                for i in range(len(branches)):
                    for j in range(i + 1, len(branches)):
                        b1, b2 = branches[i], branches[j]
                        if b1 == b2:
                            return False, "Alternation with duplicate branches inside unbounded/large repeat"
                        if len(b1) > 0 and len(b2) > 0:
                            if len(b1) <= len(b2) and b2[:len(b1)] == b1:
                                return False, "Alternation with overlapping branch prefixes inside unbounded/large repeat"
                            if len(b2) <= len(b1) and b1[:len(b2)] == b2:
                                return False, "Alternation with overlapping branch prefixes inside unbounded/large repeat"
            for b in branches:
                ok, reason = _analyze_ast_safety(b, in_large_repeat=in_large_repeat)
                if not ok:
                    return False, reason
    return True, ""


def check_pattern_structural_safety(pattern: str) -> Tuple[bool, str]:
    """
    Deterministically validate a regular expression pattern for ReDoS safety without wall-clock timing.
    Performs compilation and AST structural analysis using re._parser (or sre_parse fallback).
    """
    if not isinstance(pattern, str) or not pattern.strip():
        return False, "Pattern cannot be empty"
    try:
        re.compile(pattern)
    except re.error as e:
        return False, f"Regex syntax error: {e}"
    try:
        parsed = sre_parser.parse(pattern)
    except Exception as e:
        return False, f"Regex parse error: {e}"

    return _analyze_ast_safety(parsed)


def is_pattern_redos_safe(pattern: str, **kwargs: Any) -> bool:
    """
    Backward-compatible ReDoS safety check returning a boolean.
    Uses deterministic AST structural analysis (ignoring any wall-clock timeout parameter).
    """
    is_safe, _ = check_pattern_structural_safety(pattern)
    return is_safe


_WIZARD_AVAILABLE: bool = False
_WIZARD_UNAVAILABLE_REASON: str = ""


def is_wizard_available() -> bool:
    """Return whether wizard ruleset fragments are loaded and available."""
    return _WIZARD_AVAILABLE


def get_wizard_unavailable_reason() -> str:
    """Return error reason if wizard is unavailable."""
    return _WIZARD_UNAVAILABLE_REASON


def set_wizard_availability(available: bool, reason: str = "") -> None:
    """Explicitly set wizard availability state (useful for tests and error simulation)."""
    global _WIZARD_AVAILABLE, _WIZARD_UNAVAILABLE_REASON
    _WIZARD_AVAILABLE = available
    _WIZARD_UNAVAILABLE_REASON = reason


def load_and_validate_all_fragments() -> None:
    """Load, validate with Pydantic, and structurally ReDoS-verify all JSON ruleset fragments."""
    global _WIZARD_AVAILABLE, _WIZARD_UNAVAILABLE_REASON
    LOADED_FRAGMENTS["industry"].clear()
    LOADED_FRAGMENTS["occasion"].clear()
    LOADED_FRAGMENTS["locale"].clear()
    LOADED_FRAGMENTS["tone"].clear()
    try:
        for kind in ("industry", "occasion", "locale", "tone"):
            dir_path = os.path.join(RULESETS_DIR, kind)
            if not os.path.isdir(dir_path):
                continue
            for file_path in sorted(glob.glob(os.path.join(dir_path, "*.json"))):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fragment = RulesetFragment(**data)
                # ReDoS and regex compilation check
                for r in fragment.rules:
                    for pat in r.patterns:
                        is_safe, reason = check_pattern_structural_safety(pat)
                        if not is_safe:
                            raise ValueError(
                                f"ReDoS vulnerability detected in ruleset file '{file_path}', "
                                f"rule key '{r.key}', pattern '{pat}': {reason}"
                            )
                LOADED_FRAGMENTS[kind][fragment.id] = fragment
        _WIZARD_AVAILABLE = True
        _WIZARD_UNAVAILABLE_REASON = ""
        logger.info("Wizard ruleset fragments loaded and validated successfully.")
    except Exception as exc:
        _WIZARD_AVAILABLE = False
        _WIZARD_UNAVAILABLE_REASON = str(exc)
        logger.error("Failed to load wizard ruleset fragments: %s", exc)


# Initialize and validate fragments on module import
load_and_validate_all_fragments()


# ---------------------------------------------------------------------------
# Wizard Options Metadata
# ---------------------------------------------------------------------------

WIZARD_OPTIONS = {
    "questions": [
        {
            "id": "content_type",
            "number": 1,
            "title": "What would you like to check?",
            "description": "Choose the type of marketing, digital, or product content to review.",
            "options": [
                {"id": "email", "label": "Marketing email or newsletter", "description": "Promotional campaigns, lead sequences, and subscriber newsletters."},
                {"id": "webpage", "label": "Website page or blog post", "description": "Landing pages, feature overviews, blogs, and support guides."},
                {"id": "social", "label": "Social media post", "description": "Short social copy, announcements, and LinkedIn/X updates."},
                {"id": "ad", "label": "Ad or promotion", "description": "Paid advertising, banner copy, PPC headlines, and display promos."},
                {"id": "press_release", "label": "Press release or announcement", "description": "Official company statements, product debuts, and media alerts."},
                {"id": "product_desc", "label": "Product description", "description": "Catalogue listings, feature cards, and e-commerce packaging copy."},
                {"id": "policy", "label": "Policy or legal page", "description": "Terms of service, privacy statements, and customer guarantees."},
                {"id": "report", "label": "Report or presentation", "description": "White papers, executive decks, quarterly summaries, and slide copy."},
                {"id": "image_logo", "label": "Image or logo", "description": "Visual brand marks, banners, colour contrast, and graphic assets."},
            ],
            "default": "webpage",
        },
        {
            "id": "industry",
            "number": 2,
            "title": "What kind of organisation is this for?",
            "description": "Applies industry-specific compliance standards, prohibited terms, and claims checks.",
            "options": [
                {"id": "tech", "label": "Technology or software", "description": "SaaS platforms, developer tools, AI products, and tech infrastructure."},
                {"id": "finance", "label": "Bank, finance or insurance", "description": "Financial services, treasury management, fintech, and insurance."},
                {"id": "health", "label": "Health, medical or wellness", "description": "Clinical systems, medical devices, wellness apps, and diagnostic tools."},
                {"id": "ecommerce", "label": "Shop or e-commerce", "description": "Retail storefronts, consumer brands, and online shopping portals."},
                {"id": "public_nonprofit", "label": "School, university or government", "description": "Educational institutions, civic agencies, charities, and non-profits."},
                {"id": "general", "label": "Something else", "description": "General business services, consulting, agency work, and other trades."},
            ],
            "default": "general",
        },
        {
            "id": "occasion",
            "number": 3,
            "title": "Is this for a special occasion?",
            "description": "Calibrates urgency, novelty, and sensitivity rules for this specific message.",
            "options": [
                {"id": "everyday", "label": "Just everyday content", "description": "Routine communications, ongoing product information, and standard updates."},
                {"id": "launch", "label": "Launching something new", "description": "Product debuts, new feature introductions, and major releases."},
                {"id": "sale", "label": "Sale or discount", "description": "Promotional events, limited-time savings, and seasonal deals."},
                {"id": "incident", "label": "Handling a problem or incident", "description": "Service downtime notes, incident retrospectives, and customer apology notices."},
                {"id": "investor", "label": "Investor or regulatory update", "description": "Quarterly shareholder letters, earnings summaries, and compliance filings."},
                {"id": "seasonal", "label": "Festival or season", "description": "Holiday campaigns, festival greetings, and seasonal celebrations."},
            ],
            "default": "everyday",
        },
        {
            "id": "locale",
            "number": 4,
            "title": "Where will most readers be?",
            "description": "Enforces regional spelling, currency notations, and local communication standards.",
            "options": [
                {"id": "en_in", "label": "India", "description": "₹ / INR currency conventions, lakh/crore formats, and Indian English spelling."},
                {"id": "en_us", "label": "United States", "description": "American English spelling (color, organize) and $ / USD notation."},
                {"id": "en_gb", "label": "United Kingdom", "description": "British English spelling (colour, organise) and £ / GBP notation."},
                {"id": "en_ca", "label": "Canada", "description": "Canadian English spelling standards and CAD currency clarity."},
                {"id": "en_au", "label": "Australia", "description": "Australian English spelling and AUD GST-inclusive conventions."},
                {"id": "global", "label": "Worldwide", "description": "International plain English with standard ISO currency codes."},
            ],
            "default": "global",
        },
        {
            "id": "tone",
            "number": 5,
            "title": "How should it sound?",
            "description": "Sets reading ease targets and vocabulary formality benchmarks.",
            "options": [
                {"id": "professional", "label": "Professional", "description": "Authoritative, dignified, and objective corporate communication."},
                {"id": "friendly", "label": "Friendly", "description": "Warm, conversational, and approachable community voice."},
                {"id": "clear_simple", "label": "Clear and simple", "description": "Plain language with raised reading ease (65+) and short sentences."},
                {"id": "bold", "label": "Bold and energetic", "description": "Confident, spirited, and action-driven brand expression."},
            ],
            "default": "professional",
        },
    ]
}


# ---------------------------------------------------------------------------
# Composition & Preview Engine (Pure Functions)
# ---------------------------------------------------------------------------

def compose(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Pure function merging fragment rules, terms, colours, and settings from user answers.

    - Deduplicates rules by rule key.
    - Deduplicates terminology by prohibited_term.
    - Stricter accessibility wins (max contrast, max reading ease).
    - Tone sets writing style; locale sets spelling and currency conventions.
    - Produces 5-8 plain-language review summary bullets.
    """
    ans = WizardAnswers(**answers)

    ind_frag = LOADED_FRAGMENTS["industry"].get(ans.industry) or LOADED_FRAGMENTS["industry"]["general"]
    occ_frag = LOADED_FRAGMENTS["occasion"].get(ans.occasion) or LOADED_FRAGMENTS["occasion"]["everyday"]
    loc_frag = LOADED_FRAGMENTS["locale"].get(ans.locale) or LOADED_FRAGMENTS["locale"]["global"]
    tone_frag = LOADED_FRAGMENTS["tone"].get(ans.tone) or LOADED_FRAGMENTS["tone"]["professional"]

    # Deduplicate rules by key
    merged_rules_dict: Dict[str, Dict[str, Any]] = {}
    for frag in (ind_frag, occ_frag, loc_frag, tone_frag):
        for r in frag.rules:
            if r.key not in merged_rules_dict:
                merged_rules_dict[r.key] = r.model_dump()

    # Deduplicate terminology by prohibited term (case-insensitive)
    merged_terms_dict: Dict[str, Dict[str, Any]] = {}
    for frag in (ind_frag, occ_frag, loc_frag, tone_frag):
        for t in frag.terminology:
            t_key = t.prohibited.strip().lower()
            if t_key not in merged_terms_dict:
                merged_terms_dict[t_key] = t.model_dump()

    # Append optional custom never_use_words from Q6
    if ans.never_use_words:
        for custom_word in [w.strip() for w in ans.never_use_words.split(",") if w.strip()]:
            w_key = custom_word.lower()
            if w_key not in merged_terms_dict:
                merged_terms_dict[w_key] = {
                    "preferred": "approved alternate phrasing",
                    "prohibited": custom_word,
                    "replacement": "",
                    "case_sensitive": 0,
                    "notes": f"Prohibited custom brand term configured by user.",
                    "rule_key": "RULE-TERM-01",
                }

    # Strictest accessibility settings
    min_contrast_normal = max(
        [f.min_contrast_normal for f in (ind_frag, occ_frag, loc_frag, tone_frag) if f.min_contrast_normal] or [4.5]
    )
    min_contrast_large = max(
        [f.min_contrast_large for f in (ind_frag, occ_frag, loc_frag, tone_frag) if f.min_contrast_large] or [3.0]
    )
    target_reading_ease = max(
        [f.target_reading_ease for f in (ind_frag, occ_frag, loc_frag, tone_frag) if f.target_reading_ease] or [50.0]
    )

    # Merged colours (take industry palette or neutral default)
    colours = [c.model_dump() for c in ind_frag.colours] or [
        {"name": "Slate Primary", "hex_code": "#1E293B", "usage_role": "Primary headings & text", "max_delta_e": 12.0},
        {"name": "Accent Cobalt", "hex_code": "#2563EB", "usage_role": "Interactive buttons & links", "max_delta_e": 12.0},
    ]

    # Assemble plain-language summary bullets (5-8 bullets)
    summary_bullets: List[str] = []
    # 1. Industry claims bullet
    summary_bullets.extend(ind_frag.summary[:2])
    # 2. Occasion bullet
    summary_bullets.append(occ_frag.summary[0])
    # 3. Locale bullet
    summary_bullets.append(loc_frag.summary[0])
    # 4. Tone bullet
    summary_bullets.append(tone_frag.summary[0])
    # 5. Accessibility bullet
    summary_bullets.append(
        f"WCAG 2.2 AA accessibility (contrast ratio {min_contrast_normal}:1, reading ease {target_reading_ease}+)"
    )
    # 6. Custom words bullet if provided
    if ans.never_use_words:
        summary_bullets.append(f"Prohibited custom words: {ans.never_use_words}")

    # Build profile title
    profile_label = f"{ind_frag.label} · {loc_frag.label} · {occ_frag.label}"
    if ans.company_name:
        profile_label = f"{ans.company_name} ({profile_label})"

    return {
        "profile_label": profile_label,
        "answers": ans.model_dump(),
        "summary": summary_bullets[:8],
        "brand_text": {
            "industry": ind_frag.label,
            "tone_principles": f"{tone_frag.tone_principles} {ind_frag.tone_principles}".strip(),
            "writing_style": f"{loc_frag.writing_style} {tone_frag.writing_style}".strip(),
            "messaging_principles": f"{ind_frag.messaging_principles} {occ_frag.messaging_principles}".strip(),
            "do_examples": ind_frag.do_examples or [f"Draft clear, compliant {ans.content_type} content."],
            "dont_examples": ind_frag.dont_examples or [f"Use unverified superlatives or misleading claims."],
        },
        "accessibility": {
            "min_contrast_normal": min_contrast_normal,
            "min_contrast_large": min_contrast_large,
            "target_reading_ease": target_reading_ease,
        },
        "rules": list(merged_rules_dict.values()),
        "terminology": list(merged_terms_dict.values()),
        "colours": colours,
    }


def get_sample_text_for_answers(answers: Dict[str, Any]) -> str:
    """Generate realistic sample text with at least 3 deliberate findings for the chosen profile."""
    ind = answers.get("industry", "general")
    occ = answers.get("occasion", "everyday")
    loc = answers.get("locale", "global")

    # Sample tailored by industry with deliberate errors (superlative claim, prohibited term, tone issue)
    if ind == "finance":
        return (
            "We are thrilled to unveil our new institutional fund offering guaranteed returns of 18% with 100% risk-free security. "
            "Investors can't lose money with our proven treasury algorithm. Traditional banks are destroying your wealth every single day! "
            "Please do the needful and review the prospectus colour scheme before it's too late."
        )
    elif ind == "tech":
        return (
            "Our unhackable cloud infrastructure guarantees zero downtime ever across all global clusters. "
            "Our magic AI algorithm runs with zero human oversight to replace your entire engineering team permanently! "
            "This revolutionary miracle product changes everything forever. Customise your dashboard colour today."
        )
    elif ind == "health":
        return (
            "Our revolutionary miracle cure guarantees a 100% cure rate for chronic respiratory disorders and replaces doctors worldwide! "
            "Patients can now diagnose yourself without a doctor using our autonomous doctor software. "
            "Take immediate action before it's too late or suffer catastrophic consequences."
        )
    elif ind == "ecommerce":
        return (
            "We guarantee the lowest prices in the world with 100% free with no strings delivery for all shoppers! "
            "Only 3 items left—order in 3 seconds or lose it forever during our insane fire sale. "
            "Every purchase includes a hassle-free lifetime return guarantee with zero conditions attached."
        )
    elif ind == "public_nonprofit":
        return (
            "Our academy provides 100% job placement guaranteed alongside 100% free government money for every single enrolled student. "
            "Enrollment compliance is a mandatory decree or face penalties from the council! "
            "Kindly do the needful and consult the central colour advisory office."
        )
    else:
        return (
            "We are proud to provide the #1 in the world business consulting service with guaranteed zero risk for enterprise clients. "
            "Act now or suffer the consequences before it's too late to salvage your quarterly margins! "
            "Our team leverages a synergistic paradigm to deliver silver bullet results across every regional centre."
        )


# ---------------------------------------------------------------------------
# Database Persistence: Atomic Wizard Profile Creation
# ---------------------------------------------------------------------------

def create_wizard_profile_in_db(conn, answers: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically create a new isolated brand profile in SQLite from wizard answers.

    - Generates new brand ID `wiz-<8 hex>`
    - Inserts brand row
    - Inserts standard Terminology rule `RULE-TERM-01`
    - Inserts all profile rules
    - Inserts all terminology records linked to `RULE-TERM-01`
    - Inserts brand colours
    - Inserts two Pending Verification fact templates
    - Keeps at most 25 wizard profiles in demo mode (deleting oldest unused wizard brands).
    """
    cur = conn.cursor()
    spec = compose(answers)

    # In demo mode: clean up oldest wizard profiles with no audits if count >= 25
    cur.execute("SELECT id FROM brands WHERE id LIKE 'wiz-%' ORDER BY updated_at ASC")
    existing_wiz = [r["id"] for r in cur.fetchall()]
    if len(existing_wiz) >= 25:
        to_check = existing_wiz[: len(existing_wiz) - 23]
        for old_id in to_check:
            cur.execute("SELECT COUNT(*) AS c FROM audits WHERE brand_id = ?", (old_id,))
            if cur.fetchone()["c"] == 0:
                cur.execute("DELETE FROM brands WHERE id = ?", (old_id,))

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    brand_id = f"wiz-{uuid.uuid4().hex[:8]}"

    bt = spec["brand_text"]
    a11y = spec["accessibility"]

    # 1. Insert Brand
    cur.execute(
        """
        INSERT INTO brands (
            id, name, industry, description, tone_principles, writing_style,
            messaging_principles, do_examples, dont_examples, typography_specs,
            spacing_rules, logo_placement_constraints, min_contrast_normal,
            min_contrast_large, require_alt_text, enforce_heading_order,
            target_reading_ease, version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brand_id,
            spec["profile_label"],
            bt["industry"],
            f"Guided audit profile generated for {answers.get('content_type', 'content')}.",
            bt["tone_principles"],
            bt["writing_style"],
            bt["messaging_principles"],
            json.dumps(bt["do_examples"]),
            json.dumps(bt["dont_examples"]),
            "Headings: Inter SemiBold. Body: Inter Regular (14-16px).",
            "Minimum 16px clear space around primary brand elements.",
            "Top-left or centered lockup zone with high-contrast background.",
            a11y["min_contrast_normal"],
            a11y["min_contrast_large"],
            1,
            1,
            a11y["target_reading_ease"],
            1,
            now,
        ),
    )

    # 2. Insert Standard Terminology Rule (Parent Rule for Terminology table)
    term_rule_id = f"RULE-TERM-{uuid.uuid4().hex[:6]}"
    cur.execute(
        """
        INSERT INTO rules (
            id, brand_id, pillar, title, description, rule_config_json,
            severity, do_example, dont_example, active, version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            term_rule_id,
            brand_id,
            "Terminology",
            "Enforce Approved Wording & Prohibited Terms",
            "Use preferred brand terms and avoid prohibited, deprecated, or misleading vocabulary.",
            json.dumps({"source": "terminology_table"}),
            "high",
            "Use clear, approved product names and straightforward terminology.",
            "Avoid deprecated names and prohibited expressions.",
            1,
            1,
            now,
        ),
    )

    # 3. Insert Custom Profile Rules
    for idx, r in enumerate(spec["rules"]):
        r_id = f"RULE-{uuid.uuid4().hex[:6]}"
        cfg = {
            "patterns": r["patterns"],
            "suggested_replacements": r.get("suggested_replacements", {}),
            "prohibited_patterns": r["patterns"],
            "replacement": r.get("suggested_replacements", {}).get(r["patterns"][0], "") if r["patterns"] else "",
        }
        cur.execute(
            """
            INSERT INTO rules (
                id, brand_id, pillar, title, description, rule_config_json,
                severity, do_example, dont_example, active, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r_id,
                brand_id,
                r["pillar"],
                r["title"],
                r["description"],
                json.dumps(cfg),
                r["severity"],
                r.get("do_example", ""),
                r.get("dont_example", ""),
                1,
                1,
                now,
            ),
        )

    # 4. Insert Terminology Records
    for t in spec["terminology"]:
        t_id = f"TERM-{uuid.uuid4().hex[:6]}"
        cur.execute(
            """
            INSERT INTO terminology (
                id, brand_id, preferred_term, prohibited_term, replacement_term,
                case_sensitive, notes, rule_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t_id,
                brand_id,
                t["preferred"],
                t["prohibited"],
                t.get("replacement") or t["preferred"],
                t.get("case_sensitive", 0),
                t.get("notes", ""),
                term_rule_id,
                now,
            ),
        )

    # 5. Insert Brand Colours
    for c in spec["colours"]:
        c_id = f"COL-{uuid.uuid4().hex[:6]}"
        cur.execute(
            """
            INSERT INTO brand_colors (
                id, brand_id, name, hex_code, usage_role, max_delta_e
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                c_id,
                brand_id,
                c["name"],
                c["hex_code"],
                c["usage_role"],
                c.get("max_delta_e", 12.0),
            ),
        )

    # 6. Insert Two Template Pending Verification Facts
    cur.execute(
        """
        INSERT INTO verified_facts (
            id, brand_id, statement, numeric_value, numeric_units, product_context,
            source_reference, applicable_conditions, date_version, verification_status,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"FACT-{uuid.uuid4().hex[:6]}",
            brand_id,
            "Template benchmark: up to 45% efficiency gain in internal pilot trial.",
            "45",
            "% gain",
            "Productivity benchmark template",
            "Internal Lab Report (Template)",
            "Observed across preliminary evaluation cohort; pending formal compliance sign-off.",
            "2026-Q4-Template",
            "Pending Verification",
            now,
        ),
    )

    cur.execute(
        """
        INSERT INTO verified_facts (
            id, brand_id, statement, numeric_value, numeric_units, product_context,
            source_reference, applicable_conditions, date_version, verification_status,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"FACT-{uuid.uuid4().hex[:6]}",
            brand_id,
            "Service uptime target of 99.9% excluding scheduled maintenance.",
            "99.9",
            "% uptime target",
            "System availability template",
            "Standard Service Level Agreement (Template)",
            "Excludes scheduled maintenance windows communicated 7 days in advance.",
            "2026-v1-Template",
            "Pending Verification",
            now,
        ),
    )

    return {
        "brand_id": brand_id,
        "name": spec["profile_label"],
        "summary": spec["summary"],
        "rules_count": len(spec["rules"]) + 1,
        "terminology_count": len(spec["terminology"]),
        "sample_text": get_sample_text_for_answers(answers),
    }
