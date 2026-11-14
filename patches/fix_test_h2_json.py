with open("tests/test_heatmap_inspector.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "from backend.heatmap import inspect_visual_heatmap"
replacement = "import json\n    import base64\n    from backend.heatmap import inspect_visual_heatmap"

assert target in text
text = text.replace(target, replacement, 1)

with open("tests/test_heatmap_inspector.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Added imports to test_h2_heatmap_fixture_suite_against_expected_json")
