with open("backend/main.py", "r", encoding="utf-8") as f:
    code = f.read()

target = '''def _compute_rule_loop_closure(
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
    }'''

replacement = '''def _compute_rule_loop_closure(
    cur,
    brand_id: str,
    rule_id: str,
    latest_approved: Optional[Dict[str, Any]],
    min_sample: int = 5,
) -> Optional[Dict[str, Any]]:
    """H1 / B5: Loop closure computed side by side BEFORE (<= decided_at) and AFTER (> decided_at) revision approval."""
    if not latest_approved:
        return None
    decided_at = str(latest_approved.get("decided_at") or "").strip()
    if not decided_at:
        return None
    rev_date = decided_at[:10]

    # Audits before or on approval
    cur.execute(
        "SELECT id FROM audits WHERE brand_id = ? AND created_at <= ? ORDER BY created_at ASC",
        (brand_id, decided_at),
    )
    before_audits = [str(r["id"]) for r in cur.fetchall()]
    before_audits_cnt = len(before_audits)

    if before_audits_cnt > 0:
        placeholders_b = ",".join("?" for _ in before_audits)
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM findings WHERE audit_id IN ({placeholders_b}) AND rule_or_fact_id LIKE ?",
            (*before_audits, f"%{rule_id}%"),
        )
        before_v = int(cur.fetchone()["cnt"] or 0)

        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM guideline_feedback WHERE brand_id = ? AND rule_id = ? AND audit_id IN ({placeholders_b}) AND created_at <= ?",
            (brand_id, rule_id, *before_audits, decided_at),
        )
        before_o = int(cur.fetchone()["cnt"] or 0)

        cur.execute(
            f"""SELECT COUNT(DISTINCT id) AS cnt FROM findings
               WHERE audit_id IN ({placeholders_b})
                 AND rule_or_fact_id LIKE ?
                 AND (review_state = 'dismissed' OR id IN (
                     SELECT finding_id FROM review_decisions WHERE audit_id IN ({placeholders_b}) AND decision IN ('dismiss', 'dismissed')
                 ))""",
            (*before_audits, f"%{rule_id}%", *before_audits),
        )
        before_d = int(cur.fetchone()["cnt"] or 0)

        if before_v == 0 and before_o == 0:
            before_rate = 0.0
        else:
            denom_b = max(before_v, before_o, 1)
            before_rate = round((float(before_o) / float(denom_b)) * 100.0, 1)
    else:
        before_v = 0
        before_o = 0
        before_d = 0
        before_rate = None

    # Audits strictly after approval
    cur.execute(
        "SELECT id FROM audits WHERE brand_id = ? AND created_at > ? ORDER BY created_at ASC",
        (brand_id, decided_at),
    )
    post_audits = [str(r["id"]) for r in cur.fetchall()]
    post_audits_cnt = len(post_audits)

    if post_audits_cnt > 0:
        placeholders_p = ",".join("?" for _ in post_audits)
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM findings WHERE audit_id IN ({placeholders_p}) AND rule_or_fact_id LIKE ?",
            (*post_audits, f"%{rule_id}%"),
        )
        post_v = int(cur.fetchone()["cnt"] or 0)

        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM guideline_feedback WHERE brand_id = ? AND rule_id = ? AND audit_id IN ({placeholders_p}) AND created_at > ?",
            (brand_id, rule_id, *post_audits, decided_at),
        )
        post_o = int(cur.fetchone()["cnt"] or 0)

        cur.execute(
            f"""SELECT COUNT(DISTINCT id) AS cnt FROM findings
               WHERE audit_id IN ({placeholders_p})
                 AND rule_or_fact_id LIKE ?
                 AND (review_state = 'dismissed' OR id IN (
                     SELECT finding_id FROM review_decisions WHERE audit_id IN ({placeholders_p}) AND decision IN ('dismiss', 'dismissed')
                 ))""",
            (*post_audits, f"%{rule_id}%", *post_audits),
        )
        post_d = int(cur.fetchone()["cnt"] or 0)

        if post_v == 0 and post_o == 0:
            post_rate = 0.0
            disp = f"Revised {rev_date}; override rate since revision: 0.0% across {post_audits_cnt} audit(s)"
        else:
            denom_p = max(post_v, post_o, 1)
            post_rate = round((float(post_o) / float(denom_p)) * 100.0, 1)
            disp = f"Revised {rev_date}; override rate since revision: {post_rate}% ({post_o}/{denom_p} findings across {post_audits_cnt} audit(s))"
    else:
        post_v = 0
        post_o = 0
        post_d = 0
        post_rate = None
        disp = f"Revised {rev_date}; override rate since revision: — (no audits since revision)"

    has_sample = post_audits_cnt >= min_sample
    caveat = (
        f"Preliminary metrics ({post_audits_cnt}/{min_sample} audits observed since revision; minimum sample threshold is {min_sample})."
        if not has_sample
        else f"Sufficient sample observed ({post_audits_cnt} audits since revision, exceeding minimum threshold of {min_sample})."
    )

    return {
        "revision_id": latest_approved["id"],
        "revised_at": decided_at,
        "revised_date": rev_date,
        "before": {
            "audits_counted": before_audits_cnt,
            "violations": before_v,
            "overrides": before_o,
            "dismissals": before_d,
            "override_rate": before_rate,
            "override_rate_display": f"{before_rate:.1f}%" if before_rate is not None else "—",
        },
        "after": {
            "audits_counted": post_audits_cnt,
            "violations": post_v,
            "overrides": post_o,
            "dismissals": post_d,
            "override_rate": post_rate,
            "override_rate_display": f"{post_rate:.1f}%" if post_rate is not None else "—",
        },
        "has_sufficient_sample": has_sample,
        "minimum_sample_caveat": caveat,
        "scoring_factors_disclosure": "Score evaluates vagueness indicators, missing measurable criteria, override and dismissal rates, and accepted corrections.",
        "post_revision_audits_count": post_audits_cnt,
        "post_revision_violations": post_v,
        "post_revision_overrides": post_o,
        "override_rate_since_revision": post_rate,
        "display": disp,
    }'''

assert target in code, "target not found in main.py"
code = code.replace(target, replacement)

call_target = 'loop_closure = _compute_rule_loop_closure(cur, brand_id, r["id"], latest_approved)'
call_replacement = 'loop_closure = _compute_rule_loop_closure(cur, brand_id, r["id"], latest_approved, min_sample=effective_min_sample)'

assert call_target in code, "call_target not found in main.py"
code = code.replace(call_target, call_replacement)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated backend/main.py loop closure successfully")
