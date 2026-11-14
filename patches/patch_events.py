PATH = r"D:\LoomShield\backend\main.py"
src = open(PATH, encoding="utf-8").read().replace("\r\n", "\n")

target1 = """        next_ver = len(detail["revisions"]) + 1
        cur.execute(
            \"\"\"
            INSERT INTO revisions
            (audit_id, version_number, previous_content, revised_content, editor_role, change_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            \"\"\",
            (audit_id, next_ver, current_text, new_text, req.reviewer_role, change_desc, now),
        )"""

replacement1 = """        next_ver = len(detail["revisions"]) + 1
        cur.execute(
            \"\"\"
            INSERT INTO revisions
            (audit_id, version_number, previous_content, revised_content, editor_role, change_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            \"\"\",
            (audit_id, next_ver, current_text, new_text, req.reviewer_role, change_desc, now),
        )
        record_audit_event(
            cur,
            audit_id,
            "correction_applied",
            configured_user_name(),
            req.reviewer_role,
            change_desc,
            {
                "finding_id": finding_id,
                "rule_or_fact_id": target["rule_or_fact_id"],
                "decision": req.decision,
                "from": target["flagged_text"],
                "to": replacement_used,
            },
            next_ver,
            now,
        )"""

assert target1 in src, "target1 not found"
src = src.replace(target1, replacement1, 1)

target2 = """        cur.execute(
            \"\"\"
            INSERT INTO guideline_feedback
            (brand_id, rule_id, audit_id, finding_id, override_reason, suspected_cause, admin_review_state, created_at)
            VALUES (?, ?, ?, ?, ?, 'Logged via creator/reviewer dismissal', 'Open', ?)
            \"\"\",
            (detail["brand_id"], primary_rule_id, audit_id, finding_id, reason_str, now),
        )"""

replacement2 = """        cur.execute(
            \"\"\"
            INSERT INTO guideline_feedback
            (brand_id, rule_id, audit_id, finding_id, override_reason, suspected_cause, admin_review_state, created_at)
            VALUES (?, ?, ?, ?, ?, 'Logged via creator/reviewer dismissal', 'Open', ?)
            \"\"\",
            (detail["brand_id"], primary_rule_id, audit_id, finding_id, reason_str, now),
        )
        record_audit_event(
            cur,
            audit_id,
            "finding_dismissed",
            configured_user_name(),
            req.reviewer_role,
            f'Dismissed {finding_id} ({target["rule_or_fact_id"]}): "{reason_str}"',
            {
                "finding_id": finding_id,
                "rule_or_fact_id": target["rule_or_fact_id"],
                "reason": reason_str,
            },
            len(detail["revisions"]),
            now,
        )"""

assert target2 in src, "target2 not found"
src = src.replace(target2, replacement2, 1)

target3 = """        (
            audit_id,
            detail["overall_status"],
            req.new_state,
            req.approver_role,
            latest_version,
            unresolved_count,
            1 if req.override_acknowledged else 0,
            req.comment.strip() or f"State changed to {req.new_state}.",
            content_hash,
            now,
        ),
    )
    conn.commit()"""

replacement3 = """        (
            audit_id,
            detail["overall_status"],
            req.new_state,
            req.approver_role,
            latest_version,
            unresolved_count,
            1 if req.override_acknowledged else 0,
            req.comment.strip() or f"State changed to {req.new_state}.",
            content_hash,
            now,
        ),
    )
    event_type = "approved" if req.new_state == "Approved" else "status_changed"
    event_summary = (
        f"Approved for publication with {unresolved_count} unresolved finding(s)"
        + (" (authorised override recorded)." if req.override_acknowledged else ".")
        if req.new_state == "Approved"
        else f"Status changed: {detail['overall_status']} → {req.new_state}."
    )
    if req.comment.strip():
        event_summary += f' "{req.comment.strip()}"'
    record_audit_event(
        cur,
        audit_id,
        event_type,
        configured_user_name(),
        req.approver_role,
        event_summary,
        {
            "from": detail["overall_status"],
            "to": req.new_state,
            "unresolved_findings": unresolved_count,
            "override": bool(req.override_acknowledged),
            "comment": req.comment.strip(),
        },
        latest_version,
        now,
    )
    conn.commit()"""

assert target3 in src, "target3 not found"
src = src.replace(target3, replacement3, 1)

with open(PATH, "wb") as f:
    f.write(src.encode("utf-8"))
print("Added audit_events logging to decisions and workflow transitions (written as LF).")
