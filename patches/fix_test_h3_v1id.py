with open("tests/test_certificates_and_identities.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''        v1_payload = copy.deepcopy(payload)
        v1_payload["certificate_version"] = 1'''

replacement = '''        v1_payload = copy.deepcopy(payload)
        v1_payload["certificate_version"] = 1
        v1_payload["certificate_id"] = "CERT-V1-COMPAT"'''

assert target in text
text = text.replace(target, replacement)

with open("tests/test_certificates_and_identities.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated v1_payload certificate_id in test_certificates_and_identities.py")
