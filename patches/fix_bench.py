from pathlib import Path

p = Path(r"D:\LoomShield\tests\generate_test_cycles_report.py")
text = p.read_text(encoding="utf-8")

old_imp = "from backend.main import app, get_brand_vault_bundle"
new_imp = "from backend.main import app, audit_rate_limiter, get_brand_vault_bundle"

assert old_imp in text
text = text.replace(old_imp, new_imp, 1)

old_loop = "        for i in range(15):"
new_loop = """        for i in range(15):
            audit_rate_limiter.clear()"""

assert old_loop in text
text = text.replace(old_loop, new_loop, 1)

p.write_text(text, encoding="utf-8")
print("Updated generate_test_cycles_report.py to clear rate limiter between benchmark runs")
