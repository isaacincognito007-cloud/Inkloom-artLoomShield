with open("tests/test_certificates_and_identities.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '    init_db()\n    reset_demo_workspace()'
replacement = '    from backend.database import reset_demo_workspace\n    init_db()\n    reset_demo_workspace()'

assert target in text
text = text.replace(target, replacement)

with open("tests/test_certificates_and_identities.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed import in test_certificates_and_identities.py")
