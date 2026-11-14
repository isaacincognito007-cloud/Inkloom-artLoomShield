from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_step8 = """        # 8. Edge Case: Same action twice (double-click guard)
        page.goto(live_server_url + "#/new-audit")
        page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)"""

new_step8 = """        # 8. Edge Case: Same action twice (double-click guard)
        page.goto(live_server_url + "#/new-audit")
        if page.locator("#wizardUseExistingBtn").is_visible():
            page.locator("#wizardUseExistingBtn").click()
        else:
            page.evaluate("AppState.auditStage = 'input'; AppState.wizardMode = false; switchView('new-audit', false);")
        page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)"""

assert old_step8 in text, "old_step8 not found"
text = text.replace(old_step8, new_step8, 1)

p.write_text(text, encoding="utf-8")
print("Updated step 8 in tests/e2e/test_ui_e2e.py")
