from pathlib import Path

# 1. Fix frontend/app.js
p_app = Path(r"D:\LoomShield\frontend\app.js")
app_text = p_app.read_text(encoding="utf-8")

# Update command palette line 6407
old_cmd = "{ type: 'Action', label: 'New audit', detail: 'Start auditing new document copy or files', run: () => { AppState.auditStage = 'input'; switchView('new-audit'); } },"
new_cmd = "{ type: 'Action', label: 'New audit', detail: 'Start auditing new document copy or files', run: () => { AppState.auditStage = 'input'; AppState.wizardMode = true; AppState.wizardStep = 1; switchView('new-audit'); } },"
assert old_cmd in app_text, "old_cmd not found"
app_text = app_text.replace(old_cmd, new_cmd, 1)

# Update switchView hash update with isNavigatingHash timeout
old_switch_hash = """    if (hashMap[viewName] && window.location.hash !== hashMap[viewName]) {
      window.location.hash = hashMap[viewName];
    }"""
new_switch_hash = """    if (hashMap[viewName] && window.location.hash !== hashMap[viewName]) {
      isNavigatingHash = true;
      window.location.hash = hashMap[viewName];
      setTimeout(() => { isNavigatingHash = false; }, 50);
    }"""
assert old_switch_hash in app_text, "old_switch_hash not found"
app_text = app_text.replace(old_switch_hash, new_switch_hash, 1)

# Update openAuditById hash update with isNavigatingHash timeout
old_open_hash = """    if (updateHash && !isNavigatingHash) {
      window.location.hash = `#/audit/${encodeURIComponent(auditId)}`;
    }"""
new_open_hash = """    if (updateHash && !isNavigatingHash) {
      isNavigatingHash = true;
      window.location.hash = `#/audit/${encodeURIComponent(auditId)}`;
      setTimeout(() => { isNavigatingHash = false; }, 50);
    }"""
assert old_open_hash in app_text, "old_open_hash not found"
app_text = app_text.replace(old_open_hash, new_open_hash, 1)

# Update handleHashRouting new-audit condition
old_handle_new_audit = """    } else if (rawHash === '#/new-audit' || rawHash === '#new-audit') {
      AppState.auditStage = 'input';
      AppState.wizardMode = false;
      await switchView('new-audit', false);"""
new_handle_new_audit = """    } else if (rawHash === '#/new-audit' || rawHash === '#new-audit') {
      AppState.auditStage = 'input';
      if (AppState.wizardMode !== true) {
        AppState.wizardMode = false;
      }
      await switchView('new-audit', false);"""
assert old_handle_new_audit in app_text, "old_handle_new_audit not found"
app_text = app_text.replace(old_handle_new_audit, new_handle_new_audit, 1)

p_app.write_text(app_text, encoding="utf-8")
print("frontend/app.js updated")

# 2. Fix tests/e2e/test_ui_e2e.py selectors
p_e2e = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
e2e_text = p_e2e.read_text(encoding="utf-8")

e2e_text = e2e_text.replace(
    'page.wait_for_selector("#inputStage", state="visible", timeout=5000)',
    'page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)',
)
e2e_text = e2e_text.replace(
    'page.wait_for_selector("#resultsStage", state="visible", timeout=15000)',
    'page.wait_for_selector("#auditResultsStage", state="visible", timeout=15000)',
)

p_e2e.write_text(e2e_text, encoding="utf-8")
print("tests/e2e/test_ui_e2e.py updated")
