import re

with open(r"D:\LoomShield\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

routes = re.findall(r"@app\.(get|post|put|delete|patch)\(\"([^\"]+)\"", content)
print(f"Total routes in main.py: {len(routes)}")
for method, path in routes:
    print(f"  {method.upper():6} {path}")
