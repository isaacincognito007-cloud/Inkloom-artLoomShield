with open("backend/database.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''    _ensure_column(cur, "brands", "min_clear_space_ratio", "REAL DEFAULT 0.25")
    _ensure_column(cur, "brands", "min_clear_space_px", "INTEGER DEFAULT 16")'''

replacement = '''    _ensure_column(cur, "brands", "min_clear_space_ratio", "REAL DEFAULT 0.25")
    _ensure_column(cur, "brands", "min_clear_space_px", "INTEGER DEFAULT 16")
    _ensure_column(cur, "brands", "approved_logo_b64", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_format", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_filename", "TEXT DEFAULT ''")
    _ensure_column(cur, "brands", "approved_logo_updated_at", "TEXT DEFAULT ''")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS certificate_revocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id TEXT NOT NULL UNIQUE,
            audit_id TEXT NOT NULL,
            brand_id TEXT NOT NULL,
            revoked_by TEXT NOT NULL,
            revoked_by_user_id TEXT DEFAULT '',
            revocation_reason TEXT NOT NULL,
            revoked_at TEXT NOT NULL
        );
        """
    )'''

assert target in text, "target not found in database.py"
text = text.replace(target, replacement)

with open("backend/database.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated backend/database.py migrations successfully")
