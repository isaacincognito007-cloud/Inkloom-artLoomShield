from pathlib import Path

p = Path(r"D:\LoomShield\tests\test_certificates_and_identities.py")
content = p.read_bytes()
target = b'assert payload["certificate_version"] == 1'
replacement = b'assert payload["certificate_version"] == 2'
assert target in content
new_content = content.replace(target, replacement, 1)
p.write_bytes(new_content)
print("Replaced successfully")
