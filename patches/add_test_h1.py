with open("tests/test_clarity_rewriter.py", "r", encoding="utf-8") as f:
    text = f.read()

new_test = '''

def test_h1_clarity_rewriter_before_after_loop_closure_metrics():
    """H1: For every approved revision, show side by side for that rule: BEFORE and AFTER metrics with caveat."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LOOMSHIELD_WORKSPACE_MODE", "demo")
        init_db()
        reset_demo_workspace()
        client = TestClient(app)

        # 1. Propose and approve revision for RULE-TONE-02
        prop_res = client.post(
            "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
            json={
                "new_text": "Write for the target reader's domain, defining protocols on first mention [SET THRESHOLD: max 30 words per overview].",
                "do_examples": ["Include SLA numbers."],
                "dont_examples": ["Avoid undefined acronyms."],
            },
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert prop_res.status_code == 200, prop_res.text
        rev_id = prop_res.json()["id"]

        appr_res = client.post(
            f"/api/ambiguity-radar/novapay/revisions/{rev_id}/approve",
            headers={"X-Test-Role": "Brand Administrator"},
        )
        assert appr_res.status_code == 200, appr_res.text

        # 2. Query radar endpoint and check loop closure side by side structure
        radar = client.get("/api/ambiguity-radar/novapay").json()
        r_tone = next(r for r in radar["rules_analysis"] if r["rule_id"] == "RULE-TONE-02")
        lc = r_tone.get("loop_closure")
        assert lc is not None, "loop_closure must be present for approved revision"
        assert lc["revision_id"] == rev_id

        # BEFORE metrics
        before = lc.get("before")
        assert before is not None, "before metrics must be present"
        assert "audits_counted" in before
        assert "violations" in before
        assert "overrides" in before
        assert "dismissals" in before
        assert "override_rate" in before
        assert "override_rate_display" in before
        assert before["audits_counted"] >= 2
        assert before["overrides"] >= 2

        # AFTER metrics
        after = lc.get("after")
        assert after is not None, "after metrics must be present"
        assert "audits_counted" in after
        assert "violations" in after
        assert "overrides" in after
        assert "dismissals" in after
        assert "override_rate" in after
        assert "override_rate_display" in after

        # Caveat and scoring disclosure
        assert "has_sufficient_sample" in lc
        assert "minimum_sample_caveat" in lc
        assert "Preliminary" in lc["minimum_sample_caveat"] or "Sufficient" in lc["minimum_sample_caveat"]
        assert "scoring_factors_disclosure" in lc
        assert "Score evaluates vagueness indicators" in lc["scoring_factors_disclosure"]
'''

assert "def test_h1_clarity_rewriter_before_after_loop_closure_metrics" not in text
text = text + new_test

with open("tests/test_clarity_rewriter.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Added test_h1_clarity_rewriter_before_after_loop_closure_metrics to tests/test_clarity_rewriter.py")
