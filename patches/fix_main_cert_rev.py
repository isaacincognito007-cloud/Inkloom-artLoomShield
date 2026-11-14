with open("backend/main.py", "r", encoding="utf-8") as f:
    code = f.read()

target = '''        cur.execute("SELECT * FROM certificates WHERE id = ?", (certificate_id,))
        c_row = cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail=f"Certificate '{certificate_id}' not found.")

        cur.execute(
            """
            INSERT OR REPLACE INTO certificate_revocations
            (certificate_id, audit_id, brand_id, revoked_by, revoked_by_user_id, revocation_reason, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                certificate_id,
                c_row["audit_id"],
                c_row["brand_id"],
                actor["user_name"],
                actor.get("user_id") or "",
                reason_str,
                now,
            ),
        )'''

replacement = '''        cur.execute("SELECT * FROM certificates WHERE id = ?", (certificate_id,))
        c_row = cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail=f"Certificate '{certificate_id}' not found.")

        try:
            c_payload = json.loads(c_row["payload_json"])
            b_id = str(c_payload.get("brand_id") or "")
        except Exception:
            b_id = ""

        cur.execute(
            """
            INSERT OR REPLACE INTO certificate_revocations
            (certificate_id, audit_id, brand_id, revoked_by, revoked_by_user_id, revocation_reason, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                certificate_id,
                c_row["audit_id"],
                b_id,
                actor["user_name"],
                actor.get("user_id") or "",
                reason_str,
                now,
            ),
        )'''

assert target in code, "target not found in main.py"
code = code.replace(target, replacement)

# Also in get_certificate_revocation_status:
target_status = 'cur.execute("SELECT id, audit_id, brand_id, created_at FROM certificates WHERE id = ?", (certificate_id,))'
replacement_status = 'cur.execute("SELECT id, audit_id, issued_at FROM certificates WHERE id = ?", (certificate_id,))'

assert target_status in code, "target_status not found in main.py"
code = code.replace(target_status, replacement_status)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Fixed brand_id in backend/main.py certificate revocation endpoints")
