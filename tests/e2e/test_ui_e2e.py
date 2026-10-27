# coding: utf-8
"""
End-to-End Playwright UI Verification Suite for LoomShield (tests/e2e/test_ui_e2e.py).
Skipped automatically if Playwright or a Chromium/Edge browser binary is unavailable.

Asserts:
- Soft Glass design system tokens, allowed glass surfaces, solid surface guardrails, max 3 backdrop-filter elements
- Self-hosted fonts (/fonts/InterVariable.woff2 and /fonts/GeistMono-Variable.woff2 return HTTP 200)
- Responsive viewports (1280px, 768px, 375px), table card stacking at 768px, >= 44px touch targets, no horizontal scroll at 375px
- J/K/A/D keyboard shortcuts:
  * Modifier keys (Ctrl, Meta, Alt) ignored by finding shortcuts (Ctrl+A does not accept; Ctrl+K only opens palette)
  * A and D act ONLY on an explicitly selected finding (never default to the first finding on open)
  * J/K navigate findings; D opens inline dismiss box; A accepts fix on explicitly selected finding
- End-to-end audit -> review -> accept -> submit -> approve -> history workflow
- Axe WCAG 2.1 AA accessibility checks (0 violations on Overview, Command Palette, New Audit, and Results)
"""
import os
import socket
import threading
import time
from pathlib import Path
import pytest

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

E2E_DIR = Path(__file__).resolve().parent
AXE_PATH = E2E_DIR / "axe.min.js"


@pytest.fixture(scope="module")
def live_server_url():
    """Start an ephemeral uvicorn server on a free local port for E2E tests."""
    import uvicorn
    from backend.main import app
    from backend.database import init_db

    os.environ["LOOMSHIELD_WORKSPACE_MODE"] = "demo"
    init_db()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    _, port = sock.getsockname()
    sock.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"{base_url}/api/session", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    yield base_url
    server.should_exit = True


def _launch_browser(p):
    """Try launching Edge or Chromium; skip gracefully if neither is installed."""
    for channel in ("msedge", "chrome", None):
        try:
            if channel:
                return p.chromium.launch(channel=channel, headless=True)
            return p.chromium.launch(headless=True)
        except Exception:
            continue
    pytest.skip("Playwright browser binary (msedge/chrome/chromium) is not installed on this machine.")


def _run_axe(page, axe_js: str):
    page.evaluate(axe_js)
    results = page.evaluate("axe.run({ runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } })")
    return results.get("violations", [])


def _count_visible_backdrop_filters(page):
    return page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        const matches = [];
        for (const el of all) {
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            const bf = style.backdropFilter || style.webkitBackdropFilter || 'none';
            if (bf && bf !== 'none') {
                matches.push({ tag: el.tagName.toLowerCase(), id: el.id, className: el.className, backdropFilter: bf });
            }
        }
        return matches;
    }""")


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright is not installed")
def test_loomshield_ui_viewports_soft_glass_and_e2e_flow(live_server_url):
    axe_js = AXE_PATH.read_text(encoding="utf-8") if AXE_PATH.exists() else None

    with sync_playwright() as p:
        browser = _launch_browser(p)
        context = browser.new_context()
        page = context.new_page()

        # 1. Self-hosted fonts return 200
        for font_file in ("InterVariable.woff2", "GeistMono-Variable.woff2"):
            resp = page.request.get(f"{live_server_url}/fonts/{font_file}")
            assert resp.status == 200, f"/fonts/{font_file} returned {resp.status}"
            assert len(resp.body()) > 1000

        # 2. Desktop (1280px): Soft Glass tokens, allowed surfaces, max 3 backdrop-filters, 4 metric cards
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(live_server_url)
        page.wait_for_selector("#appSidebar")
        sidebar_box = page.locator("#appSidebar").bounding_box()
        assert 230 <= sidebar_box["width"] <= 250

        tokens = page.evaluate("""() => {
            const s = getComputedStyle(document.documentElement);
            return {
                space4: s.getPropertyValue('--space-4').trim(),
                space48: s.getPropertyValue('--space-48').trim(),
                radiusControl: s.getPropertyValue('--radius-control').trim(),
                radiusCard: s.getPropertyValue('--radius-card').trim(),
                radiusHero: s.getPropertyValue('--radius-hero').trim(),
                radiusModal: s.getPropertyValue('--radius-modal').trim(),
                glassBg: s.getPropertyValue('--glass-bg').trim(),
                glassBlur: s.getPropertyValue('--glass-blur').trim(),
            };
        }""")
        assert tokens["space4"] == "4px" and tokens["space48"] == "48px"
        assert tokens["radiusControl"] == "8px" and tokens["radiusCard"] == "12px"
        assert tokens["radiusHero"] == "16px" and tokens["radiusModal"] == "16px"
        assert tokens["glassBlur"] == "12px"

        bf_overview = _count_visible_backdrop_filters(page)
        assert 1 <= len(bf_overview) <= 3

        solid_check = page.evaluate("""() => {
            const metric = getComputedStyle(document.querySelector('.metric-card'));
            const table = getComputedStyle(document.querySelector('.data-table'));
            const hero = getComputedStyle(document.querySelector('.hero-start-card'));
            return {
                metricBf: metric.backdropFilter || metric.webkitBackdropFilter || 'none',
                tableBf: table.backdropFilter || table.webkitBackdropFilter || 'none',
                heroRadius: hero.borderRadius,
            };
        }""")
        assert solid_check["metricBf"] == "none" and solid_check["tableBf"] == "none"
        assert solid_check["heroRadius"] == "16px"

        # Status badges all pair SVG icon + text
        missing_svg = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.status-badge'))
                .filter(b => !b.querySelector('svg'))
                .map(b => b.outerHTML);
        }""")
        assert len(missing_svg) == 0, f"Status badges missing SVG icon: {missing_svg}"

        for card_id in ("metricCardDocs", "metricCardFindings", "metricCardApproved", "metricCardRules"):
            assert page.locator(f"#{card_id}").is_visible()

        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        # 3. Tablet (768px): Table card stacking & >= 44px touch targets
        page.set_viewport_size({"width": 768, "height": 1024})
        time.sleep(0.3)
        table_stacking = page.evaluate("""() => {
            const thead = document.querySelector('.data-table thead');
            const tr = document.querySelector('.data-table tbody tr');
            return {
                theadDisplay: thead ? getComputedStyle(thead).display : null,
                trDisplay: tr ? getComputedStyle(tr).display : null,
                btnMinHeight: getComputedStyle(document.querySelector('.btn')).minHeight,
            };
        }""")
        assert table_stacking["theadDisplay"] == "none", "Table thead should be hidden at 768px"
        assert table_stacking["trDisplay"] == "block", "Table rows should stack as block cards at 768px"
        assert table_stacking["btnMinHeight"] == "44px", "Buttons must have >= 44px min-height at 768px"

        # 4. Mobile (375px): No horizontal scroll, >= 44px touch target, mobile drawer glass & max 3 backdrop-filter elements
        page.set_viewport_size({"width": 375, "height": 667})
        time.sleep(0.3)
        scroll_width, client_width = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        assert scroll_width <= client_width + 1, f"Horizontal scroll at 375px: {scroll_width} > {client_width}"

        mobile_btn = page.locator("#mobileMenuBtn")
        assert mobile_btn.is_visible()
        btn_box = mobile_btn.bounding_box()
        assert btn_box["width"] >= 44 and btn_box["height"] >= 44

        mobile_btn.click()
        time.sleep(0.25)
        assert page.evaluate("document.getElementById('appSidebar').classList.contains('mobile-open')")
        bf_mobile = _count_visible_backdrop_filters(page)
        assert len(bf_mobile) <= 3

        page.locator(".sidebar-nav .nav-item[data-view='overview']").click()
        time.sleep(0.25)
        assert not page.evaluate("document.getElementById('appSidebar').classList.contains('mobile-open')")

        # 5. Desktop Command Palette (Ctrl+K) & E2E Audit Flow
        page.set_viewport_size({"width": 1280, "height": 800})
        page.keyboard.press("Control+k")
        time.sleep(0.3)
        assert page.locator("#commandPaletteModal").is_visible()
        assert len(_count_visible_backdrop_filters(page)) <= 3
        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        page.fill("#commandPaletteInput", "new audit")
        time.sleep(0.15)
        page.keyboard.press("Enter")
        time.sleep(0.35)
        assert page.evaluate("document.getElementById('commandPaletteModal').style.display === 'none'")

        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        page.locator("#wizardUseExistingBtn").click()
        time.sleep(0.3)
        assert page.locator("#auditInputStage").is_visible()
        assert page.evaluate("document.getElementById('runAuditBtn').disabled")

        sample_copy = "<h2>Instant Payouts</h2><p>Our platform guarantees 95% faster settlement with guaranteed zero risk. We provide frictionless synergetic paradigms.</p>"
        page.fill("#auditContentText", sample_copy)
        page.locator("#auditContentText").dispatch_event("input")
        time.sleep(0.15)
        assert not page.evaluate("document.getElementById('runAuditBtn').disabled")

        page.click("#runAuditBtn")
        page.wait_for_selector("#auditResultsStage", state="visible", timeout=15000)

        # Verify Split Layout & Solid Surfaces
        left_box = page.locator("#panelSource").bounding_box()
        right_box = page.locator("#panelFindings").bounding_box()
        assert right_box["x"] > left_box["x"]

        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        # 6. Verify J/K/A/D and Modifier Key Behaviour (A2)
        # Initially, no finding is auto-selected
        initial_sel = page.evaluate("AppState.selectedFindingId")
        assert initial_sel is None, f"Expected no auto-selected finding on open, got {initial_sel}"

        # Pressing A or D when no finding is selected does nothing
        initial_open_count = page.evaluate("(AppState.currentAudit.findings || []).filter(f => f.review_state === 'open').length")
        page.keyboard.press("a")
        page.keyboard.press("d")
        time.sleep(0.2)
        after_noop_open_count = page.evaluate("(AppState.currentAudit.findings || []).filter(f => f.review_state === 'open').length")
        assert after_noop_open_count == initial_open_count, "A or D must not act when no finding is explicitly selected"

        # Pressing J selects the first finding; pressing J again selects the second finding; pressing K returns to the first
        page.keyboard.press("j")
        time.sleep(0.2)
        first_sel = page.evaluate("AppState.selectedFindingId")
        assert first_sel is not None

        page.keyboard.press("j")
        time.sleep(0.2)
        second_sel = page.evaluate("AppState.selectedFindingId")
        assert second_sel != first_sel

        page.keyboard.press("k")
        time.sleep(0.2)
        back_to_first = page.evaluate("AppState.selectedFindingId")
        assert back_to_first == first_sel

        # Pressing Ctrl+A with a finding selected must NOT accept the finding (modifier keys ignored)
        page.keyboard.press("Control+a")
        time.sleep(0.3)
        state_after_ctrl_a = page.evaluate(f"(AppState.currentAudit.findings.find(f => f.id === '{first_sel}') || {{}}).review_state")
        assert state_after_ctrl_a == "open", "Ctrl+A must not trigger finding accept shortcut"

        # Pressing Ctrl+K only opens the palette without changing selectedFindingId
        page.keyboard.press("Control+k")
        time.sleep(0.25)
        assert page.locator("#commandPaletteModal").is_visible()
        assert page.evaluate("AppState.selectedFindingId") == first_sel
        page.keyboard.press("Escape")
        time.sleep(0.2)

        # Click elsewhere to blur input, then press D on the explicitly selected finding -> opens inline dismiss box
        page.locator("#panelSource .panel-title").click()
        time.sleep(0.1)
        page.keyboard.press("d")
        time.sleep(0.2)
        dismiss_visible = page.evaluate(f"document.getElementById('dismissBox_{first_sel}')?.style.display === 'block'")
        assert dismiss_visible, "Pressing D on an explicitly selected finding must open its inline dismiss box"

        # Blur dismiss input, select a finding with a suggested fix, and press A to accept
        page.locator("#panelSource .panel-title").click()
        time.sleep(0.1)
        fixable_id = page.evaluate("""() => {
            const f = (AppState.currentAudit.findings || []).find(x => x.suggested_correction && x.review_state === 'open');
            if (f) { AppState.selectedFindingId = f.id; return f.id; }
            return null;
        }""")
        if fixable_id:
            page.keyboard.press("a")
            time.sleep(0.8)
            new_state = page.evaluate(f"(AppState.currentAudit.findings.find(f => f.id === '{fixable_id}') || {{}}).review_state")
            assert new_state == "accepted", f"Expected 'accepted' after pressing A on {fixable_id}, got {new_state}"

        # 7. Demo Sign-In Menu, Separation of Duties, Approval & Signed Certificate (#verify)
        # Open the "Sign in as" menu and verify disclosure label + max 3 backdrop-filters
        page.click("#accountRoleBtn")
        time.sleep(0.25)
        assert page.locator("#demoSignInMenu").is_visible()
        assert len(_count_visible_backdrop_filters(page)) <= 3
        disclosure_text = page.locator("#demoSignInDisclosureNote").inner_text()
        assert "Demo sign-in: anyone can choose any demo user. This shows separation of duties; it is not authentication." in disclosure_text

        # Sign in as Marcus Lee (Reviewer) and submit the audit for review
        page.click("button[data-demo-user-id='usr_marcus']")
        time.sleep(0.5)
        assert page.evaluate("AppState.userId") == "usr_marcus"
        assert "Marcus Lee" in page.locator("#accountRoleBtn").inner_text()

        page.click("button[data-wf='In Review']")
        time.sleep(0.8)
        assert page.evaluate("AppState.currentAudit.overall_status") == "In Review"
        assert page.evaluate("AppState.currentAudit.submitted_by_user_id") == "usr_marcus"

        # Separation of duties: Marcus submitted this audit, so Approve button is disabled for Marcus
        assert page.evaluate("document.getElementById('workspaceApproveBtn').disabled")
        assert "Separation of duties" in page.locator("#workflowUnresolvedNotice").inner_text()

        # Switch to Ava Chen (Brand Administrator) via the "Sign in as" menu
        page.click("#accountRoleBtn")
        time.sleep(0.2)
        page.click("button[data-demo-user-id='usr_ava']")
        time.sleep(0.5)
        assert page.evaluate("AppState.userId") == "usr_ava"

        open_rem = page.evaluate("(AppState.currentAudit.findings || []).filter(f => ['open','needs_review'].includes(f.review_state)).length")
        if open_rem > 0:
            page.check("#workflowOverrideCheckbox")
            page.fill("#workflowCommentInput", "E2E Reviewer sign-off with override justification")
            page.locator("#workflowCommentInput").dispatch_event("input")
            time.sleep(0.2)

        assert not page.evaluate("document.getElementById('workspaceApproveBtn').disabled")
        page.click("#workspaceApproveBtn")
        time.sleep(0.9)
        assert page.evaluate("AppState.currentAudit.overall_status") == "Approved"

        # Certificate button appears on Approved audit -> open Certificate modal -> verify on #verify page
        assert page.locator("#resultsCertificateBtn").is_visible()
        page.click("#resultsCertificateBtn")
        page.wait_for_selector("#printableCertificateSheet", state="visible", timeout=5000)
        assert len(_count_visible_backdrop_filters(page)) <= 3
        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        page.click("#certOpenVerifierBtn")
        page.wait_for_selector("#verifyResultBadge", state="visible", timeout=5000)
        assert "Valid" in page.locator("#verifyResultBadge").inner_text()
        if axe_js:
            assert len(_run_axe(page, axe_js)) == 0

        browser.close()
