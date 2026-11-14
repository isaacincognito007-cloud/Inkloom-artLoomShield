with open("tests/test_certificates_and_identities.py", "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

for i, l in enumerate(lines):
    if 'v1_payload["certificate_version"] = 1' in l:
        lines.insert(i + 1, '    v1_payload["certificate_id"] = "CERT-V1-COMPAT"')
        break

with open("tests/test_certificates_and_identities.py", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Added CERT-V1-COMPAT to line")
