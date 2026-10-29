import os

import pytest
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


@pytest.fixture(autouse=True)
def demo_workspace(monkeypatch):
    # F11: scoped via monkeypatch so demo mode never leaks into other test modules.
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
    init_db()
    reset_demo_workspace()
    yield


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


# ============================================================================
# DAY 3 HARDENING: F4, F5, F6
# ============================================================================

import re

import backend.main as main_mod
from backend.main import get_brand_vault_bundle


def _token(user_id):
    return client.post("/api/demo/login", json={"user_id": user_id}).json()["token"]


def test_f4_rule_tone_02_never_receives_fact_101_article_agreement_and_nonzero_ambiguity_after():
    vault = get_brand_vault_bundle("novapay")
    facts = vault["verified_facts"]
    assert any(f["id"] == "FACT-101" for f in facts)
    tone02 = next(r for r in vault["rules"] if r["id"] == "RULE-TONE-02")

    # (a) Generator level: a tone rule is not quantity-type, so no Verified Fact is cited.
    cand = generate_candidate_rewrite(rule=tone02, verified_facts=facts, past_findings=[])
    assert cand["cited_fact_id"] is None
    assert "FACT-101" not in cand["new_text"]
    assert cand["threshold_source"] == "placeholder"
    assert "[SET THRESHOLD: unit]" in cand["new_text"]

    # (a) API level: the proposal stored for RULE-TONE-02 never cites FACT-101.
    ava = _token("usr_ava")
    prop = client.post(
        "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
        headers={"Authorization": f"Bearer {ava}"},
        json={},
    )
    assert prop.status_code == 200
    assert "FACT-101" not in prop.json()["new_text"]
    assert "64" not in extract_numeric_tokens(prop.json()["new_text"])

    # (b) "Use an appropriate amount..." never produces "an a"; the article agrees with the replacement.
    art = generate_candidate_rewrite(
        rule={"id": "RULE-ART", "title": "Detail", "pillar": "Tone and Voice",
              "description": "Use an appropriate amount of technical detail."},
        verified_facts=facts,
    )
    low = art["new_text"].lower()
    assert "an a " not in low
    assert not re.search(r"\ban\s+[bcdfgjklmnpqrstvwxyz]", low)
    assert not re.search(r"\ba\s+[aeio]", low)
    assert art["new_text"].startswith("Use a ")

    # (b) Prepositional replacement consumes "in a ... manner" instead of producing "in a within".
    msg = generate_candidate_rewrite(
        rule={"id": "RULE-PREP", "title": "Notices", "pillar": "Messaging",
              "description": "Operational status updates must be sent in a timely manner."},
        verified_facts=[],
    )
    assert "in a within" not in msg["new_text"].lower()
    assert "manner" not in msg["new_text"].lower()

    # (c) An unrelated fact must not be appended just to drive ambiguity_after to 0.
    unrelated = [{
        "id": "FACT-UNRELATED",
        "statement": "Office cafeteria serves 250 lunches per day.",
        "numeric_value": "250",
        "numeric_units": "lunches",
        "product_context": "Cafeteria catering",
        "applicable_conditions": "Weekdays",
        "verification_status": "Verified",
    }]
    for rule in (tone02, {"id": "RULE-Q", "title": "Notices", "pillar": "Messaging",
                          "description": "Send timely notices with adequate explanation."}):
        c = generate_candidate_rewrite(rule=rule, verified_facts=unrelated)
        assert c["cited_fact_id"] is None
        assert "250" not in extract_numeric_tokens(c["new_text"])
        assert c["ambiguity_after"] > 0


def test_f5_approve_revision_409_when_rule_changed_and_atomic_status_transition(monkeypatch):
    ava = _token("usr_ava")
    auth = {"Authorization": f"Bearer {ava}"}

    # 1. Stale proposal: rule edited after the proposal -> 409, edited wording kept.
    prop = client.post("/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose", headers=auth, json={}).json()
    vault = client.get("/api/vault/novapay").json()
    rule = next(r for r in vault["rules"] if r["id"] == "RULE-TONE-02")
    edited = "Limit each paragraph to at most 2 API endpoint names and define each on first use."
    put = client.put(
        "/api/vault/novapay/rules/RULE-TONE-02",
        headers=auth,
        json={
            "pillar": rule["pillar"],
            "title": rule["title"],
            "description": edited,
            "severity": rule.get("severity") or "medium",
            "do_example": rule.get("do_example") or "",
            "dont_example": rule.get("dont_example") or "",
            "pattern_regex": "",
        },
    )
    assert put.status_code == 200
    ver_before = client.get("/api/vault/novapay").json()["brand"]["version"]
    stale = client.post(f"/api/ambiguity-radar/novapay/revisions/{prop['id']}/approve", headers=auth)
    assert stale.status_code == 409
    after = client.get("/api/vault/novapay").json()
    assert next(r for r in after["rules"] if r["id"] == "RULE-TONE-02")["description"] == edited
    assert after["brand"]["version"] == ver_before

    # 2. Atomic transition: simulate a concurrent approver that already moved the revision out of
    #    'proposed' after our read. The conditional UPDATE must hit 0 rows -> 409, nothing applied.
    prop2 = client.post("/api/ambiguity-radar/novapay/rules/RULE-TONE-03/propose", headers=auth, json={}).json()
    conn = get_connection()
    conn.execute("UPDATE guideline_revisions SET status = 'approved' WHERE id = ?", (prop2["id"],))
    conn.commit()
    conn.close()
    real_hydrate = main_mod._hydrate_revision_row

    def stale_read(row):
        out = real_hydrate(row)
        if out.get("id") == prop2["id"]:
            out["status"] = "proposed"
        return out

    monkeypatch.setattr(main_mod, "_hydrate_revision_row", stale_read)
    v_before = client.get("/api/vault/novapay").json()
    rule3_before = next(r for r in v_before["rules"] if r["id"] == "RULE-TONE-03")
    race = client.post(f"/api/ambiguity-radar/novapay/revisions/{prop2['id']}/approve", headers=auth)
    assert race.status_code == 409
    assert "no longer 'proposed'" in race.json()["detail"]
    v_after = client.get("/api/vault/novapay").json()
    assert v_after["brand"]["version"] == v_before["brand"]["version"]
    assert next(r for r in v_after["rules"] if r["id"] == "RULE-TONE-03")["description"] == rule3_before["description"]

    # Reject uses the same conditional UPDATE.
    race_rej = client.post(f"/api/ambiguity-radar/novapay/revisions/{prop2['id']}/reject", headers=auth, json={})
    assert race_rej.status_code == 409
    monkeypatch.setattr(main_mod, "_hydrate_revision_row", real_hydrate)

    # 3. A normal proposal still approves exactly once; the second approval is 409.
    prop3 = client.post("/api/ambiguity-radar/novapay/rules/RULE-MSG-02/propose", headers=auth, json={}).json()
    assert client.post(f"/api/ambiguity-radar/novapay/revisions/{prop3['id']}/approve", headers=auth).status_code == 200
    assert client.post(f"/api/ambiguity-radar/novapay/revisions/{prop3['id']}/approve", headers=auth).status_code == 409


def test_f6_demo_mode_seeds_at_least_6_sample_audits_and_3_extra_vague_rules_with_high_medium_priorities(monkeypatch):
    audits = client.get("/api/audits?brand_id=novapay").json()["audits"]
    sample = [a for a in audits if "sample data" in a["document_name"].lower()]
    assert len(sample) >= 6

    rule_ids = {r["id"] for r in client.get("/api/vault/novapay").json()["rules"]}
    assert {"RULE-TONE-03", "RULE-MSG-02", "RULE-CLAIM-02"}.issubset(rule_ids)

    radar = client.get("/api/ambiguity-radar/novapay").json()
    assert radar["sufficient_sample"] is True
    by_id = {r["rule_id"]: r for r in radar["rules_analysis"]}
    priorities = {r["priority"] for r in radar["rules_analysis"]}
    assert {"High", "Medium"}.issubset(priorities)
    high_vague = [r for r in radar["rules_analysis"] if r["priority"] == "High" and r["is_vague"]]
    assert high_vague and all(r["override_rate"] > 20 for r in high_vague)
    # Exactly-20% stays out of High (the rule is "> 20%", not ">= 20%").
    assert by_id["RULE-MSG-02"]["override_rate"] == 20.0
    assert by_id["RULE-MSG-02"]["priority"] == "Medium"

    # Idempotent: repeated init_db() does not duplicate sample rows.
    conn = get_connection()
    counts_before = (
        conn.execute("SELECT COUNT(*) FROM audits").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM guideline_feedback").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
    )
    conn.close()
    init_db()
    init_db()
    conn = get_connection()
    counts_after = (
        conn.execute("SELECT COUNT(*) FROM audits").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM guideline_feedback").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
    )
    conn.close()
    assert counts_after == counts_before

    # Production mode: sample audits are not re-seeded and never counted in the overview.
    monkeypatch.setenv("LOOMSHIELD_WORKSPACE_MODE", "production")
    conn = get_connection()
    conn.execute("DELETE FROM guideline_feedback WHERE audit_id IN ('AUD-1003','AUD-1004','AUD-1005','AUD-1006')")
    conn.execute("DELETE FROM findings WHERE audit_id IN ('AUD-1003','AUD-1004','AUD-1005','AUD-1006')")
    conn.execute("DELETE FROM audits WHERE id IN ('AUD-1003','AUD-1004','AUD-1005','AUD-1006')")
    conn.commit()
    conn.close()
    init_db()
    conn = get_connection()
    assert conn.execute(
        "SELECT COUNT(*) FROM audits WHERE id IN ('AUD-1003','AUD-1004','AUD-1005','AUD-1006')"
    ).fetchone()[0] == 0
    conn.close()

def test_f9_every_emitted_finding_detection_method_starts_with_tier_prefix():
    # 1. Check all findings currently seeded in the database
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, detection_method FROM findings")
    db_findings = cur.fetchall()
    conn.close()
    assert len(db_findings) > 0
    for fid, dm in db_findings:
        dm_str = str(dm or "").strip()
        assert dm_str.startswith("Tier 1:") or dm_str.startswith("Tier 2:") or dm_str.startswith("Tier 1 + Tier 2:"), (
            f"Database finding {fid} detection_method '{dm}' does not start with Tier prefix"
        )

    # 2. Check dynamically generated findings from run_six_pillar_audit
    from backend.engine import run_six_pillar_audit
    vault = get_brand_vault_bundle("novapay")
    sample_text = (
        "NovaPay AI Engine provides 95% faster settlement with zero human oversight. "
        "Use an appropriate amount of technical detail."
    )
    res = run_six_pillar_audit(
        content=sample_text,
        brand=vault["brand"],
        rules=vault["rules"],
        terminology_rows=vault["terminology"],
        facts=vault["verified_facts"],
        brand_colors=vault["colors"],
        fg_color="#000000",
        bg_color="#FFFFFF",
    )
    findings = res.get("findings", [])
    assert len(findings) >= 3
    for f in findings:
        dm = str(f.get("detection_method") or "").strip()
        assert dm.startswith("Tier 1:") or dm.startswith("Tier 2:") or dm.startswith("Tier 1 + Tier 2:"), (
            f"Emitted finding {f.get('id')} detection_method '{dm}' does not start with Tier prefix"
        )


def test_f10_readme_traceability_backticked_test_names_exist_in_pytest_collection():
    import subprocess
    from pathlib import Path
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    assert readme_path.exists(), "README.md not found"
    readme_text = readme_path.read_text(encoding="utf-8")

    backticked_tests = set(re.findall(r"`(test_[a-zA-Z0-9_]+)`", readme_text))
    assert len(backticked_tests) >= 30, f"Expected at least 30 test names in README, found {len(backticked_tests)}"

    proc = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"pytest --collect-only failed: {proc.stderr}"
    collected_tests = set()
    for line in proc.stdout.splitlines():
        if "::" in line:
            name = line.split("::")[-1].split("[")[0].strip()
            collected_tests.add(name)

    missing = backticked_tests - collected_tests
    assert not missing, f"README references tests not found in pytest collection: {missing}"
