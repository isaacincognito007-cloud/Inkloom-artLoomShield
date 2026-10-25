import json
import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app, audit_rate_limiter
from backend.database import get_connection, init_db, reset_demo_workspace
from backend.wizard import (
    LOADED_FRAGMENTS,
    RULESETS_DIR,
    WIZARD_OPTIONS,
    check_pattern_structural_safety,
    compose,
    get_sample_text_for_answers,
    is_pattern_redos_safe,
    is_wizard_available,
    load_and_validate_all_fragments,
    set_wizard_availability,
)
from backend.engine import run_six_pillar_audit

client = TestClient(app)


def test_fragments_loaded_and_validated():
    """All 6 industry, 6 occasion, 6 locale, and 4 tone fragments are loaded and valid."""
    assert len(LOADED_FRAGMENTS["industry"]) >= 6
    assert len(LOADED_FRAGMENTS["occasion"]) >= 6
    assert len(LOADED_FRAGMENTS["locale"]) >= 6
    assert len(LOADED_FRAGMENTS["tone"]) >= 4

    for kind, frags in LOADED_FRAGMENTS.items():
        for fid, frag in frags.items():
            assert frag.id == fid
            assert frag.label
            assert len(frag.summary) >= 1
            # Maximum 4 rules and 8 terms per fragment constraint
            assert len(frag.rules) <= 4, f"{fid} exceeded 4 rules limit"
            assert len(frag.terminology) <= 8, f"{fid} exceeded 8 terms limit"


def test_every_fragment_regex_redos_safe():
    """Every regex pattern in all fragments compiles and passes 5,000-char ReDoS safety checks."""
    for kind, frags in LOADED_FRAGMENTS.items():
        for fid, frag in frags.items():
            for rule in frag.rules:
                for pat in rule.patterns:
                    assert is_pattern_redos_safe(pat, timeout_sec=0.05) is True, f"ReDoS failure in {fid}: {pat}"


def test_compose_pure_function_merges_multiple_answer_sets():
    """compose() merges fragments, deduplicates, enforces stricter accessibility, and formats labels."""
    # Test Set A: Tech + Launch + US + Bold
    ans_a = {"industry": "tech", "occasion": "launch", "locale": "en_us", "tone": "bold"}
    spec_a = compose(ans_a)
    assert "Technology or software" in spec_a["profile_label"]
    assert "Launching something new" in spec_a["profile_label"]
    assert "United States" in spec_a["profile_label"]
    assert len(spec_a["summary"]) >= 5
    assert len(spec_a["summary"]) <= 8

    # Test Set B: Finance + Sale + UK + Clear Simple (raises reading ease to 65+)
    ans_b = {
        "industry": "finance",
        "occasion": "sale",
        "locale": "en_gb",
        "tone": "clear_simple",
        "never_use_words": "shady, crypto-scheme",
    }
    spec_b = compose(ans_b)
    assert spec_b["accessibility"]["target_reading_ease"] >= 65.0
    terms = [t["prohibited"] for t in spec_b["terminology"]]
    assert "shady" in terms
    assert "crypto-scheme" in terms


def test_wizard_options_endpoint():
    """GET /api/wizard/options returns question tiles, options, and descriptions."""
    res = client.get("/api/wizard/options")
    assert res.status_code == 200
    data = res.json()
    assert "questions" in data
    assert len(data["questions"]) == 5
    q_ids = [q["id"] for q in data["questions"]]
    assert "content_type" in q_ids
    assert "industry" in q_ids
    assert "occasion" in q_ids
    assert "locale" in q_ids
    assert "tone" in q_ids


def test_wizard_preview_endpoint_does_not_write_db():
    """POST /api/wizard/preview returns summary bullets and tailored sample text without writing to database."""
    conn = get_connection()
    count_before = conn.execute("SELECT COUNT(*) AS c FROM brands").fetchone()["c"]
    conn.close()

    payload = {
        "content_type": "email",
        "industry": "ecommerce",
        "occasion": "sale",
        "locale": "global",
        "tone": "friendly",
    }
    res = client.post("/api/wizard/preview", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert len(data["summary"]) >= 5
    assert "sample_text" in data
    assert "prices" in data["sample_text"].lower() or "sale" in data["sample_text"].lower()

    conn = get_connection()
    count_after = conn.execute("SELECT COUNT(*) AS c FROM brands").fetchone()["c"]
    conn.close()
    assert count_after == count_before


def test_wizard_profile_creation_atomic_and_never_modifies_existing_brands():
    """POST /api/wizard/profile atomically creates new brand and never mutates existing brands."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, version FROM brands WHERE id = 'novapay'")
    nova_before = dict(cur.fetchone())
    conn.close()

    payload = {
        "content_type": "webpage",
        "industry": "health",
        "occasion": "incident",
        "locale": "en_us",
        "tone": "professional",
        "company_name": "Apex Diagnostics",
        "never_use_words": "hocus-pocus",
    }
    res = client.post("/api/wizard/profile", json=payload)
    assert res.status_code == 200
    data = res.json()
    brand_id = data["brand_id"]
    assert brand_id.startswith("wiz-")
    assert "Apex Diagnostics" in data["profile_label"]

    # Verify atomic DB rows created
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM brands WHERE id = ?", (brand_id,))
    brand_row = cur.fetchone()
    assert brand_row is not None
    assert brand_row["min_contrast_normal"] >= 4.5

    cur.execute("SELECT COUNT(*) AS c FROM rules WHERE brand_id = ?", (brand_id,))
    rule_count = cur.fetchone()["c"]
    assert rule_count >= 2

    cur.execute("SELECT COUNT(*) AS c FROM terminology WHERE brand_id = ?", (brand_id,))
    term_count = cur.fetchone()["c"]
    assert term_count >= 2

    cur.execute("SELECT COUNT(*) AS c FROM brand_colors WHERE brand_id = ?", (brand_id,))
    color_count = cur.fetchone()["c"]
    assert color_count >= 2

    cur.execute("SELECT COUNT(*) AS c FROM verified_facts WHERE brand_id = ?", (brand_id,))
    fact_count = cur.fetchone()["c"]
    assert fact_count == 2

    # Verify novapay remains untouched
    cur.execute("SELECT id, name, version FROM brands WHERE id = 'novapay'")
    nova_after = dict(cur.fetchone())
    conn.close()
    assert nova_after["version"] == nova_before["version"]
    assert nova_after["name"] == nova_before["name"]


def test_sample_text_yields_at_least_three_findings():
    """Each industry example text produces at least 3 findings against its generated profile."""
    industries = ["general", "tech", "finance", "health", "ecommerce", "public_nonprofit"]
    for ind in industries:
        answers = {"industry": ind, "occasion": "everyday", "locale": "global", "tone": "professional"}
        res = client.post("/api/wizard/profile", json=answers)
        assert res.status_code == 200
        data = res.json()
        brand_id = data["brand_id"]
        vault = data["vault"]
        sample_text = data["sample_text"]

        audit_res = run_six_pillar_audit(
            content=sample_text,
            brand=vault["brand"],
            rules=vault["rules"],
            terminology_rows=vault["terminology"],
            facts=vault["verified_facts"],
            brand_colors=vault.get("colors") or vault.get("brand_colors", []),
        )
        findings = audit_res["findings"]
        assert len(findings) >= 3, f"Industry '{ind}' sample yielded {len(findings)} findings (< 3 required)"


def test_wizard_profile_forbidden_for_role_without_run_audits(monkeypatch):
    """Users lacking run_audits permission receive 403 Forbidden on wizard profile creation."""
    from backend import config
    monkeypatch.setitem(config.ROLE_PERMISSIONS["Content Creator"], "run_audits", False)
    monkeypatch.setenv("LOOMSHIELD_USER_ROLE", "Content Creator")

    res = client.post(
        "/api/wizard/profile",
        json={"industry": "general", "occasion": "everyday"},
    )
    assert res.status_code == 403
    assert "permission" in res.json()["detail"].lower()


def test_reset_demo_workspace_still_works_cleanly():
    """reset_demo_workspace restores initial workspace brands and does not error."""
    reset_demo_workspace()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM brands WHERE id IN ('novapay', 'verdant')")
    assert cur.fetchone()["c"] == 2
    conn.close()


def test_all_builtin_rulesets_load_successfully():
    """All built-in rulesets load successfully and wizard is marked available."""
    assert is_wizard_available() is True
    assert len(LOADED_FRAGMENTS["industry"]) >= 6
    assert len(LOADED_FRAGMENTS["occasion"]) >= 6
    assert len(LOADED_FRAGMENTS["locale"]) >= 6
    assert len(LOADED_FRAGMENTS["tone"]) >= 4

    for kind, frags in LOADED_FRAGMENTS.items():
        for fid, frag in frags.items():
            for rule in frag.rules:
                for pat in rule.patterns:
                    safe, reason = check_pattern_structural_safety(pat)
                    assert safe is True, f"Structural check failed for {fid} ({rule.key}): {reason}"


def test_specific_patterns_pass_validation():
    """Specific patterns from sale.json, everyday.json, and industry/general.json pass validation."""
    check_files = [
        os.path.join(RULESETS_DIR, "occasion", "sale.json"),
        os.path.join(RULESETS_DIR, "occasion", "everyday.json"),
        os.path.join(RULESETS_DIR, "industry", "general.json"),
    ]
    for fp in check_files:
        assert os.path.exists(fp), f"Ruleset file {fp} does not exist"
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("rules", []):
            for pat in r.get("patterns", []):
                safe, reason = check_pattern_structural_safety(pat)
                assert safe is True, f"Pattern '{pat}' in {fp} ({r.get('key')}) rejected: {reason}"


def test_syntax_errors_rejected_with_clear_reason():
    """Patterns with syntax errors are rejected with a clear reason."""
    invalid_patterns = [
        (r"(?P<unclosed", "Regex parse error"),
        (r"[a-z", "Regex syntax error"),
        (r"*abc", "Regex syntax error"),
        (r"+", "Regex syntax error"),
        (r"(", "Regex syntax error"),
    ]
    for pat, _ in invalid_patterns:
        safe, reason = check_pattern_structural_safety(pat)
        assert safe is False, f"Invalid pattern '{pat}' was erroneously accepted"
        assert len(reason) > 0, f"No reason provided for invalid pattern '{pat}'"
        assert any(keyword in reason.lower() for keyword in ("syntax", "parse", "error")), (
            f"Reason '{reason}' does not explain syntax error for '{pat}'"
        )


def test_catastrophic_backtracking_patterns_rejected():
    """Patterns known to cause catastrophic backtracking are rejected with clear reasons."""
    dangerous_patterns = [
        ("(a+)+$", "Nested unbounded or large repeats detected"),
        ("(a|aa)+$", "Alternation with empty or nullable branch"),
        ("(.*)*", "Nested unbounded or large repeats detected"),
        ("([0-9]{1,150}){1,100}", "Nested unbounded or large repeats detected"),
        ("(ab|cd|ab)+", "Alternation with duplicate branches"),
    ]
    for pat, expected_subreason in dangerous_patterns:
        safe, reason = check_pattern_structural_safety(pat)
        assert safe is False, f"Dangerous pattern '{pat}' was erroneously accepted"
        assert expected_subreason in reason, f"Expected '{expected_subreason}' in reason '{reason}' for pattern '{pat}'"


def test_validation_is_deterministic_loop():
    """Validation is deterministic: run 100 times in a loop and assert identical results every time."""
    test_cases = [
        (r"\b(?:returns?|profits?|yield)\b", True),
        (r"\b(?:lowest\s+prices?\s+in\s+the\s+world)\b", True),
        ("(cat|dog)+$", True),
        (r"\d+%", True),
        ("(a+)+$", False),
        ("(a|aa)+$", False),
        ("(.*)*", False),
        (r"(?P<invalid", False),
    ]
    baseline = [check_pattern_structural_safety(pat) for pat, _ in test_cases]
    for idx, (pat, expected_safe) in enumerate(test_cases):
        assert baseline[idx][0] == expected_safe

    for _ in range(100):
        current = [check_pattern_structural_safety(pat) for pat, _ in test_cases]
        assert current == baseline


def test_wizard_failure_returns_503_while_health_and_audits_work():
    """When wizard is unavailable, /api/wizard/* returns structured 503, but /api/health and audits return 200."""
    try:
        set_wizard_availability(False, "Simulated ruleset fragment corruption")
        assert is_wizard_available() is False

        # 1. Wizard options endpoint returns 503 structured error
        res_opts = client.get("/api/wizard/options")
        assert res_opts.status_code == 503
        data_opts = res_opts.json()
        assert data_opts["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "Guided setup is temporarily unavailable" in data_opts["error"]["message"]

        # 2. Wizard preview endpoint returns 503 structured error
        res_prev = client.post("/api/wizard/preview", json={"industry": "tech"})
        assert res_prev.status_code == 503
        data_prev = res_prev.json()
        assert data_prev["error"]["code"] == "SERVICE_UNAVAILABLE"

        # 3. Wizard profile endpoint returns 503 structured error
        res_prof = client.post("/api/wizard/profile", json={"industry": "tech"})
        assert res_prof.status_code == 503
        data_prof = res_prof.json()
        assert data_prof["error"]["code"] == "SERVICE_UNAVAILABLE"

        # 4. /api/health still returns 200
        res_health = client.get("/api/health")
        assert res_health.status_code == 200

        # 5. Audits endpoint still returns 200
        audit_payload = {
            "brand_id": "novapay",
            "document_name": "Resilience Test Post",
            "input_format": "text",
            "content": "NovaPay provides simple payments across borders.",
            "confidential_mode": True,
        }
        res_audit = client.post("/api/audits", json=audit_payload)
        assert res_audit.status_code == 200
        assert "id" in res_audit.json()
    finally:
        load_and_validate_all_fragments()
        assert is_wizard_available() is True


def test_vault_rule_creation_rejects_unsafe_regex():
    """Vault rule creation and update reject unsafe regexes with 422 Unprocessable Entity."""
    # 1. ReDoS pattern with nested repeats
    res_unsafe = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Unsafe Repeat Rule",
            "description": "Test rule containing ReDoS pattern",
            "severity": "high",
            "pattern_regex": "(a+)+$",
        },
    )
    assert res_unsafe.status_code == 422
    data_unsafe = res_unsafe.json()
    assert "Rule pattern rejected" in data_unsafe["detail"]
    assert "Nested unbounded or large repeats" in data_unsafe["detail"]

    # 2. ReDoS pattern with overlapping branches inside repeat
    res_unsafe_branch = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Unsafe Branch Rule",
            "description": "Test rule containing ReDoS alternation pattern",
            "severity": "high",
            "pattern_regex": "(a|aa)+$",
        },
    )
    assert res_unsafe_branch.status_code == 422
    assert "Rule pattern rejected" in res_unsafe_branch.json()["detail"]

    # 3. Syntax error in regex
    res_syntax = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Invalid Syntax Rule",
            "description": "Test rule containing syntax error",
            "severity": "high",
            "pattern_regex": "(?P<unclosed",
        },
    )
    assert res_syntax.status_code == 422
    assert "Rule pattern rejected" in res_syntax.json()["detail"]

    # 4. Safe pattern succeeds
    res_safe = client.post(
        "/api/vault/novapay/rules",
        json={
            "pillar": "Tone and Voice",
            "title": "Safe Test Rule",
            "description": "Test rule containing safe pattern",
            "severity": "medium",
            "pattern_regex": r"\b(?:safe_word|another_safe_word)\b",
        },
    )
    assert res_safe.status_code == 200
    rule_id = res_safe.json()["rule_id"]

    # 5. Updating existing rule with unsafe regex also rejects with 422
    res_update_unsafe = client.put(
        f"/api/vault/novapay/rules/{rule_id}",
        json={
            "pillar": "Tone and Voice",
            "title": "Safe Test Rule Updated",
            "description": "Update attempt with ReDoS pattern",
            "severity": "medium",
            "pattern_regex": "(.*)*",
        },
    )
    assert res_update_unsafe.status_code == 422
    assert "Rule pattern rejected" in res_update_unsafe.json()["detail"]
