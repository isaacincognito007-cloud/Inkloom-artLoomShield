with open("tests/test_clarity_rewriter.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''        prop_res = client.post(
            "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
            json={
                "new_text": "Write for the target reader's domain, defining protocols on first mention [SET THRESHOLD: max 30 words per overview].",
                "do_examples": ["Include SLA numbers."],
                "dont_examples": ["Avoid undefined acronyms."],
            },
            headers={"X-Test-Role": "Brand Administrator"},
        )'''

replacement = '''        prop_res = client.post(
            "/api/ambiguity-radar/novapay/rules/RULE-TONE-02/propose",
            json={},
            headers={"X-Test-Role": "Brand Administrator"},
        )'''

assert target in text, "target not found"
text = text.replace(target, replacement)

with open("tests/test_clarity_rewriter.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed test_h1 in tests/test_clarity_rewriter.py")
