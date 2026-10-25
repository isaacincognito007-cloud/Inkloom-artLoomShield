import pytest
from fastapi.testclient import TestClient
from backend.main import app, audit_rate_limiter
from backend.database import get_connection, init_db, reset_demo_workspace
from backend.wizard import (
    LOADED_FRAGMENTS,
    WIZARD_OPTIONS,
    compose,
    get_sample_text_for_answers,
    is_pattern_redos_safe,
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
