with open("tests/test_heatmap_inspector.py", "r", encoding="utf-8") as f:
    text = f.read()

bad = """import json
    import base64
    from backend.heatmap import inspect_visual_heatmap"""

good = """import base64
import json
from backend.heatmap import inspect_visual_heatmap"""

assert bad in text
text = text.replace(bad, good)

with open("tests/test_heatmap_inspector.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed imports in test_heatmap_inspector.py")
