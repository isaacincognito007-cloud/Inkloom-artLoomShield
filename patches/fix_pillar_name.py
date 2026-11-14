from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_str = 'assert corrupt_png_result["data"]["pillar_states"]["Brand Identity & Palette"] == "Check Failed"'
new_str = 'assert corrupt_png_result["data"]["pillar_states"]["Visual and Logo Consistency"] == "Check Failed"'

assert old_str in text
text = text.replace(old_str, new_str, 1)

old_str2 = 'assert corrupt_png_result["data"]["pillar_states"]["Brand Identity & Palette"] != "Passed"'
new_str2 = 'assert corrupt_png_result["data"]["pillar_states"]["Visual and Logo Consistency"] != "Passed"'

assert old_str2 in text
text = text.replace(old_str2, new_str2, 1)

p.write_text(text, encoding="utf-8")
print("Updated pillar name to Visual and Logo Consistency in test_ui_e2e.py")
