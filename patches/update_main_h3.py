with open("backend/main.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update verify_certificate_endpoint to check revocation
old_verify_logic = '''        if isinstance(audit_id, str) and audit_id.strip():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT current_content, overall_status FROM audits WHERE id = ?", (audit_id.strip(),))
            a_row = cur.fetchone()
            conn.close()'''

new_verify_logic = '''        cert_id = payload.get("certificate_id") if isinstance(payload, dict) else None
        conn = get_connection()
        cur = conn.cursor()
        
        # Check revocation in database
        rev_row = None
        if isinstance(cert_id, str) and cert_id.strip():
            cur.execute("SELECT * FROM certificate_revocations WHERE certificate_id = ?", (cert_id.strip(),))
            rev_row = cur.fetchone()
            if rev_row:
                result["is_revoked"] = True
                result["status"] = "revoked"
                result["revoked_at"] = rev_row["revoked_at"]
                result["revocation_reason"] = rev_row["revocation_reason"]
                result["revoked_by"] = rev_row["revoked_by"]
                result["reasons"].append(
                    f"This certificate was revoked by {rev_row['revoked_by']} on {rev_row['revoked_at'][:10]}: {rev_row['revocation_reason']}"
                )

        if isinstance(audit_id, str) and audit_id.strip():
            cur.execute("SELECT current_content, overall_status FROM audits WHERE id = ?", (audit_id.strip(),))
            a_row = cur.fetchone()
            conn.close()'''

assert old_verify_logic in code, "old_verify_logic not found in main.py"
code = code.replace(old_verify_logic, new_verify_logic)

# Add RevokeCertificateRequest and endpoints after verify_certificate_endpoint
new_cert_endpoints = '''


class RevokeCertificateRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@app.post("/api/certificates/{certificate_id}/revoke")
def revoke_certificate(
    certificate_id: str,
    req: RevokeCertificateRequest,
    actor: Dict[str, str] = Depends(current_actor),
):
    """H3(b): A Brand Administrator can revoke a compliance certificate with a mandatory reason."""
    require_permission(actor["role"], "edit_brand_vault", "Only a Brand Administrator can revoke compliance certificates")
    reason_str = req.reason.strip()
    if not reason_str:
        raise HTTPException(status_code=400, detail="A non-empty revocation reason is required.")
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM certificates WHERE id = ?", (certificate_id,))
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
        )
        record_audit_event(
            cur,
            c_row["audit_id"],
            "certificate_revoked",
            actor["user_name"],
            actor["role"],
            f"Compliance certificate {certificate_id} was revoked: {reason_str}",
            {"certificate_id": certificate_id, "reason": reason_str},
            None,
            now,
            actor_user_id=actor.get("user_id") or "",
        )
    return {
        "status": "revoked",
        "certificate_id": certificate_id,
        "reason": reason_str,
        "revoked_at": now,
    }


@app.get("/api/certificates/{certificate_id}/status")
def get_certificate_revocation_status(certificate_id: str):
    """H3(b): Public status endpoint returning revocation status without any content hashes."""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, audit_id, brand_id, created_at FROM certificates WHERE id = ?", (certificate_id,))
        c_row = cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail=f"Certificate '{certificate_id}' not found.")

        cur.execute("SELECT * FROM certificate_revocations WHERE certificate_id = ?", (certificate_id,))
        r_row = cur.fetchone()

        if r_row:
            return {
                "certificate_id": certificate_id,
                "audit_id": c_row["audit_id"],
                "status": "revoked",
                "is_revoked": True,
                "revoked_at": r_row["revoked_at"],
                "revocation_reason": r_row["revocation_reason"],
                "revoked_by": r_row["revoked_by"],
            }
        return {
            "certificate_id": certificate_id,
            "audit_id": c_row["audit_id"],
            "status": "active",
            "is_revoked": False,
            "revoked_at": None,
            "revocation_reason": None,
            "revoked_by": None,
        }
'''

target_after = "    return result\n\n\n@app.post(\"/api/audits/{audit_id}/rerun\")"
assert target_after in code, "target_after not found in main.py"
code = code.replace(target_after, "    return result" + new_cert_endpoints + "\n\n@app.post(\"/api/audits/{audit_id}/rerun\")")

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated backend/main.py with certificate revocation endpoints successfully")
