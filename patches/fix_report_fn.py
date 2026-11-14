with open("scripts/generate_fixture_report.py", "r", encoding="utf-8") as f:
    text = f.read()

target = 'hm = inspect_visual_heatmap(raw_bytes, colors, brand=brand, grid_size=2)'
replacement = 'hm = inspect_visual_heatmap(raw_bytes, colors, brand=brand, filename=filename, grid_size=2)'

assert target in text
text = text.replace(target, replacement)

with open("scripts/generate_fixture_report.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed filename param in generate_fixture_report.py")
