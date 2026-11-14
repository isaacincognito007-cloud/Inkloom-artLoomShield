with open("tests/test_heatmap_inspector.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add Path import if not present
if "from pathlib import Path" not in text:
    text = "from pathlib import Path\n" + text

text = text.replace('headers={"X-Test-Role": "Content Creator"}', 'headers={"X-Loomshield-Role": "Content Creator"}')
text = text.replace('headers={"X-Test-Role": "Brand Administrator"}', 'headers={"X-Loomshield-Role": "Brand Administrator"}')

with open("tests/test_heatmap_inspector.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed test_heatmap_inspector.py")
