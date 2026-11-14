with open("backend/heatmap.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''            "located_method": resolved_logo.get("located_method") or resolved_logo.get("source"),
            "logo_box": {
                "x": round(lx, 2),
                "y": round(ly, 2),
                "width": round(lw, 2),
                "height": round(lh, 2),
                "source": resolved_logo["source"],
                "located_method": resolved_logo.get("located_method") or resolved_logo["source"],
            },'''

replacement = '''            "located_method": resolved_logo.get("located_method") or resolved_logo.get("source"),
            "logo_box": {
                "x": round(lx, 2),
                "y": round(ly, 2),
                "width": round(lw, 2),
                "height": round(lh, 2),
                "source": resolved_logo["source"],
                "located_method": resolved_logo.get("located_method") or resolved_logo["source"],
                **({"score": resolved_logo["score"]} if "score" in resolved_logo else {}),
                **({"scale": resolved_logo["scale"]} if "scale" in resolved_logo else {}),
            },'''

assert target in text
text = text.replace(target, replacement)

with open("backend/heatmap.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated backend/heatmap.py with logo_box score and scale")
