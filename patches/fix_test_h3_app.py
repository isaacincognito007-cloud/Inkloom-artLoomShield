with open("tests/test_certificates_and_identities.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '    client = TestClient(app)'
replacement = '    client = TestClient(main_mod.app)'

assert target in text
text = text.replace(target, replacement)

with open("tests/test_certificates_and_identities.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed app import in test_certificates_and_identities.py")
