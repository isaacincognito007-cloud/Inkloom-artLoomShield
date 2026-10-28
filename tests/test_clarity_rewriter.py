import os
from fastapi.testclient import TestClient

from backend.clarity_rewriter import (
    AMBIGUITY_FORMULA,
    correlate_ambiguity_and_overrides,
    extract_numeric_tokens,
    generate_candidate_rewrite,
    load_vague_lexicon,
    score_rule_ambiguity,
)
from backend.database import get_connection, init_db, reset_demo_workspace
from backend.main import app

client = TestClient(app)


def setup_function():
    os.environ["LOOMSHIELD_WORKSPACE_MODE"] = "demo"
    init_db()
    reset_demo_workspace()


def test_b1_scorer_determinism_with_golden_fixtures():
    lex = load_vague_lexicon()
    golden_vague = (
        "Maintain an appropriate amount of technical detail when appropriate and keep copy reasonably concise."
    )
    res1 = score_rule_ambiguity(golden_vague, do_example="", dont_example="", lexicon=lex)
    res2 = score_rule_ambiguity(golden_vague, do_example="", dont_example="", lexicon=lex)

    assert res1 == res2
    assert res1["score"] == 100
    assert res1["is_vague"] is True
    assert res1["subjective_only"] is True
    assert res1["formula"] == AMBIGUITY_FORMULA
    assert len(res1["matched_spans"]) >= 3
    for sp in res1["matched_spans"]:
        assert golden_vague[sp["start"]:sp["end"]].lower() == sp["phrase"].lower()

    golden_clear = (
        "Limit display headlines to at most 12 words and define every protocol acronym on first use."
    )
    clear_res = score_rule_ambiguity(
        golden_clear,
        do_example="Use ISO 20022 (International Organization for Standardization messaging standard) in body copy.",
        dont_example="Do not exceed 12 words in display headlines.",
        lexicon=lex,
    )
    assert clear_res["score"] == 0
    assert clear_res["is_vague"] is False
    assert clear_res["matched_spans"] == []


def test_b2_minimum_sample_rule_and_priority_correlation():
    vague_eval = {"score": 65, "is_vague": True}
    clear_eval = {"score": 0, "is_vague": False}

    # Below minimum sample (e.g. 2 audits < min_sample 5) -> "Not enough data" or "Vague (no usage data)"
    low_sample_vague = correlate_ambiguity_and_overrides(
        ambiguity=vague_eval,
        violations_count=4,
        overrides_count=3,
        audits_sample_count=2,
        min_sample=5,
    )
    assert low_sample_vague["sufficient_sample"] is False
    assert low_sample_vague["override_rate_display"] == "Not enough data"
    assert low_sample_vague["classification_label"] == "Vague (no usage data)"
    assert low_sample_vague["priority"] != "High"

    low_sample_clear = correlate_ambiguity_and_overrides(
        ambiguity=clear_eval,
        violations_count=2,
        overrides_count=0,
        audits_sample_count=2,
        min_sample=5,
    )
    assert low_sample_clear["override_rate_display"] == "Not enough data"
    assert low_sample_clear["classification_label"] == "Not enough data"

    # Above minimum sample (6 audits >= 5), vague AND override rate > 20% -> High priority
    high_prio = correlate_ambiguity_and_overrides(
        ambiguity=vague_eval,
        violations_count=5,
        overrides_count=2,  # 40% > 20%
        audits_sample_count=6,
        min_sample=5,
    )
    assert high_prio["sufficient_sample"] is True
    assert high_prio["override_rate"] == 40.0
    assert high_prio["priority"] == "High"

    # Above minimum sample, vague but 0 usage data -> "Vague (no usage data)"
    vague_no_usage = correlate_ambiguity_and_overrides(
        ambiguity=vague_eval,
        violations_count=0,
        overrides_count=0,
        audits_sample_count=6,
        min_sample=5,
    )
    assert vague_no_usage["classification_label"] == "Vague (no usage data)"
    assert vague_no_usage["priority"] == "Medium"


def test_b3_property_no_candidate_contains_invented_number_and_placeholder_when_no_fact():
    synthetic_facts = [
        {
            "id": "FACT-BENCH-64",
            "statement": "Cross-border settlement throughput is up to 64% faster under approved benchmark conditions.",
            "numeric_value": "64",
            "numeric_units": "%",
            "product_context": "Cross-border settlement throughput speed",
            "applicable_conditions": "T+0 clearing corridors",
            "verification_status": "Verified",
        },
        {
            "id": "FACT-SLA-9999",
            "statement": "Platform provides a 99.99% contractual uptime SLA.",
            "numeric_value": "99.99",
            "numeric_units": "%",
            "product_context": "Contractual uptime reliability SLA",
            "applicable_conditions": "Active-active regions",
            "verification_status": "Verified",
        },
    ]

    synthetic_rules = [
        {
            "id": "RULE-PROP-1",
            "title": "Technical Detail Balance",
            "description": "Use an appropriate amount of technical detail when appropriate in customer copy.",
            "do_example": "",
            "dont_example": "",
        },
        {
            "id": "RULE-PROP-2",
            "title": "Cross-Border Settlement Speed Claims",
            "description": "Keep cross-border settlement throughput speed claims reasonably accurate and generally modest.",
            "do_example": "",
            "dont_example": "",
        },
        {
            "id": "RULE-PROP-3",
            "title": "Headline Brevity Within 14 Words",
            "description": "Headlines should be reasonably brief and stay under 14 words where suitable.",
            "do_example": "",
            "dont_example": "",
        },
        {
            "id": "RULE-PROP-4",
            "title": "Visual Spacing",
            "description": "Provide adequate whitespace and sufficient margin around cards as needed.",
            "do_example": "",
            "dont_example": "",
        },
    ]

    for rule in synthetic_rules:
        cand = generate_candidate_rewrite(rule=rule, verified_facts=synthetic_facts, past_findings=[])
        new_text = cand["new_text"]
        numbers_in_candidate = set(extract_numeric_tokens(new_text))

        rule_nums = set(extract_numeric_tokens(f"{rule['title']} {rule['description']}"))
        fact_nums = set()
        if cand.get("cited_fact_id"):
            matched_f = next(f for f in synthetic_facts if f["id"] == cand["cited_fact_id"])
            fact_blob = " ".join(
                str(matched_f.get(k, ""))
                for k in ("id", "statement", "numeric_value", "numeric_units", "applicable_conditions")
            )
            fact_nums = set(extract_numeric_tokens(fact_blob))

        allowed_nums = rule_nums | fact_nums
        assert numbers_in_candidate.issubset(allowed_nums), (
            f"Candidate invented numbers {numbers_in_candidate - allowed_nums} in '{new_text}'"
        )

    # Rule with no numbers and no matching verified facts must insert [SET THRESHOLD: unit]
    no_fact_cand = generate_candidate_rewrite(
        rule=synthetic_rules[3],
        verified_facts=[],
        past_findings=[],
    )
    assert "[SET THRESHOLD: unit]" in no_fact_cand["new_text"]
    assert extract_numeric_tokens(no_fact_cand["new_text"]) == []
    assert no_fact_cand["ambiguity_after"] < no_fact_cand["ambiguity_before"]


def test_b3_no_improvement_found_when_already_optimal():
    already_clear_rule = {
        "id": "RULE-CLEAR-01",
        "title": "Acronym Definition",
        "description": "Define every protocol acronym within 10 words of first use.",
        "do_example": "Use ISO 20022 (International Organization for Standardization standard) in paragraph 1.",
        "dont_example": "Do not use undefined acronyms in customer-facing headlines.",
    }
    cand = generate_candidate_rewrite(rule=already_clear_rule, verified_facts=[], past_findings=[])
    assert cand["improved"] is False
    assert cand["status"] == "no improvement found"
    assert cand["message"] == "no improvement found"


def test_b4_b5_permissions_approve_bumps_version_logs_event_and_reject_leaves_vault_unchanged():
    # 1. Content Creator (Priya) and Reviewer (Marcus) get 403 on propose, approve, reject
    priya_token = client.post("/api/demo/login", json={"user_id": "usr_priya"}).json()["token"]
    marcus_token = client.post("/api/demo/login", json={"user_id": "usr_marcus"}).json()["token"]
    ava_token = client.post("/api/demo/login", json={"user_id": "usr_ava"}).json()["token"]

    for tok in (priya_token, marcus_token):
        r_prop = client.post(
            "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
            headers={"Authorization": f"Bearer {tok}"},
            json={},
        )
        assert r_prop.status_code == 403

        r_app = client.post(
            "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/approve",
            headers={"Authorization": f"Bearer {tok}"},
            json={},
        )
        assert r_app.status_code == 403

    # 2. Brand Administrator (Ava) proposes and rejects -> vault unchanged
    vault_before = client.get("/api/vault/novapay").json()
    ver_before = vault_before["brand"]["version"]
    rule_before = next(r for r in vault_before["rules"] if r["id"] == "RULE-TONE-02")

    prop_res = client.post(
        "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
        headers={"Authorization": f"Bearer {ava_token}"},
        json={},
    )
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert prop_data["status"] == "proposed"
    assert prop_data["ambiguity_after"] < prop_data["ambiguity_before"]

    rej_res = client.post(
        f"/api/ambiguity-radar/novapay/revisions/{prop_data['id']}/reject",
        headers={"Authorization": f"Bearer {ava_token}"},
        json={"reason": "Keep original phrasing until Q1 style council review."},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    vault_after_reject = client.get("/api/vault/novapay").json()
    assert vault_after_reject["brand"]["version"] == ver_before
    rule_after_reject = next(r for r in vault_after_reject["rules"] if r["id"] == "RULE-TONE-02")
    assert rule_after_reject["description"] == rule_before["description"]

    # 3. Brand Administrator (Ava) proposes and approves -> updates rule, bumps brand_version, logs audit event
    prop2 = client.post(
        "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
        headers={"Authorization": f"Bearer {ava_token}"},
        json={},
    ).json()

    app_res = client.post(
        f"/api/ambiguity-radar/novapay/revisions/{prop2['id']}/approve",
        headers={"Authorization": f"Bearer {ava_token}"},
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "approved"
    assert app_data["brand_version_after"] == ver_before + 1
    assert app_data["audit_event"]["event_type"] == "guideline_revision_approved"

    vault_after_approve = client.get("/api/vault/novapay").json()
    assert vault_after_approve["brand"]["version"] == ver_before + 1
    rule_after_approve = next(r for r in vault_after_approve["rules"] if r["id"] == "RULE-TONE-02")
    assert rule_after_approve["description"] == prop2["new_text"]

    # Verify audit event is persisted in audit_events table
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_events WHERE event_type = 'guideline_revision_approved'")
    ev_rows = cur.fetchall()
    conn.close()
    assert len(ev_rows) >= 1

    # B5: Verify loop closure is returned in GET /api/ambiguity-radar/novapay
    radar = client.get("/api/ambiguity-radar/novapay").json()
    r_tone = next(r for r in radar["rules_analysis"] if r["rule_id"] == "RULE-TONE-02")
    assert r_tone["loop_closure"] is not None
    assert "Revised " in r_tone["loop_closure"]["display"]
    assert "override rate since revision" in r_tone["loop_closure"]["display"]


def test_b7_idempotent_migration_and_ui_escaping():
    # Calling init_db() repeatedly must be 100% idempotent
    init_db()
    init_db()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(guideline_revisions)")
    cols = {row["name"] for row in cur.fetchall()}
    conn.close()

    required_cols = {
        "id",
        "rule_id",
        "old_text",
        "new_text",
        "do_examples",
        "dont_examples",
        "ambiguity_before",
        "ambiguity_after",
        "status",
        "created_by",
        "decided_by",
        "decided_at",
        "brand_version_before",
        "brand_version_after",
    }
    assert required_cols.issubset(cols)

    # Verify frontend/app.js escapes rule text in renderRuleTextWithVagueSpans
    app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "app.js"))
    with open(app_js_path, "r", encoding="utf-8") as fh:
        js_code = fh.read()
    assert "function renderRuleTextWithVagueSpans" in js_code
    assert "escapeHtml(text.slice(cursor, start))" in js_code
    assert "escapeHtml(text.slice(start, end))" in js_code
    assert "suggestion for human sign-off" in js_code.lower()
