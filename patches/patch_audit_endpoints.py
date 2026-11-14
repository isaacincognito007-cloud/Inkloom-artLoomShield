import re

PATH = r"D:\LoomShield\backend\main.py"
src = open(PATH, encoding="utf-8").read()

# 1. Update create_and_run_audit to pass actor_role=role
old_call = """    audit_id = persist_audit_record(
        brand_id=req.brand_id,
        document_name=req.document_name,
        input_format=req.input_format,
        content=req.content,
        fg_color=req.fg_color,
        bg_color=req.bg_color,
        image_alt_text=req.image_alt_text,
        has_visual_asset=req.has_visual_asset,
        visual_metadata=timing_meta,
        confidential_mode=req.confidential_mode,
        audit_output=audit_output,
    )"""

new_call = """    audit_id = persist_audit_record(
        brand_id=req.brand_id,
        document_name=req.document_name,
        input_format=req.input_format,
        content=req.content,
        fg_color=req.fg_color,
        bg_color=req.bg_color,
        image_alt_text=req.image_alt_text,
        has_visual_asset=req.has_visual_asset,
        visual_metadata=timing_meta,
        confidential_mode=req.confidential_mode,
        audit_output=audit_output,
        actor_role=role,
    )"""

assert old_call in src, "old_call not found in main.py"
src = src.replace(old_call, new_call, 1)

# 2. Update create_audit_from_upload signature and calls
old_upload_sig = """@app.post("/api/audits/upload")
async def create_audit_from_upload(
    brand_id: str = Form("novapay"),
    document_name: str = Form(""),
    fg_color: str = Form(""),
    bg_color: str = Form(""),
    image_alt_text: str = Form(""),
    confidential_mode: bool = Form(True),
    file: UploadFile = File(...),
):"""

new_upload_sig = """@app.post("/api/audits/upload")
async def create_audit_from_upload(
    brand_id: str = Form("novapay"),
    document_name: str = Form(""),
    fg_color: str = Form(""),
    bg_color: str = Form(""),
    image_alt_text: str = Form(""),
    confidential_mode: bool = Form(True),
    file: UploadFile = File(...),
    role: str = Depends(current_role),
):"""

assert old_upload_sig in src, "old_upload_sig not found"
src = src.replace(old_upload_sig, new_upload_sig, 1)

old_vis_persist = """        audit_id = persist_audit_record(
            brand_id=brand_id,
            document_name=safe_doc_name,
            input_format=ext.lstrip("."),
            content=f"[Visual Asset Audit: {fname}]",
            fg_color=fg_color,
            bg_color=bg_color,
            image_alt_text=image_alt_text,
            has_visual_asset=True,
            visual_metadata=vis_info,
            confidential_mode=confidential_mode,
            audit_output=audit_output,
        )"""

new_vis_persist = """        audit_id = persist_audit_record(
            brand_id=brand_id,
            document_name=safe_doc_name,
            input_format=ext.lstrip("."),
            content=f"[Visual Asset Audit: {fname}]",
            fg_color=fg_color,
            bg_color=bg_color,
            image_alt_text=image_alt_text,
            has_visual_asset=True,
            visual_metadata=vis_info,
            confidential_mode=confidential_mode,
            audit_output=audit_output,
            actor_role=role,
        )"""

assert old_vis_persist in src, "old_vis_persist not found"
src = src.replace(old_vis_persist, new_vis_persist, 1)

old_doc_persist = """    audit_id = persist_audit_record(
        brand_id=brand_id,
        document_name=safe_doc_name,
        input_format=parsed["input_format"],
        content=parsed["extracted_text"] or f"[Unparseable file: {fname}]",
        fg_color=fg_color,
        bg_color=bg_color,
        image_alt_text=image_alt_text,
        has_visual_asset=(parsed["input_format"] == "svg"),
        visual_metadata={},
        confidential_mode=confidential_mode,
        audit_output=audit_output,
    )"""

new_doc_persist = """    audit_id = persist_audit_record(
        brand_id=brand_id,
        document_name=safe_doc_name,
        input_format=parsed["input_format"],
        content=parsed["extracted_text"] or f"[Unparseable file: {fname}]",
        fg_color=fg_color,
        bg_color=bg_color,
        image_alt_text=image_alt_text,
        has_visual_asset=(parsed["input_format"] == "svg"),
        visual_metadata={},
        confidential_mode=confidential_mode,
        audit_output=audit_output,
        actor_role=role,
    )"""

assert old_doc_persist in src, "old_doc_persist not found"
src = src.replace(old_doc_persist, new_doc_persist, 1)

# 3. In get_audit_detail, load audit_events
old_approvals_load = """    cur.execute("SELECT * FROM approvals WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    approvals = [dict(ap) for ap in cur.fetchall()]

    conn.close()"""

new_approvals_load = """    cur.execute("SELECT * FROM approvals WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    approvals = [dict(ap) for ap in cur.fetchall()]

    cur.execute("SELECT * FROM audit_events WHERE audit_id = ? ORDER BY id ASC", (audit_id,))
    events = []
    for ev in cur.fetchall():
        evd = dict(ev)
        try:
            evd["detail"] = json.loads(evd.pop("detail_json") or "{}")
        except Exception:
            evd["detail"] = {}
        events.append(evd)

    conn.close()"""

assert old_approvals_load in src, "old_approvals_load not found"
src = src.replace(old_approvals_load, new_approvals_load, 1)

open(PATH, "w", encoding="utf-8").write(src)
print("Updated audit creation and detail endpoints successfully.")
