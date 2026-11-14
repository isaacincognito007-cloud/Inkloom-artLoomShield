with open("backend/clarity_rewriter.py", "r", encoding="utf-8") as f:
    text = f.read()

target1 = '"""Deterministically score a guideline rule from 0 (completely clear) to 100 (highly ambiguous)."""'
replace1 = '''"""Deterministically score a guideline rule from 0 (completely clear) to 100 (highly ambiguous).

    Score evaluates vagueness indicators, missing measurable criteria, override and dismissal rates, and accepted corrections.
    """'''

assert target1 in text, "target1 not found"
text = text.replace(target1, replace1)

target2 = '"""Combine deterministic ambiguity score with override telemetry respecting the minimum sample threshold."""'
replace2 = '''"""Combine deterministic ambiguity score with override telemetry respecting the minimum sample threshold.

    Score evaluates vagueness indicators, missing measurable criteria, override and dismissal rates, and accepted corrections.
    """'''

assert target2 in text, "target2 not found"
text = text.replace(target2, replace2)

with open("backend/clarity_rewriter.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated backend/clarity_rewriter.py successfully")
