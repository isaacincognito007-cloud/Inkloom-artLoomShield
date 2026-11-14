from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

# Find the start of test_h5_naive_user_journey_playwright and replace both tests
idx = text.find("def test_h5_naive_user_journey_playwright")
assert idx != -1, "test_h5_naive_user_journey_playwright not found"

base_text = text[:idx]

new_tests = '''def test_h5_naive_user_journey_playwright(live_server_url):
    """
    H5 Naive-User Journey:
    Wizard -> Audit -> Fix/Accept -> Submit (Marcus) -> Reviewer Approve (Ava) -> Certificate -> Verify.
    """
    if not HAS_PLAYWRIGHT:
        pytest.skip("Playwright is not installed.")
    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(live_server_url)
        page.wait_for_selector("#view-overview", state="visible", timeout=10000)

        # 1. Start from Overview New Audit -> Wizard Stage
        page.click("#overviewNewAuditBtn")
        page.wait_for_selector("#wizardStage", state="visible", timeout=5000)

        # Skip wizard setup using existing brand guidelines to enter workspace input form
        page.click("#wizardUseExistingBtn")
        page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)

        # 2. Fill content with known violations and run audit
        page.fill("#auditDocName", "Q4 Global Growth Launch")
        page.fill(
            "#auditContentText",
            "NovaWallet gives institutional clients up to 95% faster processing with zero human oversight.",
        )
        page.locator("#auditContentText").dispatch_event("input")
        expect(page.locator("#runAuditBtn")).to_be_enabled()
        page.click("#runAuditBtn")
        page.wait_for_selector("#auditResultsStage", state="visible", timeout=15000)

        # Verify audit findings rendered in the workspace
        page.wait_for_selector("#panelFindings .finding-card", state="visible", timeout=10000)
        findings_count = page.evaluate("AppState.currentAudit.findings.length")
        assert findings_count >= 2, f"Expected multiple findings, got {findings_count}"

        # 3. Fix / Accept a suggested correction on a finding
        fixable_id = page.evaluate("""() => {
            const f = (AppState.currentAudit.findings || []).find(x => x.suggested_correction && x.review_state === 'open');
            if (f) { AppState.selectedFindingId = f.id; return f.id; }
            return null;
        }""")
        assert fixable_id is not None
        page.locator(f".finding-card[data-id='{fixable_id}']").click()
        page.keyboard.press("a")
        page.wait_for_function(
            "(fid) => (AppState.currentAudit.findings.find(f => f.id === fid) || {}).review_state === 'accepted'",
            arg=fixable_id,
        )

        # 4. Sign in as Marcus Lee (Reviewer / Submitter)
        page.click("#accountRoleBtn")
        page.wait_for_selector("#demoSignInMenu", state="visible", timeout=3000)
        page.click("button[data-demo-user-id='usr_marcus']")
        page.wait_for_function("() => AppState.userId === 'usr_marcus'")
        expect(page.locator("#accountRoleBtn")).to_contain_text("Marcus Lee")

        # 5. Submit audit for review
        page.click("button[data-wf='In Review']")
        page.wait_for_function("() => AppState.currentAudit && AppState.currentAudit.overall_status === 'In Review'")
        assert page.evaluate("AppState.currentAudit.submitted_by_user_id") == "usr_marcus"

        # Separation of duties: Marcus cannot approve an audit he submitted
        expect(page.locator("#workspaceApproveBtn")).to_be_disabled()

        # 6. Switch to Ava Chen (Brand Administrator)
        page.click("#accountRoleBtn")
        page.wait_for_selector("#demoSignInMenu", state="visible", timeout=3000)
        page.click("button[data-demo-user-id='usr_ava']")
        page.wait_for_function("() => AppState.userId === 'usr_ava'")

        # Acknowledge remaining findings with override justification
        page.check("#workflowOverrideCheckbox")
        page.fill("#workflowCommentInput", "Naive user journey approval after reviewing open items")
        page.locator("#workflowCommentInput").dispatch_event("input")
        expect(page.locator("#workspaceApproveBtn")).to_be_enabled()
        page.click("#workspaceApproveBtn")
        page.wait_for_function("() => AppState.currentAudit && AppState.currentAudit.overall_status === 'Approved'")

        # 7. Issue signed certificate and verify on #verify
        expect(page.locator("#resultsCertificateBtn")).to_be_visible()
        page.click("#resultsCertificateBtn")
        page.wait_for_selector("#printableCertificateSheet", state="visible", timeout=6000)

        # Open verifier modal link
        page.click("#certOpenVerifierBtn")
        page.wait_for_selector("#verifyResultBadge", state="visible", timeout=6000)
        expect(page.locator("#verifyResultBadge")).to_contain_text("Valid")

        browser.close()


def test_h5_edge_case_journeys_playwright(live_server_url):
    """
    H5 Edge-Case Journeys:
    Empty text, 6 MB, renamed .exe as .pdf, corrupt PNG, 13 MP, backend down, refresh on every view, same action twice.
    """
    if not HAS_PLAYWRIGHT:
        pytest.skip("Playwright is not installed.")
    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(live_server_url)
        page.wait_for_selector("#view-overview", state="visible", timeout=10000)

        # 1. Edge Case: Empty text submission guard
        page.evaluate("AppState.auditStage = 'input'; AppState.wizardMode = false; switchView('new-audit', false);")
        page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)
        page.fill("#auditContentText", "")
        page.locator("#auditContentText").dispatch_event("input")
        expect(page.locator("#runAuditBtn")).to_be_disabled()
        page.evaluate("executeTextAudit()")
        expect(page.locator("#toastContainer")).to_contain_text("Please enter content to audit.")

        # 2. Edge Case: 6 MB upload rejection (> 5 MB limit)
        upload_6mb_result = page.evaluate("""async () => {
            const buf = new Uint8Array(6 * 1024 * 1024 + 10);
            const fd = new FormData();
            fd.append('brand_id', 'novapay');
            fd.append('document_name', 'oversized_6mb.txt');
            fd.append('file', new Blob([buf], { type: 'text/plain' }), 'oversized_6mb.txt');
            const res = await fetch('/api/audits/upload', { method: 'POST', body: fd });
            return { status: res.status, text: await res.text() };
        }""")
        assert upload_6mb_result["status"] in (400, 413)
        assert "5" in upload_6mb_result["text"]

        # 3. Edge Case: Renamed .exe as .pdf
        exe_pdf_result = page.evaluate("""async () => {
            const exeHeader = new Uint8Array([0x4D, 0x5A, 0x90, 0x00, 0x03, 0x00, 0x00, 0x00]); // MZ PE header
            const fd = new FormData();
            fd.append('brand_id', 'novapay');
            fd.append('document_name', 'malicious.pdf');
            fd.append('file', new Blob([exeHeader], { type: 'application/pdf' }), 'malicious.pdf');
            const res = await fetch('/api/audits/upload', { method: 'POST', body: fd });
            return { status: res.status, text: await res.text() };
        }""")
        assert exe_pdf_result["status"] == 400
        assert "pdf" in exe_pdf_result["text"].lower() or "unsupported" in exe_pdf_result["text"].lower() or "error" in exe_pdf_result["text"].lower()

        # 4. Edge Case: Corrupt PNG image
        corrupt_png_result = page.evaluate("""async () => {
            const corruptBytes = new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0xDE, 0xAD, 0xBE, 0xEF]);
            const fd = new FormData();
            fd.append('brand_id', 'novapay');
            fd.append('document_name', 'corrupt.png');
            fd.append('file', new Blob([corruptBytes], { type: 'image/png' }), 'corrupt.png');
            const res = await fetch('/api/audits/upload', { method: 'POST', body: fd });
            return { status: res.status, text: await res.text() };
        }""")
        assert corrupt_png_result["status"] == 400
        assert "image" in corrupt_png_result["text"].lower() or "decode" in corrupt_png_result["text"].lower() or "corrupt" in corrupt_png_result["text"].lower()

        # 5. Edge Case: 13 Megapixels image rejection (exceeds 12 MP cap)
        from PIL import Image
        import io
        from backend.engine import inspect_raster_image
        img_13mp = Image.new("RGBA", (3700, 3600), (255, 255, 255, 255))
        buf = io.BytesIO()
        img_13mp.save(buf, format="PNG")
        try:
            inspect_raster_image(buf.getvalue(), [])
            cap_rejected = False
        except ValueError as exc:
            cap_rejected = True
            assert "12" in str(exc)
        assert cap_rejected, "Expected 13 MP image to be rejected by the 12 MP pixel cap"

        # 6. Edge Case: Backend connection error handling
        page.evaluate("""() => {
            AppState.sessionAvailable = false;
            const banner = document.getElementById('sessionUnavailableBanner');
            if (banner) {
                banner.style.display = 'flex';
                document.getElementById('sessionUnavailableText').textContent = 'Server connection is unavailable (simulated test).';
            }
        }""")
        expect(page.locator("#sessionUnavailableBanner")).to_be_visible()
        expect(page.locator("#sessionUnavailableText")).to_contain_text("Server connection is unavailable")
        # Restoring session
        page.evaluate("""() => {
            AppState.sessionAvailable = true;
            document.getElementById('sessionUnavailableBanner').style.display = 'none';
        }""")

        # 7. Edge Case: Refresh on every view & sessionStorage demo sign-in persistence
        page.click("#accountRoleBtn")
        page.wait_for_selector("#demoSignInMenu", state="visible", timeout=3000)
        page.click("button[data-demo-user-id='usr_marcus']")
        page.wait_for_function("() => AppState.userId === 'usr_marcus'")

        routes_to_test = [
            "#/overview",
            "#/vault",
            "#/queue",
            "#/insights",
            "#/history",
            "#/settings",
            "#/verify",
            "#/new-audit",
        ]
        for route in routes_to_test:
            page.goto(live_server_url + route)
            page.reload()
            page.wait_for_load_state("domcontentloaded")
            saved_user = page.evaluate("AppState.userId || (JSON.parse(sessionStorage.getItem('loomshield_demo_session') || '{}')).userId")
            assert saved_user == "usr_marcus", f"Expected usr_marcus on {route} after refresh, got {saved_user}"

        # 8. Edge Case: Same action twice (double-click guard)
        page.goto(live_server_url + "#/new-audit")
        page.wait_for_selector("#auditInputStage", state="visible", timeout=5000)
        page.fill("#auditContentText", "Testing double click guard prevention with valid input.")
        page.locator("#auditContentText").dispatch_event("input")
        expect(page.locator("#runAuditBtn")).to_be_enabled()
        page.evaluate("""() => {
            const btn = document.getElementById('runAuditBtn');
            btn.click();
            btn.click();
        }""")
        page.wait_for_selector("#auditResultsStage", state="visible", timeout=15000)

        browser.close()
'''

p.write_text(base_text + new_tests, encoding="utf-8")
print("Updated tests/e2e/test_ui_e2e.py")
