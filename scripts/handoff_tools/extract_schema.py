import re

with open(r"D:\LoomShield\backend\database.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find CREATE TABLE statements
create_tables = re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-zA-Z0-9_]+)\s*\((.*?)\);", content, re.DOTALL)
print(f"Found {len(create_tables)} CREATE TABLE definitions in database.py:")
for table_name, schema in create_tables:
    print(f"\n--- Table: {table_name} ---")
    cols = [line.strip() for line in schema.split("\n") if line.strip() and not line.strip().startswith("--")]
    for c in cols[:15]:
        print(f"  {c}")
    if len(cols) > 15:
        print(f"  ... and {len(cols) - 15} more lines")
