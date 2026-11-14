from pathlib import Path

p = Path(r"D:\LoomShield\tests\generate_test_cycles_report.py")
text = p.read_text(encoding="utf-8")

text = text.replace("audit_rate_limiter.clear()", "audit_rate_limiter.reset()")
p.write_text(text, encoding="utf-8")
print("Updated clear() to reset() in generate_test_cycles_report.py")
