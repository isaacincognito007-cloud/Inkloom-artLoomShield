with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

target = "## 8. Round 3 Traceability Table, Certificate Format v1, and Heatmap Limits"
anchor_section = """## What Certificates Do and Do Not Prove

LoomShield compliance certificates are cryptographically verifiable records exported as canonical JSON envelopes signed with Ed25519.

### What Certificates Prove
1. **Cryptographic Authenticity & Integrity:** An Ed25519 digital signature over canonical UTF-8 JSON proves that the certificate envelope was signed by the private key corresponding to the stated key ID (`kid`).
2. **Immutability of Audit Content & Findings:** Any post-issuance alteration to the certified text SHA-256, original content SHA-256, findings summary, policy dismissals, submitter identity, or approver metadata mathematically breaks the signature (verified both online and offline via `scripts/verify_certificate.py`).
3. **Governance Traceability & Separation of Duties:** Documents the verified submitter (`submitted_by` `{user_id, name, role}`), approver sign-off (`approval` `{approver_name, approver_role, approved_at, override_acknowledged}`), Brand Vault guideline version (`brand_version`), and engine version (`engine_version`).
4. **Revocation Registry:** Each certificate includes a public revocation status endpoint (`revocation.status_url`) queryable without authentication or content disclosure.

### What Certificates Do NOT Prove (and Why External Anchoring is Not Built)
1. **No Legal or Regulatory Warranty:** Compliance certificates certify adherence to internal configured Brand Vault rules; they do not constitute legal advice or an external regulatory guarantee.
2. **Why External Anchoring Outside the Database is Not Built:** External anchoring on public blockchains, transparency logs, or third-party RFC 3161 timestamp authorities is deliberately not built. In enterprise brand and marketing operations, guideline compliance reviews are internal organizational governance assertions, not decentralized cross-organization contracts. Anchoring hashes on external public ledgers introduces third-party network failure modes, gas fees, and competitive timing/metadata leakage regarding unannounced marketing campaigns. Self-contained Ed25519 signatures over canonical JSON with offline verifiability and server-side revocation satisfy organizational compliance and audit requirements cleanly without external blockchain dependencies.

---

"""

assert target in text, "target not found in README.md"
text = text.replace(target, anchor_section + target)

# Also update the traceability table to include test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility
trace_target = "test_h3_certificate_post_requires_approve_and_get_never_issues,"
trace_replacement = "test_h3_certificate_post_requires_approve_and_get_never_issues, `test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility`,"

if trace_target in text:
    text = text.replace(trace_target, trace_replacement)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated README.md with 'What Certificates Do and Do Not Prove' successfully")
