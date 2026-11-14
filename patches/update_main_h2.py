with open("backend/main.py", "r", encoding="utf-8") as f:
    code = f.read()

# Add ClearSpaceUpdate model
model_target = "class VisualSpecsUpdate(BaseModel):"
model_replacement = '''class ClearSpaceUpdate(BaseModel):
    min_clear_space_ratio: float = Field(0.25, ge=0.0, le=5.0)
    min_clear_space_px: Optional[int] = Field(16, ge=0, le=500)


class VisualSpecsUpdate(BaseModel):
    typography_specs: str
    spacing_rules: str
    logo_placement_constraints: str
    min_clear_space_ratio: Optional[float] = None
    min_clear_space_px: Optional[int] = None'''

assert model_target in code, "model_target not found in main.py"
# replace only the first occurrence (definition of VisualSpecsUpdate)
code = code.replace(
    '''class VisualSpecsUpdate(BaseModel):
    typography_specs: str
    spacing_rules: str
    logo_placement_constraints: str''',
    model_replacement,
    1
)

# In update_visual_specs, update min_clear_space_ratio and min_clear_space_px if provided
vis_target = '''        cur.execute(
            """
            UPDATE brands
            SET typography_specs = ?, spacing_rules = ?, logo_placement_constraints = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.typography_specs.strip(),
                req.spacing_rules.strip(),
                req.logo_placement_constraints.strip(),
                now,
                brand_id,
            ),
        )'''

vis_replacement = '''        ratio_val = float(req.min_clear_space_ratio) if req.min_clear_space_ratio is not None else None
        px_val = int(req.min_clear_space_px) if req.min_clear_space_px is not None else None
        if ratio_val is not None and px_val is not None:
            cur.execute(
                """
                UPDATE brands
                SET typography_specs = ?, spacing_rules = ?, logo_placement_constraints = ?,
                    min_clear_space_ratio = ?, min_clear_space_px = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    req.typography_specs.strip(),
                    req.spacing_rules.strip(),
                    req.logo_placement_constraints.strip(),
                    ratio_val,
                    px_val,
                    now,
                    brand_id,
                ),
            )
        elif ratio_val is not None:
            cur.execute(
                """
                UPDATE brands
                SET typography_specs = ?, spacing_rules = ?, logo_placement_constraints = ?,
                    min_clear_space_ratio = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    req.typography_specs.strip(),
                    req.spacing_rules.strip(),
                    req.logo_placement_constraints.strip(),
                    ratio_val,
                    now,
                    brand_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE brands
                SET typography_specs = ?, spacing_rules = ?, logo_placement_constraints = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    req.typography_specs.strip(),
                    req.spacing_rules.strip(),
                    req.logo_placement_constraints.strip(),
                    now,
                    brand_id,
                ),
            )'''

assert vis_target in code, "vis_target not found in main.py"
code = code.replace(vis_target, vis_replacement)

# Add logo upload, delete, and clear-space endpoints right after delete_brand_color
logo_endpoints = '''

@app.post("/api/vault/{brand_id}/logo")
async def upload_approved_brand_logo(
    brand_id: str,
    file: UploadFile = File(...),
    actor: Dict[str, str] = Depends(current_actor),
):
    """H2(a): A Brand Administrator can upload one approved logo (PNG or SVG, max 300 KB)."""
    require_permission(actor["role"], "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    
    # Read upload stream in chunks with strict 300 KB limit
    raw_bytes = await _read_upload_in_chunks(file, max_bytes=300 * 1024)
    
    fname = os.path.basename(file.filename or "logo").replace("..", "")
    ext = os.path.splitext(fname.lower())[1]

    fmt = ""
    if ext == ".svg" or (len(raw_bytes) > 4 and b"<svg" in raw_bytes[:1024].lower()):
        fmt = "image/svg+xml"
    elif ext == ".png" or raw_bytes.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        fmt = "image/png"
    else:
        raise HTTPException(status_code=400, detail="Only PNG and SVG logo files (max 300 KB) are accepted.")

    b64_str = f"data:{fmt};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
    now = datetime.now(timezone.utc).isoformat()

    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET approved_logo_b64 = ?, approved_logo_format = ?, approved_logo_filename = ?,
                approved_logo_updated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (b64_str, fmt, fname, now, now, brand_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")

    return {"status": "updated", "vault": get_brand_vault_bundle(brand_id)}


@app.delete("/api/vault/{brand_id}/logo")
def delete_approved_brand_logo(
    brand_id: str,
    actor: Dict[str, str] = Depends(current_actor),
):
    """H2(a): Remove the approved brand logo asset."""
    require_permission(actor["role"], "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()

    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET approved_logo_b64 = '', approved_logo_format = '', approved_logo_filename = '',
                approved_logo_updated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, brand_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")

    return {"status": "deleted", "vault": get_brand_vault_bundle(brand_id)}


@app.put("/api/vault/{brand_id}/clear-space")
def update_clear_space_settings(
    brand_id: str,
    req: ClearSpaceUpdate,
    actor: Dict[str, str] = Depends(current_actor),
):
    """H2(c): Clear space as a multiple of logo height, editable in Vault UI (keep px as optional)."""
    require_permission(actor["role"], "edit_brand_vault", "Only a Brand Administrator can change Brand Vault guidelines")
    now = datetime.now(timezone.utc).isoformat()
    ratio_val = float(req.min_clear_space_ratio)
    px_val = int(req.min_clear_space_px) if req.min_clear_space_px is not None else 16

    with db_session() as conn:
        cur = conn.cursor()
        bump_brand_version(cur, brand_id)
        cur.execute(
            """
            UPDATE brands
            SET min_clear_space_ratio = ?, min_clear_space_px = ?, updated_at = ?
            WHERE id = ?
            """,
            (ratio_val, px_val, now, brand_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")

    return {"status": "updated", "vault": get_brand_vault_bundle(brand_id)}
'''

del_color_target = '    return {"status": "deleted", "color_id": color_id}'
assert del_color_target in code, "del_color_target not found in main.py"
code = code.replace(del_color_target, del_color_target + logo_endpoints, 1)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated backend/main.py with logo and clear space endpoints successfully")
