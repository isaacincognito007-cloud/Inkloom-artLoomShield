import re

PATH = r"D:\LoomShield\backend\main.py"
src = open(PATH, encoding="utf-8").read()

VAULT_EDIT_MSG = "Only a Brand Administrator can change Brand Vault guidelines"

edits = {
    "def create_brand_profile(req: BrandCreateRequest):":
        ("def create_brand_profile(req: BrandCreateRequest, role: str = Depends(current_role)):",
         'require_permission(role, "manage_brands", "Only a Brand Administrator can create brand profiles")'),
    "def update_brand_voice(brand_id: str, req: BrandVoiceUpdate):":
        ("def update_brand_voice(brand_id: str, req: BrandVoiceUpdate, role: str = Depends(current_role)):", None),
    "def update_visual_specs(brand_id: str, req: VisualSpecsUpdate):":
        ("def update_visual_specs(brand_id: str, req: VisualSpecsUpdate, role: str = Depends(current_role)):", None),
    "def update_accessibility_specs(brand_id: str, req: AccessibilitySpecsUpdate):":
        ("def update_accessibility_specs(brand_id: str, req: AccessibilitySpecsUpdate, role: str = Depends(current_role)):", None),
    "def add_terminology_entry(brand_id: str, req: TerminologyCreate):":
        ("def add_terminology_entry(brand_id: str, req: TerminologyCreate, role: str = Depends(current_role)):", None),
    "def update_terminology_entry(brand_id: str, term_id: str, req: TerminologyCreate):":
        ("def update_terminology_entry(brand_id: str, term_id: str, req: TerminologyCreate, role: str = Depends(current_role)):", None),
    "def delete_terminology_entry(brand_id: str, term_id: str):":
        ("def delete_terminology_entry(brand_id: str, term_id: str, role: str = Depends(current_role)):", None),
    "def add_verified_fact(brand_id: str, req: VerifiedFactCreate):":
        ("def add_verified_fact(brand_id: str, req: VerifiedFactCreate, role: str = Depends(current_role)):",
         'require_permission(role, "propose_facts", "Your role cannot add fact records")\n'
         '    if req.verification_status == "Verified":\n'
         '        require_permission(role, "verify_facts", "Only a Brand Administrator can mark a fact as Verified")'),
    "def update_verified_fact(brand_id: str, fact_id: str, req: VerifiedFactCreate):":
        ("def update_verified_fact(brand_id: str, fact_id: str, req: VerifiedFactCreate, role: str = Depends(current_role)):", None),
    "def update_fact_verification_status(brand_id: str, fact_id: str, verification_status: str = Form(...)):":
        ("def update_fact_verification_status(brand_id: str, fact_id: str, verification_status: str = Form(...), role: str = Depends(current_role)):",
         'require_permission(role, "verify_facts", "Only a Brand Administrator can change fact verification status")'),
    "def delete_verified_fact(brand_id: str, fact_id: str):":
        ("def delete_verified_fact(brand_id: str, fact_id: str, role: str = Depends(current_role)):", None),
    "def add_brand_color(brand_id: str, req: BrandColorCreate):":
        ("def add_brand_color(brand_id: str, req: BrandColorCreate, role: str = Depends(current_role)):", None),
    "def update_brand_color(brand_id: str, color_id: str, req: BrandColorCreate):":
        ("def update_brand_color(brand_id: str, color_id: str, req: BrandColorCreate, role: str = Depends(current_role)):", None),
    "def delete_brand_color(brand_id: str, color_id: str):":
        ("def delete_brand_color(brand_id: str, color_id: str, role: str = Depends(current_role)):", None),
    "def add_brand_rule(brand_id: str, req: RuleCreate):":
        ("def add_brand_rule(brand_id: str, req: RuleCreate, role: str = Depends(current_role)):", None),
    "def update_brand_rule(brand_id: str, rule_id: str, req: RuleCreate):":
        ("def update_brand_rule(brand_id: str, rule_id: str, req: RuleCreate, role: str = Depends(current_role)):", None),
    "def delete_brand_rule(brand_id: str, rule_id: str):":
        ("def delete_brand_rule(brand_id: str, rule_id: str, role: str = Depends(current_role)):", None),
}

for old, (new, guard) in edits.items():
    assert src.count(old) == 1, old
    guard = guard or f'require_permission(role, "edit_brand_vault", "{VAULT_EDIT_MSG}")'
    src = src.replace(old, f"{new}\n    {guard}")

open(PATH, "w", encoding="utf-8").write(src)
print("patched", len(edits), "endpoints")
