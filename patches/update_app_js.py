import re
from pathlib import Path

p = Path(r"D:\LoomShield\frontend\app.js")
text = p.read_text(encoding="utf-8")

# 1. 401 clear sessionStorage in apiFetch
old_401 = """      AppState.userInitials = 'SW';
      AppState.activeRole = (AppState.session && AppState.session.configured_role) || 'Content Creator';"""

new_401 = """      AppState.userInitials = 'SW';
      AppState.activeRole = (AppState.session && AppState.session.configured_role) || 'Content Creator';
      try { sessionStorage.removeItem('loomshield_demo_session'); } catch (_e) {}"""

assert old_401 in text
text = text.replace(old_401, new_401, 1)

# 2. Results certificate button double-click guard
old_cert_btn = """  document.getElementById('resultsCertificateBtn')?.addEventListener('click', () => {
    if (AppState.currentAudit && AppState.currentAudit.id) {
      openCertificateModal(AppState.currentAudit.id);
    }
  });"""

new_cert_btn = """  const resultsCertBtn = document.getElementById('resultsCertificateBtn');
  if (resultsCertBtn) {
    resultsCertBtn.addEventListener('click', async () => {
      if (resultsCertBtn.disabled || resultsCertBtn.dataset.busy === '1') return;
      resultsCertBtn.dataset.busy = '1';
      resultsCertBtn.disabled = true;
      try {
        if (AppState.currentAudit && AppState.currentAudit.id) {
          await openCertificateModal(AppState.currentAudit.id);
        }
      } finally {
        resultsCertBtn.disabled = false;
        resultsCertBtn.dataset.busy = '0';
      }
    });
  }"""

assert old_cert_btn in text
text = text.replace(old_cert_btn, new_cert_btn, 1)

# 3. Hash routing handler
old_hashchange = """  window.addEventListener('hashchange', async () => {
    const h = window.location.hash;
    if (h === '#verify') {
      await switchView('verify-certificate');
    } else if (h === '#new-audit') {
      AppState.auditStage = 'input';
      AppState.wizardMode = false;
      await switchView('new-audit');
    } else if (h === '#results') {
      const firstId = AppState.overviewData?.recent_audits?.[0]?.id || 'AUD-1001';
      await openAuditById(firstId);
    }
  });"""

new_hashchange = """  window.addEventListener('hashchange', async () => {
    await handleHashRouting();
  });"""

assert old_hashchange in text
text = text.replace(old_hashchange, new_hashchange, 1)

# 4. resetDemoBtn update
old_reset = """  document.getElementById('resetDemoBtn').addEventListener('click', () => {
    openModalDialog({
      title: 'Reset demo workspace',
      bodyHtml: 'This will restore the seeded NovaPay Enterprise and Verdant Clinical Systems demo guidelines, verified facts, and initial sample audits. Continue?',
      confirmLabel: 'Reset demo data',
      onConfirm: async () => {
        try {
          await apiFetch('/api/demo/reset', { method: 'POST' });
          AppState.currentAudit = null;
          AppState.selectedFindingId = null;
          await loadBrandsAndInit();
          showToast('Demo workspace restored to initial state.');
        } catch (err) {
          showToast(`Reset failed: ${err.message}`);
        }
      },
    });
  });"""

new_reset = """  document.getElementById('resetDemoBtn')?.addEventListener('click', () => {
    const btn = document.getElementById('resetDemoBtn');
    if (btn && (btn.disabled || btn.dataset.busy === '1')) return;
    openModalDialog({
      title: 'Reset demo workspace?',
      bodyHtml: '<p><strong>Notice:</strong> This workspace is shared by everyone using this demo link. Resetting will restore seeded sample audits, guidelines, and verified facts for all active visitors. Are you sure you want to reset?</p>',
      confirmLabel: 'Reset shared demo workspace',
      onConfirm: async () => {
        if (btn) {
          btn.disabled = true;
          btn.dataset.busy = '1';
        }
        try {
          await apiFetch('/api/demo/reset', { method: 'POST' });
          AppState.currentAudit = null;
          AppState.selectedFindingId = null;
          await loadBrandsAndInit();
          showToast('Shared demo workspace restored to initial state.');
        } catch (err) {
          showToast(`Reset failed: ${err.message}`);
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.dataset.busy = '0';
          }
        }
      },
    });
  });"""

assert old_reset in text
text = text.replace(old_reset, new_reset, 1)

# 5. switchView and handleHashRouting and openAuditById
old_switch_view = """async function switchView(viewName) {
  if (AppState.activeView !== viewName && !confirmDiscardUnsavedChanges()) {
    return;
  }
  AppState.activeView = viewName;
  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    const isCurrent = btn.getAttribute('data-view') === viewName;
    btn.classList.toggle('active', isCurrent);
    if (isCurrent) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });
  document.querySelectorAll('.workspace-view').forEach((sec) => {
    sec.style.display = sec.id === `view-${viewName}` ? 'block' : 'none';
  });
  document.getElementById('topbarViewTitle').textContent =
    viewName === 'new-audit' && AppState.auditStage === 'results'
      ? 'Audit results'
      : (VIEW_TITLES[viewName] || viewName);

  if (viewName === 'overview') await refreshOverview();
  if (viewName === 'new-audit') updateRunAuditBtnState();
  if (viewName === 'new-audit') renderAuditWorkspace();
  if (viewName === 'brand-vault') await refreshBrandVault();
  if (viewName === 'review-queue') await renderReviewQueueView();
  if (viewName === 'ambiguity-radar') await renderAmbiguityRadarView();
  if (viewName === 'audit-history') await renderAuditHistoryView();
  if (viewName === 'settings') renderSettingsView();
  if (viewName === 'engine-status') await renderEngineStatusView();
  if (viewName === 'verify-certificate') await renderVerifyCertificateView();
}"""

new_switch_view = """let isNavigatingHash = false;

async function handleHashRouting() {
  if (isNavigatingHash) return;
  isNavigatingHash = true;
  try {
    const rawHash = (window.location.hash || '').trim();
    if (!rawHash || rawHash === '#' || rawHash === '#/') {
      await switchView('overview', false);
      return;
    }
    const auditMatch = rawHash.match(/^#\/?audit\/([A-Za-z0-9_-]+)$/);
    if (auditMatch) {
      await openAuditById(auditMatch[1], false);
      return;
    }
    if (rawHash === '#results' || rawHash === '#/results') {
      if (AppState.currentAudit && AppState.currentAudit.id) {
        await openAuditById(AppState.currentAudit.id, false);
      } else if (AppState.overviewData?.recent_audits?.length > 0) {
        await openAuditById(AppState.overviewData.recent_audits[0].id, false);
      } else {
        AppState.auditStage = 'input';
        AppState.wizardMode = false;
        await switchView('new-audit', false);
      }
      return;
    }
    if (rawHash === '#/queue' || rawHash === '#queue') {
      await switchView('review-queue', false);
    } else if (rawHash === '#/insights' || rawHash === '#insights') {
      await switchView('ambiguity-radar', false);
    } else if (rawHash === '#/history' || rawHash === '#history') {
      await switchView('audit-history', false);
    } else if (rawHash === '#/vault' || rawHash === '#vault') {
      await switchView('brand-vault', false);
    } else if (rawHash === '#/settings' || rawHash === '#settings') {
      await switchView('settings', false);
    } else if (rawHash === '#/overview' || rawHash === '#overview') {
      await switchView('overview', false);
    } else if (rawHash === '#/verify' || rawHash === '#verify') {
      await switchView('verify-certificate', false);
    } else if (rawHash === '#/new-audit' || rawHash === '#new-audit') {
      AppState.auditStage = 'input';
      AppState.wizardMode = false;
      await switchView('new-audit', false);
    } else if (rawHash === '#/about' || rawHash === '#about') {
      await switchView('about-roadmap', false);
    } else if (rawHash === '#/engine-status' || rawHash === '#engine-status') {
      await switchView('engine-status', false);
    }
  } finally {
    isNavigatingHash = false;
  }
}

async function switchView(viewName, updateHash = true) {
  if (AppState.activeView !== viewName && !confirmDiscardUnsavedChanges()) {
    return;
  }
  AppState.activeView = viewName;
  if (updateHash && !isNavigatingHash) {
    const hashMap = {
      'overview': '#/overview',
      'review-queue': '#/queue',
      'ambiguity-radar': '#/insights',
      'audit-history': '#/history',
      'brand-vault': '#/vault',
      'settings': '#/settings',
      'verify-certificate': '#/verify',
      'new-audit': '#/new-audit',
      'engine-status': '#/engine-status',
      'about-roadmap': '#/about',
    };
    if (hashMap[viewName] && window.location.hash !== hashMap[viewName]) {
      window.location.hash = hashMap[viewName];
    }
  }
  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    const isCurrent = btn.getAttribute('data-view') === viewName;
    btn.classList.toggle('active', isCurrent);
    if (isCurrent) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });
  document.querySelectorAll('.workspace-view').forEach((sec) => {
    sec.style.display = sec.id === `view-${viewName}` ? 'block' : 'none';
  });
  document.getElementById('topbarViewTitle').textContent =
    viewName === 'new-audit' && AppState.auditStage === 'results'
      ? 'Audit results'
      : (VIEW_TITLES[viewName] || viewName);

  if (viewName === 'overview') await refreshOverview();
  if (viewName === 'new-audit') updateRunAuditBtnState();
  if (viewName === 'new-audit') renderAuditWorkspace();
  if (viewName === 'brand-vault') await refreshBrandVault();
  if (viewName === 'review-queue') await renderReviewQueueView();
  if (viewName === 'ambiguity-radar') await renderAmbiguityRadarView();
  if (viewName === 'audit-history') await renderAuditHistoryView();
  if (viewName === 'settings') renderSettingsView();
  if (viewName === 'engine-status') await renderEngineStatusView();
  if (viewName === 'verify-certificate') await renderVerifyCertificateView();
}"""

assert old_switch_view in text
text = text.replace(old_switch_view, new_switch_view, 1)

# 6. loadBrandsAndInit: restore sessionStorage and call handleHashRouting
old_load_brands_start = """  const timeoutMs = isInitialStartup ? 90000 : 45000;"""
new_load_brands_start = """  try {
    const savedSessionStr = sessionStorage.getItem('loomshield_demo_session');
    if (savedSessionStr) {
      const saved = JSON.parse(savedSessionStr);
      if (saved && saved.token) {
        AppState.demoToken = saved.token;
        AppState.userId = saved.userId || '';
        AppState.userName = saved.userName || 'Demo User';
        AppState.userInitials = saved.userInitials || '';
        AppState.activeRole = saved.activeRole || 'Content Creator';
      }
    }
  } catch (_e) {}

  const timeoutMs = isInitialStartup ? 90000 : 45000;"""

assert old_load_brands_start in text
text = text.replace(old_load_brands_start, new_load_brands_start, 1)

old_load_brands_end = """    if (window.location.hash === '#verify') {
      await switchView('verify-certificate');
    } else if (window.location.hash === '#new-audit') {
      AppState.auditStage = 'input';
      AppState.wizardMode = false;
      await switchView('new-audit');
    } else if (window.location.hash === '#results') {
      const firstId = AppState.overviewData?.recent_audits?.[0]?.id || 'AUD-1001';
      await openAuditById(firstId);
    }"""

new_load_brands_end = """    await handleHashRouting();"""

assert old_load_brands_end in text
text = text.replace(old_load_brands_end, new_load_brands_end, 1)

# 7. openAuditById with hash update
old_open_audit = """async function openAuditById(auditId) {
  try {
    const audit = await apiFetch(`/api/audits/${encodeURIComponent(auditId)}`);
    AppState.currentAudit = audit;
    AppState.auditStage = 'results';
    AppState.selectedPillarFilter = 'ALL';
    AppState.selectedSeverityFilter = 'ALL';
    AppState.selectedStatusFilter = 'ALL';
    AppState.findingSearchQuery = '';
    AppState.selectedFindingId = null;
    await switchView('new-audit');
  } catch (err) {
    showToast(`Could not load audit ${auditId}: ${err.message}`);
  }
}"""

new_open_audit = """async function openAuditById(auditId, updateHash = true) {
  try {
    const audit = await apiFetch(`/api/audits/${encodeURIComponent(auditId)}`);
    AppState.currentAudit = audit;
    AppState.auditStage = 'results';
    AppState.selectedPillarFilter = 'ALL';
    AppState.selectedSeverityFilter = 'ALL';
    AppState.selectedStatusFilter = 'ALL';
    AppState.findingSearchQuery = '';
    AppState.selectedFindingId = null;
    if (updateHash && !isNavigatingHash) {
      window.location.hash = `#/audit/${encodeURIComponent(auditId)}`;
    }
    await switchView('new-audit', false);
  } catch (err) {
    showToast(`Could not load audit ${auditId}: ${err.message}`);
  }
}"""

assert old_open_audit in text
text = text.replace(old_open_audit, new_open_audit, 1)

# 8. runAuditBtn double-click guard
old_run_btn = """  document.getElementById('runAuditBtn').addEventListener('click', async () => {
    const fInput = document.getElementById('auditFileUpload');
    if (AppState.inputMethod === 'upload' && fInput.files && fInput.files.length > 0) {
      await executeFileUploadAudit(fInput.files[0]);
      fInput.value = '';
      const fCard = document.getElementById('uploadFileCard');
      if (fCard) fCard.style.display = 'none';
      const previewBar = document.getElementById('uploadFilePreviewBar');
      if (previewBar) previewBar.style.display = 'none';
    } else if (AppState.inputMethod === 'upload' && (!fInput.files || fInput.files.length === 0)) {
      showToast('Please select or drop a file to audit, or switch to "Paste content".');
    } else {
      await executeTextAudit();
    }
  });"""

new_run_btn = """  const runAuditBtnEl = document.getElementById('runAuditBtn');
  runAuditBtnEl.addEventListener('click', async () => {
    if (runAuditBtnEl.disabled || runAuditBtnEl.dataset.busy === '1') return;
    runAuditBtnEl.dataset.busy = '1';
    runAuditBtnEl.disabled = true;
    try {
      const fInput = document.getElementById('auditFileUpload');
      if (AppState.inputMethod === 'upload' && fInput.files && fInput.files.length > 0) {
        await executeFileUploadAudit(fInput.files[0]);
        fInput.value = '';
        const fCard = document.getElementById('uploadFileCard');
        if (fCard) fCard.style.display = 'none';
        const previewBar = document.getElementById('uploadFilePreviewBar');
        if (previewBar) previewBar.style.display = 'none';
      } else if (AppState.inputMethod === 'upload' && (!fInput.files || fInput.files.length === 0)) {
        showToast('Please select or drop a file to audit, or switch to "Paste content".');
      } else {
        await executeTextAudit();
      }
    } finally {
      runAuditBtnEl.disabled = false;
      runAuditBtnEl.dataset.busy = '0';
      updateRunAuditBtnState();
    }
  });"""

assert old_run_btn in text
text = text.replace(old_run_btn, new_run_btn, 1)

# 9. Workflow buttons double-click guard
old_wf_btns = """  // Workflow transitions
  document.querySelectorAll('#workflowTransitionBox button[data-wf]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const targetState = btn.getAttribute('data-wf');
      await transitionCurrentAuditWorkflow(targetState);
    });
  });"""

new_wf_btns = """  // Workflow transitions
  document.querySelectorAll('#workflowTransitionBox button[data-wf]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (btn.disabled || btn.dataset.busy === '1') return;
      const allBtns = document.querySelectorAll('#workflowTransitionBox button[data-wf]');
      allBtns.forEach((b) => { b.disabled = true; b.dataset.busy = '1'; });
      try {
        const targetState = btn.getAttribute('data-wf');
        await transitionCurrentAuditWorkflow(targetState);
      } finally {
        allBtns.forEach((b) => { b.disabled = false; b.dataset.busy = '0'; });
        updateWorkspaceApprovalGuard();
      }
    });
  });"""

assert old_wf_btns in text
text = text.replace(old_wf_btns, new_wf_btns, 1)

# 10. signInAsDemoUser save sessionStorage
old_demo_login_end = """    showToast(`Signed in as ${AppState.userName} (${AppState.activeRole}).`);"""
new_demo_login_end = """    try {
      sessionStorage.setItem('loomshield_demo_session', JSON.stringify({
        token: AppState.demoToken,
        userId: AppState.userId,
        userName: AppState.userName,
        userInitials: AppState.userInitials,
        activeRole: AppState.activeRole,
      }));
    } catch (_e) {}
    showToast(`Signed in as ${AppState.userName} (${AppState.activeRole}).`);"""

assert old_demo_login_end in text
text = text.replace(old_demo_login_end, new_demo_login_end, 1)

p.write_text(text, encoding="utf-8")
print("frontend/app.js updated successfully with H5 features")
