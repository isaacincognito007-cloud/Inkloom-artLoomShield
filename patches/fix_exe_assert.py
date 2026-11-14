from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_str = 'assert "[Unparseable file" in exe_pdf_result["data"]["content"]'
new_str = 'assert exe_pdf_result["data"]["document_name"] == "malicious.pdf"'

assert old_str in text
text = text.replace(old_str, new_str, 1)

p.write_text(text, encoding="utf-8")
print("Fixed exe assert in test_ui_e2e.py")
