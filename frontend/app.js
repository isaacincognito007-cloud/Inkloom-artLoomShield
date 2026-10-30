function updateProcessingModeUI() {
  const title = document.getElementById('processingModeTitle');
  const helper = document.getElementById('localModeHelper');
  const badge = document.getElementById('processingModeBadge');
  const isLocal = AppState.processingMode === 'local';

  if (title && helper && badge) {
    if (isLocal) {
      title.textContent = 'Local on-device processing';
      helper.textContent = 'Processed on this device; nothing leaves your machine.';
      badge.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>On-device</span>';
      badge.className = 'status-badge badge-passed';
    } else {
      title.textContent = 'Hosted server processing';
      helper.textContent = AppState.demoMode
        ? 'Your content is sent to the LoomShield server for processing and the audit is saved to history. Demo workspace: do not submit confidential material.'
        : 'Your content is sent to the LoomShield server for processing and the audit is saved to history. This workspace has no sign-in: submitted content is stored and visible to anyone using this deployment; do not submit confidential material.';
      badge.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>Hosted server</span>';
      badge.className = 'status-badge badge-neutral';
    }
  }

  const sidebarBtn = document.getElementById('sidebarSystemStatusBtn');
  const sidebarPillText = document.getElementById('sidebarStatusPillText');
  if (sidebarBtn && sidebarPillText) {
    if (isLocal) {
      sidebarPillText.textContent = 'Local processing';
      sidebarBtn.title = 'View privacy and local processing status';
    } else {
      sidebarPillText.textContent = 'Hosted processing';
      sidebarBtn.title = 'View privacy and hosted system status';
    }
  }

  const banner = document.getElementById('demoWorkspaceBanner');
  if (banner) {
    banner.style.display = AppState.demoMode ? 'flex' : 'none';
  }

  const startHere = document.getElementById('overviewStartHereCard');
  if (startHere) {
    startHere.style.display = AppState.demoMode ? 'block' : 'none';
  }
}

/**
 * LoomShield — Brand Governance Workspace
 * Production UI Controller
 */

const LABELS = {
  pillar: 'Check area',
  pillars: 'Check areas',
  findings: 'Issues',
  finding: 'Issue',
  brandVault: 'Brand guidelines',
  terminology: 'Preferred words',
  verifiedFacts: 'Approved facts',
  visualIdentity: 'Colours and logo',
  voiceRules: 'Tone and rules',
  checkFailed: "Couldn't check",
  needsReview: 'Needs a human look',
  ambiguityRadar: 'Guideline insights',
  localProcessing: 'Local processing',
  hostedProcessing: 'Hosted engine',
};

const AppState = {
  brands: [],
  activeBrandId: '',
  activeView: 'overview',
  auditStage: 'input', // 'input' | 'results'
  activeMobilePanel: 'source', // 'source' | 'findings' | 'correction'
  session: null,
  userId: '',
  userName: '',
  userInitials: '',
  demoToken: '',
  demoUsers: [],
  activeRole: 'Content Creator',
  demoMode: false,
  processingMode: 'hosted',
  sessionAvailable: true,
  firstLoadSuccess: false,
  permissions: {},
  inputMethod: 'paste', // 'paste' | 'upload'
  hasUnsavedChanges: false,

  // Guided wizard state (Slice 1 headline flow)
  wizardMode: true,
  wizardStep: 1,
  wizardAnswers: {
    content_type: 'webpage',
    industry: 'general',
    occasion: 'everyday',
    locale: 'global',
    tone: 'professional',
    company_name: '',
    never_use_words: '',
  },
  wizardOptions: null,
  wizardPreview: null,
  wizardSampleText: '',

  // Overview state
  overviewData: null,
  overviewStatusFilter: 'ALL',

  // View refresh tracking & errors
  lastRefreshed: {
    overview: null,
    vault: null,
    reviewQueue: null,
    radar: null,
    history: null,
    engineStatus: null,
  },
  vaultError: null,
  reviewQueueOffset: 0,

  // Audit Results state
  currentAudit: null,
  selectedFindingId: null,
  selectedPillarFilter: 'ALL',
  selectedSeverityFilter: 'ALL',
  selectedStatusFilter: 'ALL',
  findingSearchQuery: '',
  sourceViewMode: 'working', // 'working' | 'original'
  sourceFormatView: 'rendered', // 'rendered' | 'source'

  // Brand Vault state
  activeVaultTab: 'voice',
  vaultSearchQuery: '',
  vaultSearchScope: 'tab', // 'tab' | 'all'
  vaultData: null,
  vaultFormOpen: {
    rule: false,
    term: false,
    fact: false,
    color: false,
  },

  // Review Queue & Audit History state
  reviewQueueFilter: 'ALL',
  reviewQueueSearch: '',
  auditsList: [],
  selectedHistoryAuditId: null,
  historyFormatView: 'rendered', // 'rendered' | 'source'

  // System Status state
  engineStatus: null,
};

const SIX_PILLARS = [
  'Tone and Voice',
  'Terminology',
  'Messaging',
  'Promotional Claims',
  'Visual and Logo Consistency',
  'Accessibility',
];

const VIEW_TITLES = {
  'overview': 'Overview',
  'new-audit': 'New audit',
  'brand-vault': 'Brand guidelines',
  'review-queue': 'Review queue',
  'ambiguity-radar': 'Guideline insights',
  'audit-history': 'Audit history',
  'settings': 'Settings',
  'engine-status': 'Privacy and system status',
  'verify-certificate': 'Verify certificate',
  'about-roadmap': 'About & roadmap',
};

// ============================================================================
// UTILITIES, SAFE HTML SANITISATION & INLINE WORD DIFF
// ============================================================================

function escapeHtml(val) {
  if (val === null || val === undefined) return '';
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatTimestamp(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return String(isoStr);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getActiveBrandDisplayName() {
  const found = (AppState.brands || []).find((b) => b.id === AppState.activeBrandId);
  if (found) return `${found.name} · v${found.version}`;
  if (AppState.vaultData && AppState.vaultData.brand) {
    return `${AppState.vaultData.brand.name} · v${AppState.vaultData.brand.version}`;
  }
  return AppState.activeBrandId;
}

function showToast(message) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast-msg';
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 4000);
}

function setUnsavedVaultChanges(hasChanges) {
  AppState.hasUnsavedChanges = Boolean(hasChanges);
  const badge = document.getElementById('vaultUnsavedBadge');
  if (badge) {
    badge.style.display = hasChanges ? 'inline-flex' : 'none';
  }
}

function confirmDiscardUnsavedChanges() {
  if (!AppState.hasUnsavedChanges) return true;
  const ok = window.confirm('You have unsaved edits on this screen. Discard changes and continue?');
  if (ok) {
    setUnsavedVaultChanges(false);
  }
  return ok;
}

function normalizeStatusDisplay(rawState) {
  const s = String(rawState || 'Draft');
  const map = {
    'Passed': 'Passed',
    'Not Checked': 'Not checked',
    'Needs Review': LABELS.needsReview || 'Needs a human look',
    'needs_review': LABELS.needsReview || 'Needs a human look',
    'Check Failed': LABELS.checkFailed || "Couldn't check",
    'Findings': 'Issues found',
    'open': 'Open',
    'accepted': 'Accepted',
    'modified': 'Modified',
    'dismissed': 'Dismissed',
    'In Review': 'In review',
    'Changes Requested': 'Changes requested',
  };
  return map[s] || s;
}

function renderStateBadge(state) {
  const raw = String(state || 'Draft');
  const display = normalizeStatusDisplay(raw);
  const lower = raw.toLowerCase();
  let cls = 'badge-neutral';
  let icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><circle cx="12" cy="12" r="9"/></svg>';

  if (['passed', 'approved', 'verified', 'accepted', 'modified', 'available', 'self-test passed', 'on'].includes(lower)) {
    cls = 'badge-passed';
    icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
  } else if (['findings', 'check failed', 'failed', 'error', 'changes requested', 'open', 'high', 'critical'].includes(lower)) {
    cls = 'badge-error';
    icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  } else if (['needs review', 'needs_review', 'in review', 'revised', 'pending verification', 'medium', 'recommended for review', 'monitor'].includes(lower)) {
    cls = 'badge-warning';
    icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  } else if (['not checked', 'draft', 'dismissed', 'archived', 'low', 'no action needed', 'disabled / not configured', 'unavailable'].includes(lower)) {
    cls = 'badge-neutral';
    icon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="5" y1="12" x2="19" y2="12"/></svg>';
  }

  return `<span class="status-badge ${cls}">${icon}<span>${escapeHtml(display)}</span></span>`;
}

/**
 * Safe Formatted Document Renderer (Strips raw HTML/Markdown syntax into clean semantic blocks
 * while preserving exact character-offset highlight spans!)
 */

function updateRunAuditBtnState() {
  const runBtn = document.getElementById('runAuditBtn');
  const textArea = document.getElementById('auditContentText');
  const fileInput = document.getElementById('auditFileUpload');
  if (!runBtn) return;
  const hasText = Boolean(textArea && textArea.value.trim().length > 0);
  const hasFile = Boolean(fileInput && fileInput.files && fileInput.files.length > 0);
  const isValid = AppState.inputMethod === 'upload' ? hasFile : hasText;
  runBtn.disabled = !isValid;
  runBtn.title = isValid ? 'Run compliance audit' : 'Add document content or upload a file to run audit';
}

function renderSafeDocumentHtml(rawText, highlightFindings, selectedFindingId, formatMode) {
  const text = String(rawText || '');
  const validFindings = (highlightFindings || [])
    .filter((f) => f.start_index >= 0 && f.end_index > f.start_index && f.end_index <= text.length)
    .sort((a, b) => a.start_index - b.start_index || (a.end_index - a.start_index) - (b.end_index - b.start_index));

  // Build non-overlapping segments
  const segments = [];
  let cursor = 0;
  for (const f of validFindings) {
    if (f.start_index < cursor) continue;
    if (f.start_index > cursor) {
      segments.push({ text: text.slice(cursor, f.start_index), finding: null });
    }
    segments.push({ text: text.slice(f.start_index, f.end_index), finding: f });
    cursor = f.end_index;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), finding: null });
  }

  // Raw source mode: monospace escaped text with highlights
  if (formatMode === 'source') {
    return segments
      .map((seg) => {
        if (!seg.finding) return escapeHtml(seg.text);
        const f = seg.finding;
        const isSel = f.id === selectedFindingId;
        const sevCls = `severity-${f.severity} state-${f.review_state} ${isSel ? 'selected-span' : ''}`;
        return `<mark class="source-highlight ${sevCls}" data-finding-id="${escapeHtml(f.id)}" title="${escapeHtml(f.issue_type)} (${escapeHtml(f.rule_or_fact_id)})">${escapeHtml(seg.text)}</mark>`;
      })
      .join('');
  }

  // Rendered mode: safely strip HTML tags & Markdown hashes while preserving highlight marks
  function sanitizeSegmentText(str) {
    // Replace block closing tags with double newline markers before escaping
    const withBreaks = str
      .replace(/<\/\s*(?:h[1-6]|p|div|li|blockquote)\s*>/gi, '\n\n')
      .replace(/<\s*br\s*\/?>/gi, '\n')
      .replace(/<\s*h1[^>]*>/gi, '[[H1]]')
      .replace(/<\s*h2[^>]*>/gi, '[[H2]]')
      .replace(/<\s*(?:h3|h4|h5|h6)[^>]*>/gi, '[[H3]]')
      .replace(/<\s*li[^>]*>/gi, '• ')
      .replace(/<[^>]+>/g, '');
    return escapeHtml(withBreaks);
  }

  const combinedSafe = segments
    .map((seg) => {
      const cleaned = sanitizeSegmentText(seg.text);
      if (!seg.finding) return cleaned;
      const f = seg.finding;
      const isSel = f.id === selectedFindingId;
      const sevCls = `severity-${f.severity} state-${f.review_state} ${isSel ? 'selected-span' : ''}`;
      return `<mark class="source-highlight ${sevCls}" data-finding-id="${escapeHtml(f.id)}" title="${escapeHtml(f.issue_type)} (${escapeHtml(f.rule_or_fact_id)})">${cleaned}</mark>`;
    })
    .join('');

  const blocks = combinedSafe
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);

  if (blocks.length === 0) {
    return '<div class="rendered-doc-block"><em>No text content</em></div>';
  }

  return blocks
    .map((blk) => {
      let contentHtml = blk;
      let cls = 'rendered-doc-block';
      if (contentHtml.startsWith('[[H1]]')) {
        contentHtml = contentHtml.replace('[[H1]]', '').trim();
        cls += ' rendered-doc-h1';
      } else if (contentHtml.startsWith('[[H2]]')) {
        contentHtml = contentHtml.replace('[[H2]]', '').trim();
        cls += ' rendered-doc-h2';
      } else if (contentHtml.startsWith('[[H3]]')) {
        contentHtml = contentHtml.replace('[[H3]]', '').trim();
        cls += ' rendered-doc-h3';
      } else if (/^#{1,6}\s+/.test(contentHtml)) {
        const m = contentHtml.match(/^(#{1,6})\s+(.*)$/s);
        if (m) {
          const lvl = m[1].length;
          contentHtml = m[2].trim();
          cls += lvl === 1 ? ' rendered-doc-h1' : (lvl === 2 ? ' rendered-doc-h2' : ' rendered-doc-h3');
        }
      }
      contentHtml = contentHtml.replace(/\[\[H[123]\]\]/g, '');
      return `<div class="${cls}">${contentHtml}</div>`;
    })
    .join('');
}

/**
 * Word-Level Inline Diff Generator (<del class="diff-del"> and <ins class="diff-ins">)
 */
function computeWordDiffHtml(oldStr, newStr, formatMode = 'rendered') {
  const cleanForDiff = (s) => {
    const str = String(s || '');
    if (formatMode === 'source') return str;
    return str
      .replace(/<\/\s*(?:h[1-6]|p|div|li)\s*>/gi, '\n')
      .replace(/<[^>]+>/g, '')
      .replace(/^#{1,6}\s+/gm, '')
      .trim();
  };

  const aText = cleanForDiff(oldStr);
  const bText = cleanForDiff(newStr);
  if (aText === bText) {
    return escapeHtml(bText);
  }

  const aTokens = aText.split(/(\s+)/);
  const bTokens = bText.split(/(\s+)/);

  // LCS matrix for word tokens
  const m = aTokens.length;
  const n = bTokens.length;
  if (m * n > 250000) {
    return `<del class="diff-del">${escapeHtml(aText)}</del> <ins class="diff-ins">${escapeHtml(bText)}</ins>`;
  }

  const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (aTokens[i] === bTokens[j]) {
        dp[i][j] = 1 + dp[i + 1][j + 1];
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  let i = 0;
  let j = 0;
  const out = [];
  while (i < m && j < n) {
    if (aTokens[i] === bTokens[j]) {
      out.push(escapeHtml(aTokens[i]));
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      if (aTokens[i].trim()) {
        out.push(`<del class="diff-del">${escapeHtml(aTokens[i])}</del>`);
      } else {
        out.push(escapeHtml(aTokens[i]));
      }
      i++;
    } else {
      if (bTokens[j].trim()) {
        out.push(`<ins class="diff-ins">${escapeHtml(bTokens[j])}</ins>`);
      } else {
        out.push(escapeHtml(bTokens[j]));
      }
      j++;
    }
  }
  while (i < m) {
    if (aTokens[i].trim()) out.push(`<del class="diff-del">${escapeHtml(aTokens[i])}</del>`);
    else out.push(escapeHtml(aTokens[i]));
    i++;
  }
  while (j < n) {
    if (bTokens[j].trim()) out.push(`<ins class="diff-ins">${escapeHtml(bTokens[j])}</ins>`);
    else out.push(escapeHtml(bTokens[j]));
    j++;
  }
  return out.join('');
}

class ApiError extends Error {
  constructor(status, code, message, field = null, requestId = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.field = field;
    this.requestId = requestId;
  }
}

async function apiFetch(url, options = {}, timeoutMs = 45000) {
  const headers = Object.assign({}, options.headers || {});
  if (AppState.demoToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${AppState.demoToken}`;
  } else if (AppState.activeRole && !headers['x-loomshield-role']) {
    headers['x-loomshield-role'] = AppState.activeRole;
  }

  const isColdStartEndpoint = url.startsWith('/api/session') || url.startsWith('/api/brands');
  const effectiveTimeout = (isColdStartEndpoint && !AppState.firstLoadSuccess) ? 90000 : timeoutMs;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), effectiveTimeout);

  const opts = Object.assign({}, options, {
    headers,
    signal: options.signal || controller.signal,
  });

  let res;
  try {
    res = await fetch(url, opts);
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError(0, 'TIMEOUT', `Request timed out after ${Math.round(effectiveTimeout / 1000)} seconds. Please try again.`);
    }
    throw new ApiError(0, 'NETWORK_ERROR', 'Network connection error. Please verify the LoomShield server is running.');
  } finally {
    clearTimeout(timeoutId);
  }

  let data = null;
  try {
    data = await res.json();
  } catch (_e) {
    data = null;
  }

  if (!res.ok) {
    if (res.status === 401 && AppState.demoToken) {
      AppState.demoToken = '';
      AppState.userId = '';
      AppState.userName = 'Sample workspace user';
      AppState.userInitials = 'SW';
      AppState.activeRole = (AppState.session && AppState.session.configured_role) || 'Content Creator';
      try { sessionStorage.removeItem('loomshield_demo_session'); } catch (_e) {}
      updateTopbarContext();
      if (AppState.activeView === 'new-audit' && AppState.auditStage === 'results') {
        updateWorkspaceApprovalGuard();
      } else if (AppState.activeView === 'settings' && typeof renderSettingsView === 'function') {
        renderSettingsView();
      }
      showToast('Your demo session expired. Sign in again.');
    }
    const errObj = data && data.error ? data.error : {};
    const code = errObj.code || `HTTP_${res.status}`;
    const field = errObj.field || null;
    const reqId = errObj.request_id || res.headers.get('x-request-id') || null;
    let message = errObj.message;
    if (!message) {
      if (typeof data?.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
        message = data.detail[0].msg || JSON.stringify(data.detail);
      } else {
        message = `Request failed (${res.status})`;
      }
    }
    throw new ApiError(res.status, code, message, field, reqId);
  }

  if (isColdStartEndpoint) {
    AppState.firstLoadSuccess = true;
  }

  return data;
}

function getApiErrorAction(err) {
  if (!err) {
    return { action: 'none', label: 'Action failed', canRetry: false, helperText: '', requestId: null };
  }
  const status = typeof err === 'object' ? (err.status || 0) : 0;
  const code = typeof err === 'object' ? (err.code || '') : '';
  const field = typeof err === 'object' ? (err.field || null) : null;
  const reqId = typeof err === 'object' ? (err.requestId || null) : null;

  if (status === 422 || code === 'VALIDATION_ERROR') {
    return {
      action: 'fix_field',
      label: 'Check input format',
      canRetry: false,
      helperText: field ? `Please correct field "${field}".` : 'Please check required fields and data format.',
      requestId: reqId,
    };
  }
  if (status === 403 || code === 'PERMISSION_DENIED') {
    return {
      action: 'ask_admin',
      label: 'Permission required',
      canRetry: false,
      helperText: 'Your current role is not authorized for this action. Contact a Brand Administrator.',
      requestId: reqId,
    };
  }
  if (status === 409 || code === 'CONFLICT') {
    const msg = (err.message || '').toLowerCase();
    let helper = 'Conflict: please refresh the workspace to view the latest status.';
    if (msg.includes('concurren')) {
      helper = 'Document or rule state changed concurrently. Refresh to view latest status.';
    } else if (msg.includes('identical')) {
      helper = 'The suggested replacement is identical to the current document content.';
    } else if (msg.includes('approved') || msg.includes('locked')) {
      helper = 'Approved audits are locked for compliance integrity and cannot be modified.';
    } else if (msg.includes('transition')) {
      helper = 'This workflow transition is not permitted in the current stage.';
    } else if (msg.includes('relocate') || msg.includes('ambiguous')) {
      helper = 'Document content has shifted. Please rerun the audit or dismiss this finding.';
    }
    return {
      action: 'refresh',
      label: 'Conflict / State changed',
      canRetry: true,
      retryLabel: 'Refresh',
      helperText: helper,
      requestId: reqId,
    };
  }
  if (status === 429 || code === 'RATE_LIMITED') {
    return {
      action: 'retry',
      label: 'Rate limited',
      canRetry: true,
      retryLabel: 'Retry',
      helperText: 'Too many requests. Please wait a moment before trying again.',
      requestId: reqId,
    };
  }
  if (status === 0 || status >= 500 || code === 'TIMEOUT' || code === 'NETWORK_ERROR') {
    return {
      action: 'retry',
      label: 'Connection / Server issue',
      canRetry: true,
      retryLabel: 'Retry',
      helperText: 'Network connection or server problem. Retrying may succeed.',
      requestId: reqId,
    };
  }
  return {
    action: 'none',
    label: 'Action failed',
    canRetry: false,
    helperText: '',
    requestId: reqId,
  };
}

function openModalDialog({ title, bodyHtml, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel }) {
  document.getElementById('appSidebar')?.classList.remove('mobile-open');
  const signInMenu = document.getElementById('demoSignInMenu');
  if (signInMenu) signInMenu.style.display = 'none';
  const root = document.getElementById('modalRoot');
  root.style.display = 'block';
  root.innerHTML = `
    <div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modalDialogTitle">
      <div class="modal-card">
        <h2 id="modalDialogTitle" style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">${escapeHtml(title)}</h2>
        <div style="font-size: 13.5px; color: var(--text-secondary); margin-bottom: 18px; line-height: 1.55;">
          ${bodyHtml}
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button type="button" class="btn" id="modalCancelBtn">${escapeHtml(cancelLabel)}</button>
          <button type="button" class="btn btn-accent" id="modalConfirmBtn">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>
    </div>
  `;

  const close = () => {
    root.style.display = 'none';
    root.innerHTML = '';
  };

  document.getElementById('modalCancelBtn').addEventListener('click', () => {
    close();
    if (onCancel) onCancel();
  });

  document.getElementById('modalConfirmBtn').addEventListener('click', async () => {
    if (onConfirm) {
      const shouldClose = await onConfirm();
      if (shouldClose !== false) close();
    } else {
      close();
    }
  });
}

function showInlineError(containerEl, errOrMessage, onRetry = null) {
  if (!containerEl) return;
  const isErr = errOrMessage instanceof Error || (typeof errOrMessage === 'object' && errOrMessage !== null && errOrMessage.message);
  const message = isErr ? errOrMessage.message : String(errOrMessage);
  const actionInfo = isErr ? getApiErrorAction(errOrMessage) : { canRetry: Boolean(onRetry), retryLabel: 'Retry', helperText: '', requestId: null };
  const showRetry = Boolean(onRetry && actionInfo.canRetry);
  const retryBtnLabel = actionInfo.retryLabel || 'Retry';
  const reqId = actionInfo.requestId || (errOrMessage && errOrMessage.requestId) || null;

  containerEl.style.display = 'block';
  containerEl.innerHTML = `
    <div class="inline-error-banner" style="background: #FEF3F2; border: 1px solid #FECDCA; border-radius: 6px; padding: 10px 14px; display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; font-size: 13px; color: #B42318;">
      <div style="display: flex; gap: 8px; align-items: flex-start;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <div>
          <div style="font-weight: 600;">${escapeHtml(actionInfo.label || 'Action failed')}</div>
          <div style="color: #475467; margin-top: 2px;">${escapeHtml(message)}</div>
          ${actionInfo.helperText ? `<div style="font-size: 12px; color: #B42318; margin-top: 3px;">${escapeHtml(actionInfo.helperText)}</div>` : ''}
          ${reqId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(reqId)}</div>` : ''}
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
        ${showRetry ? `<button type="button" class="btn btn-sm inline-retry-btn" style="background: #fff; border-color: #FDA29B; color: #B42318; font-size: 12px; padding: 3px 8px;">${escapeHtml(retryBtnLabel)}</button>` : ''}
        <button type="button" class="inline-dismiss-btn" aria-label="Dismiss error" style="background: transparent; border: none; color: #98A2B3; font-size: 18px; cursor: pointer; padding: 0 4px; line-height: 1;">&times;</button>
      </div>
    </div>
  `;
  const dismissBtn = containerEl.querySelector('.inline-dismiss-btn');
  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      clearInlineError(containerEl);
    });
  }
  const retryBtn = containerEl.querySelector('.inline-retry-btn');
  if (retryBtn && onRetry) {
    retryBtn.addEventListener('click', () => {
      clearInlineError(containerEl);
      onRetry();
    });
  }
}

function clearInlineError(containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = '';
  containerEl.style.display = 'none';
}

// ============================================================================
// INITIALIZATION & NAVIGATION
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  bindNavigationEvents();
  bindAuditWorkspaceEvents();
  bindBrandVaultEvents();
  await loadBrandsAndInit();
});

function updateTopbarContext() {
  const pill = document.getElementById('topbarBrandContextPill');
  if (pill) {
    pill.innerHTML = `Brand: <strong>${escapeHtml(getActiveBrandDisplayName())}</strong>`;
  }
  const roleLbl = document.getElementById('accountRoleLabel');
  if (roleLbl) {
    roleLbl.textContent = AppState.activeRole;
  }
  const roleBtn = document.getElementById('accountRoleBtn');
  if (roleBtn) {
    const initials = AppState.userInitials || (AppState.userName || 'Workspace User')
      .split(' ')
      .filter(Boolean)
      .map((w) => w[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
    roleBtn.innerHTML = `
      <span class="user-avatar-initials">${escapeHtml(initials)}</span>
      <span style="font-weight: 600;" id="topbarSignedInUserName">${escapeHtml(AppState.userName || 'Workspace User')}</span>
      <span class="role-pill-badge" id="accountRoleLabel">${escapeHtml(AppState.activeRole)}</span>
    `;
    roleBtn.setAttribute('title', `Sign in as demo user — Currently ${AppState.userName || 'Workspace User'} (${AppState.activeRole})`);
  }
  renderDemoSignInMenu();
  const demoBanner = document.getElementById('demoWorkspaceBanner');
  if (demoBanner) {
    demoBanner.style.display = AppState.demoMode ? 'flex' : 'none';
  }
  const tryDemoBtn = document.getElementById('overviewTryDemoBtn');
  if (tryDemoBtn) {
    tryDemoBtn.style.display = AppState.demoMode ? 'inline-flex' : 'none';
  }
}

function bindNavigationEvents() {
  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-view');
      if (view === 'new-audit') {
        AppState.auditStage = 'input';
      }
      switchView(view);
      document.getElementById('appSidebar').classList.remove('mobile-open');
    });
  });

  document.getElementById('mobileMenuBtn').addEventListener('click', () => {
    document.getElementById('appSidebar').classList.toggle('mobile-open');
  });

  document.getElementById('sidebarNewAuditBtn').addEventListener('click', () => {
    AppState.auditStage = 'input';
    switchView('new-audit');
  });

  document.getElementById('sidebarSystemStatusBtn').addEventListener('click', () => {
    switchView('engine-status');
  });

  document.getElementById('accountRoleBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    if (!AppState.demoMode) {
      switchView('settings');
      return;
    }
    const menu = document.getElementById('demoSignInMenu');
    const btn = document.getElementById('accountRoleBtn');
    if (!menu) {
      switchView('settings');
      return;
    }
    const isOpening = menu.style.display === 'none' || !menu.style.display;
    if (isOpening) {
      document.getElementById('appSidebar')?.classList.remove('mobile-open');
      const cp = document.getElementById('commandPaletteModal');
      if (cp) cp.style.display = 'none';
      const mr = document.getElementById('modalRoot');
      if (mr) mr.style.display = 'none';
      renderDemoSignInMenu();
      menu.style.display = 'block';
      btn?.setAttribute('aria-expanded', 'true');
    } else {
      menu.style.display = 'none';
      btn?.setAttribute('aria-expanded', 'false');
    }
  });

  document.getElementById('openSettingsFromSignInMenuBtn')?.addEventListener('click', () => {
    const menu = document.getElementById('demoSignInMenu');
    if (menu) menu.style.display = 'none';
    switchView('settings');
  });

  document.addEventListener('click', (e) => {
    const wrap = document.getElementById('signInDropdownWrap');
    const menu = document.getElementById('demoSignInMenu');
    if (menu && menu.style.display !== 'none' && wrap && !wrap.contains(e.target)) {
      menu.style.display = 'none';
      document.getElementById('accountRoleBtn')?.setAttribute('aria-expanded', 'false');
    }
  });

  const resultsCertBtn = document.getElementById('resultsCertificateBtn');
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
  }

  window.addEventListener('hashchange', async () => {
    await handleHashRouting();
  });

  document.getElementById('overviewNewAuditBtn').addEventListener('click', () => {
    AppState.auditStage = 'input';
    AppState.wizardMode = true;
    AppState.wizardStep = 1;
    switchView('new-audit');
  });

  document.getElementById('overviewTryDemoBtn')?.addEventListener('click', () => {
    AppState.auditStage = 'input';
    AppState.wizardMode = true;
    AppState.wizardStep = 8;
    switchView('new-audit');
  });

  const heroBtn = document.getElementById('heroStartAuditBtn');
  if (heroBtn) {
    heroBtn.addEventListener('click', () => {
      AppState.auditStage = 'input';
      AppState.wizardMode = true;
      AppState.wizardStep = 1;
      switchView('new-audit');
    });
  }

  const step1Btn = document.getElementById('walkthroughStep1Btn');
  const step2Btn = document.getElementById('walkthroughStep2Btn');
  const step3Btn = document.getElementById('walkthroughStep3Btn');

  if (step1Btn) {
    step1Btn.addEventListener('click', () => {
      AppState.auditStage = 'input';
      AppState.wizardMode = true;
      AppState.wizardStep = 1;
      switchView('new-audit');
    });
  }

  if (step2Btn) {
    step2Btn.addEventListener('click', () => {
      AppState.auditStage = 'input';
      AppState.wizardMode = true;
      AppState.wizardStep = 8;
      switchView('new-audit');
    });
  }

  if (step3Btn) {
    step3Btn.addEventListener('click', async () => {
      try {
        await openAuditById('AUD-1001');
      } catch (e) {
        switchView('review-queue');
      }
    });
  }

  document.getElementById('demoSampleSelector').addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    if (val) {
      AppState.auditStage = 'input';
      switchView('new-audit');
      loadSamplePreset(val);
      e.target.value = '';
    }
  });

  document.getElementById('resetDemoBtn')?.addEventListener('click', () => {
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
  });

  document.querySelectorAll('#overviewStatusFilters .filter-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      AppState.overviewStatusFilter = pill.getAttribute('data-ov-filter');
      document.querySelectorAll('#overviewStatusFilters .filter-pill').forEach((p) => {
        p.classList.toggle('active', p === pill);
      });
      renderRecentAuditsTable();
    });
  });

  document.getElementById('brandSelector').addEventListener('change', async (e) => {
    if (!confirmDiscardUnsavedChanges()) {
      e.target.value = AppState.activeBrandId;
      return;
    }
    AppState.activeBrandId = e.target.value;
    AppState.currentAudit = null;
    AppState.selectedFindingId = null;
    AppState.vaultData = null;
    AppState.overviewData = null;
    AppState.reviewQueueOffset = 0;
    AppState.lastRefreshed = {
      overview: null,
      vault: null,
      reviewQueue: null,
      radar: null,
      history: null,
      engineStatus: null,
    };
    try {
      await refreshAllBrandData();
      updateTopbarContext();
      const displayBrand = getActiveBrandDisplayName();
      showToast(`${displayBrand} selected`);
    } catch (err) {
      showToast(`Failed to switch brand: ${err.message}`);
    }
  });

  // Clickable metric cards (Task 4)
  const cardDocs = document.getElementById('metricCardDocs');
  if (cardDocs) cardDocs.addEventListener('click', () => setOverviewFilter('ALL'));
  const cardFindings = document.getElementById('metricCardFindings');
  if (cardFindings) cardFindings.addEventListener('click', () => setOverviewFilter('In Review'));
  const cardApproved = document.getElementById('metricCardApproved');
  if (cardApproved) cardApproved.addEventListener('click', () => setOverviewFilter('Approved'));
  const cardRules = document.getElementById('metricCardRules');
  if (cardRules) cardRules.addEventListener('click', () => switchView('brand-vault'));

  // Mobile drawer close on nav item click
  document.querySelectorAll('.sidebar-nav .nav-item').forEach((item) => {
    item.addEventListener('click', () => {
      document.getElementById('appSidebar')?.classList.remove('mobile-open');
    });
  });

  // Global copy-to-clipboard chip handler (Task 3)
  document.addEventListener('click', (e) => {
    const chip = e.target.closest('.copy-id-chip');
    if (chip) {
      e.stopPropagation();
      const text = chip.getAttribute('data-copy-text');
      if (text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(() => {
            showToast(`Copied ${text} to clipboard`);
          }).catch(() => {
            showToast(`Copied: ${text}`);
          });
        } else {
          showToast(`Copied: ${text}`);
        }
      }
    }
  });

  // Global keyboard shortcuts for Results screen (Task 6)
  window.addEventListener('keydown', handleResultsKeyNavigation);

  // Initialize command palette (Task 7)
  initCommandPalette();

    const runSelfTestBtn = document.getElementById('runEngineSelftestHeaderBtn');
  if (runSelfTestBtn) {
    runSelfTestBtn.addEventListener('click', async () => {
      await triggerEngineSelftest();
    });
  }
}

let isNavigatingHash = false;

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
      if (AppState.wizardMode !== true) {
        AppState.wizardMode = false;
      }
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
      isNavigatingHash = true;
      window.location.hash = hashMap[viewName];
      setTimeout(() => { isNavigatingHash = false; }, 50);
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
}

let isInitialStartup = true;

async function loadBrandsAndInit() {
  const sessionBanner = document.getElementById('sessionUnavailableBanner');
  const sessionText = document.getElementById('sessionUnavailableText');
  const sessionRetryBtn = document.getElementById('sessionRetryBtn');
  if (sessionRetryBtn && !sessionRetryBtn._bound) {
    sessionRetryBtn._bound = true;
    sessionRetryBtn.addEventListener('click', async () => {
      await loadBrandsAndInit();
    });
  }

  try {
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

  const timeoutMs = isInitialStartup ? 90000 : 45000;
  if (isInitialStartup && sessionBanner && sessionText) {
    sessionText.textContent = 'Waking the server (may take up to 90 seconds on free cloud instances)...';
    sessionBanner.style.display = 'flex';
    sessionBanner.style.background = '#EFF8FF';
    sessionBanner.style.color = '#175CD3';
    sessionBanner.style.borderColor = '#B2DDFF';
  }

  try {
    try {
      const sessionData = await apiFetch('/api/session', {}, timeoutMs);
      if (sessionData) {
        AppState.session = sessionData;
        AppState.demoMode = Boolean(sessionData.is_demo_mode);
        AppState.processingMode = sessionData.processing_mode || 'hosted';
        AppState.userId = sessionData.user_id || '';
        AppState.activeRole = sessionData.user_role || 'Content Creator';
        AppState.userName = sessionData.user_name || 'Workspace User';
        AppState.userInitials = sessionData.user_initials || '';
        AppState.demoUsers = sessionData.demo_users || [];
        AppState.permissions = sessionData.permissions || {};
        AppState.sessionAvailable = true;
        if (sessionBanner) sessionBanner.style.display = 'none';
      }
    } catch (_e) {
      AppState.sessionAvailable = false;
      if (sessionBanner && sessionText) {
        sessionBanner.style.background = '#FEF3F2';
        sessionBanner.style.color = '#B42318';
        sessionBanner.style.borderColor = '#FECDCA';
        sessionText.textContent = 'Cannot connect to LoomShield server. Audits and write actions are temporarily disabled.';
        sessionBanner.style.display = 'flex';
      }
      showToast('Session unavailable: operating in offline/degraded mode with write actions restricted.');
    }
    updateProcessingModeUI();

    const res = await apiFetch('/api/brands', {}, timeoutMs);
    isInitialStartup = false;
    AppState.brands = res.brands || [];
    const sel = document.getElementById('brandSelector');
    sel.innerHTML = AppState.brands
      .map((b) => `<option value="${escapeHtml(b.id)}">${escapeHtml(b.name)} (v${b.version})</option>`)
      .join('');
    if (AppState.brands.length > 0) {
      if (!AppState.brands.some((b) => b.id === AppState.activeBrandId)) {
        AppState.activeBrandId = AppState.brands[0].id;
      }
      sel.value = AppState.activeBrandId;
    }
    await refreshAllBrandData();
    updateTopbarContext();
    await handleHashRouting();
  } catch (err) {
    isInitialStartup = false;
    showToast(`Failed to initialize workspace: ${err.message}`);
  }
}

async function refreshAllBrandData() {
  await Promise.allSettled([
    refreshOverview(),
    refreshBrandVaultDataOnly(),
  ]);
  updateTopbarContext();
  if (AppState.activeView === 'brand-vault') renderBrandVaultTab();
  if (AppState.activeView === 'review-queue') await renderReviewQueueView();
  if (AppState.activeView === 'ambiguity-radar') await renderAmbiguityRadarView();
  if (AppState.activeView === 'audit-history') await renderAuditHistoryView();
}

// ============================================================================
// VIEW 1: OVERVIEW (SECTION 03)
// ============================================================================

async function refreshOverview() {
  const container = document.getElementById('recentAuditsContainer');
  if (container && !AppState.overviewData) {
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">
        Loading overview metrics...
      </div>
    `;
  }
  try {
    const data = await apiFetch(`/api/overview/${encodeURIComponent(AppState.activeBrandId)}`);
    AppState.overviewData = data;
    AppState.lastRefreshed.overview = new Date().toISOString();

    document.getElementById('metricDocsAudited').textContent = data.metrics.documents_audited;
    document.getElementById('metricOpenFindings').textContent = data.metrics.findings_requiring_attention;
    document.getElementById('metricApprovedContent').textContent = data.metrics.approved_content;
    document.getElementById('metricBrandRules').textContent = data.metrics.brand_rules;

    const brandScopeText = `${data.brand_name} · v${data.brand_version || 1}${data.is_demo ? ' (Demo profile)' : ''}`;
    document.getElementById('overviewScopeSubtitle').textContent =
      `Compliance metrics and audit records scoped to ${brandScopeText}.`;
    document.getElementById('metricDocsScopeNote').textContent = `Scoped to ${data.brand_name}`;
    document.getElementById('overviewLastUpdatedText').textContent =
      `Last updated: ${formatTimestamp(AppState.lastRefreshed.overview)}`;

    document.getElementById('navRulesCount').textContent = data.metrics.brand_rules;
    const queueCount = (data.recent_audits || []).filter((a) => a.overall_status !== 'Approved').length;
    document.getElementById('navQueueCount').textContent = queueCount;

    renderRecentAuditsTable();
  } catch (err) {
    AppState.overviewData = null;
    document.getElementById('metricDocsAudited').textContent = '—';
    document.getElementById('metricOpenFindings').textContent = '—';
    document.getElementById('metricApprovedContent').textContent = '—';
    document.getElementById('metricBrandRules').textContent = '—';
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.overview ? formatTimestamp(AppState.lastRefreshed.overview) : 'Never';
    if (container) {
      container.innerHTML = `
        <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
          <h3 style="color: #B42318;">Could not retrieve dashboard metrics</h3>
          <p style="color: #475467;">${escapeHtml(err.message)}</p>
          ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
          ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
          <button type="button" class="btn btn-sm btn-accent" id="retryOverviewBtn" style="margin-top: 12px;">Retry</button>
        </div>
      `;
      const retryBtn = document.getElementById('retryOverviewBtn');
      if (retryBtn) retryBtn.addEventListener('click', () => refreshOverview());
    }
  }
}

function setOverviewFilter(filterName) {
  AppState.overviewStatusFilter = filterName;
  document.querySelectorAll('#overviewStatusFilters .filter-pill').forEach((p) => {
    p.classList.toggle('active', p.getAttribute('data-ov-filter') === filterName);
  });
  renderRecentAuditsTable();
  const table = document.getElementById('recentAuditsContainer');
  if (table) {
    table.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function renderRecentAuditsTable() {
  const container = document.getElementById('recentAuditsContainer');
  if (!container || !AppState.overviewData) return;

  const allAudits = AppState.overviewData.recent_audits || [];
  const filtered = AppState.overviewStatusFilter === 'ALL'
    ? allAudits
    : allAudits.filter((a) => a.overall_status === AppState.overviewStatusFilter);

  if (allAudits.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <h3>No audits recorded for this brand yet</h3>
        <p>Run your first audit to check draft copy or visual assets against ${escapeHtml(AppState.overviewData.brand_name)} rules.</p>
        <div style="display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;">
          <button type="button" class="btn btn-accent" id="emptyStateStartAuditBtn">Start your first audit</button>
          ${AppState.demoMode ? '<button type="button" class="btn" id="emptyStateSampleBtn">Try a demo</button>' : ''}
        </div>
      </div>
    `;
    document.getElementById('emptyStateStartAuditBtn').addEventListener('click', () => {
      AppState.auditStage = 'input';
      switchView('new-audit');
    });
    const demoBtn = document.getElementById('emptyStateSampleBtn');
    if (demoBtn) {
      demoBtn.addEventListener('click', () => {
        AppState.auditStage = 'input';
        switchView('new-audit');
        loadSamplePreset(1);
      });
    }
    return;
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <h3>No audits match "${escapeHtml(AppState.overviewStatusFilter)}"</h3>
        <p>Select "All" to view all ${allAudits.length} recorded audit(s) for this brand.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>Document</th>
            <th>Last updated</th>
            <th>Status</th>
            <th>Open findings</th>
            <th>Next action</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map((a) => {
            const isDemoAudit = Boolean(
              a.id.startsWith('AUD-100') ||
              (a.document_name && a.document_name.includes('(Demo)')) ||
              (AppState.overviewData && AppState.overviewData.is_demo)
            );
            const sourceBadge = isDemoAudit
              ? `<span class="status-badge badge-neutral" style="font-size: 11px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>Sample data</span></span>`
              : `<span class="status-badge badge-info" style="font-size: 11px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg><span>Custom</span></span>`;

            let actionLabel = 'Open review';
            let actionClass = 'btn btn-sm open-audit-btn';
            if (a.overall_status === 'Approved') {
              actionLabel = 'View report';
              actionClass = 'btn btn-sm btn-ghost open-audit-btn';
            } else if (a.overall_status === 'In Review' || a.open_findings > 0) {
              actionLabel = 'Review findings';
              actionClass = 'btn btn-sm btn-accent open-audit-btn';
            } else if (a.overall_status === 'Draft') {
              actionLabel = 'Resume draft';
              actionClass = 'btn btn-sm open-audit-btn';
            }

            return `
            <tr>
              <td data-label="Document">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <strong>${escapeHtml(a.document_name)}</strong>
                  ${sourceBadge}
                </div>
                <div style="margin-top: 3px; display: flex; gap: 6px; align-items: center;">
                  <button type="button" class="id-chip copy-id-chip" data-copy-text="${escapeHtml(a.id)}" title="Copy audit ID">${escapeHtml(a.id)}</button>
                  <span class="mono-id">${escapeHtml(a.input_format)}</span>
                </div>
              </td>
              <td data-label="Last updated" class="nowrap-col" style="font-size: 12.5px; color: var(--text-secondary);" title="${escapeHtml(a.updated_at)}">${escapeHtml(formatTimestamp(a.updated_at))}</td>
              <td data-label="Status" class="nowrap-col">${renderStateBadge(a.overall_status)}</td>
              <td data-label="Open findings" class="nowrap-col">
                ${a.open_findings > 0
                  ? `<span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>${a.open_findings} open</span></span>`
                  : `<span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>0 open (${a.total_findings} resolved)</span></span>`}
              </td>
              <td data-label="Next action" class="nowrap-col">
                <button type="button" class="${actionClass}" data-audit-id="${escapeHtml(a.id)}">${actionLabel}</button>
              </td>
            </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  container.querySelectorAll('.open-audit-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-audit-id');
      await openAuditById(id);
    });
  });
}

async function openAuditById(auditId, updateHash = true) {
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
      isNavigatingHash = true;
      window.location.hash = `#/audit/${encodeURIComponent(auditId)}`;
      setTimeout(() => { isNavigatingHash = false; }, 50);
    }
    await switchView('new-audit', false);
  } catch (err) {
    showToast(`Could not load audit ${auditId}: ${err.message}`);
  }
}

// ============================================================================
// VIEW 2: NEW AUDIT (STEP 1 & 2 INPUT) vs AUDIT RESULTS (STEP 3 WORKSPACE)
// ============================================================================

function syncVisualCheckControlState() {
  const fileInput = document.getElementById('auditFileUpload');
  const fg = document.getElementById('auditFgColor').value.trim();
  const bg = document.getElementById('auditBgColor').value.trim();
  const checkbox = document.getElementById('auditHasVisualAsset');
  const helper = document.getElementById('visualCheckHelper');

  const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
  const fileName = hasFile ? fileInput.files[0].name.toLowerCase() : '';
  const isVisualFile = /\.(png|jpg|jpeg|svg)$/.test(fileName);
  const hasColors = Boolean(fg || bg);

  if (isVisualFile || hasColors) {
    checkbox.checked = true;
    helper.textContent = isVisualFile
      ? `Visual asset "${fileInput.files[0].name}" detected — palette and alt-text checks enabled.`
      : 'Hex colour values entered — palette tolerance and WCAG contrast checks enabled.';
  } else if (!checkbox.checked) {
    helper.textContent = 'No visual asset attached. Relevant visual checks will be marked Not checked.';
  } else {
    helper.textContent = 'Visual asset checks enabled for this audit (requires alt-text or colour values).';
  }
}

function bindAuditWorkspaceEvents() {
  // Wizard flow switcher buttons
  const wizUseExistingBtn = document.getElementById('wizardUseExistingBtn');
  const wizQuickSkipBtn = document.getElementById('wizardQuickSkipBtn');
  const switchToWizardBtn = document.getElementById('switchToWizardBtn');

  if (wizUseExistingBtn) {
    wizUseExistingBtn.addEventListener('click', () => {
      AppState.wizardMode = false;
      renderAuditWorkspace();
    });
  }

  if (wizQuickSkipBtn) {
    wizQuickSkipBtn.addEventListener('click', async () => {
      AppState.wizardAnswers = {
        content_type: 'webpage',
        industry: 'general',
        occasion: 'everyday',
        locale: 'global',
        tone: 'professional',
        company_name: '',
        never_use_words: '',
      };
      AppState.wizardStep = 8;
      await renderWizard();
    });
  }

  if (switchToWizardBtn) {
    switchToWizardBtn.addEventListener('click', () => {
      AppState.wizardMode = true;
      AppState.wizardStep = 1;
      renderAuditWorkspace();
    });
  }

  // Wire run button validation state (Task 5)
  const auditContentEl = document.getElementById('auditContentText');
  if (auditContentEl) {
    ['input', 'change', 'paste', 'keyup'].forEach((evt) => {
      auditContentEl.addEventListener(evt, updateRunAuditBtnState);
    });
  }

  // Ingestion method toggle: Paste content vs Upload file
  const pasteBtn = document.getElementById('inputMethodPasteBtn');
  const uploadBtn = document.getElementById('inputMethodUploadBtn');
  const pasteSec = document.getElementById('ingestionPasteSection');
  const uploadSec = document.getElementById('ingestionUploadSection');

  if (pasteBtn && uploadBtn) {
    pasteBtn.addEventListener('click', () => {
      AppState.inputMethod = 'paste';
    updateRunAuditBtnState();
      pasteBtn.classList.add('active');
      pasteBtn.setAttribute('aria-selected', 'true');
      uploadBtn.classList.remove('active');
      uploadBtn.setAttribute('aria-selected', 'false');
      if (pasteSec) pasteSec.style.display = 'block';
      if (uploadSec) uploadSec.style.display = 'none';
    });

    uploadBtn.addEventListener('click', () => {
      AppState.inputMethod = 'upload';
    updateRunAuditBtnState();
      uploadBtn.classList.add('active');
      uploadBtn.setAttribute('aria-selected', 'true');
      pasteBtn.classList.remove('active');
      pasteBtn.setAttribute('aria-selected', 'false');
      if (pasteSec) pasteSec.style.display = 'none';
      if (uploadSec) uploadSec.style.display = 'block';
    });
  }

  // File upload validation & preview bar
  const fileInput = document.getElementById('auditFileUpload');
  const previewBar = document.getElementById('uploadFilePreviewBar');
  const dropzone = document.getElementById('fileDropzone');
  const fileCard = document.getElementById('uploadFileCard');
  const removeFileBtn = document.getElementById('removeUploadedFileBtn');

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });
    ['dragenter', 'dragover'].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });
    ['dragleave', 'drop'].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });
    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
      }
    });
  }

  if (removeFileBtn && fileInput) {
    removeFileBtn.addEventListener('click', () => {
      fileInput.value = '';
      if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
      if (previewBar) previewBar.style.display = 'none';
      syncVisualCheckControlState();
    });
  }

  fileInput.addEventListener('change', () => {
    if (!fileInput.files || fileInput.files.length === 0) {
      if (previewBar) previewBar.style.display = 'none';
      if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
      syncVisualCheckControlState();
      return;
    }
    const f = fileInput.files[0];
    const maxBytes = 5 * 1024 * 1024;
    const ext = (f.name.split('.').pop() || '').toLowerCase();
    const allowed = ['txt', 'md', 'markdown', 'html', 'htm', 'docx', 'pdf', 'svg', 'png', 'jpg', 'jpeg'];

    if (!allowed.includes(ext)) {
      showToast(`Unsupported file type ".${ext}". Allowed: .txt, .md, .html, .docx, .pdf, .svg, .png, .jpg.`);
      fileInput.value = '';
      if (previewBar) previewBar.style.display = 'none';
      if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
      syncVisualCheckControlState();
      return;
    }
    if (f.size > maxBytes) {
      showToast(`File "${f.name}" exceeds the 5 MB limit (${(f.size / (1024 * 1024)).toFixed(2)} MB).`);
      fileInput.value = '';
      if (previewBar) previewBar.style.display = 'none';
      if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
      syncVisualCheckControlState();
      return;
    }

    const sizeKb = (f.size / 1024).toFixed(1);
    const formatMap = {
      pdf: 'PDF Document',
      docx: 'DOCX Document',
      html: 'HTML Document',
      htm: 'HTML Document',
      md: 'Markdown Document',
      markdown: 'Markdown Document',
      txt: 'Plain Text',
      svg: 'SVG Vector Graphic',
      png: 'PNG Image',
      jpg: 'JPEG Image',
      jpeg: 'JPEG Image',
    };
    const detected = formatMap[ext] || `.${ext.toUpperCase()}`;

    if (fileCard) {
      const fNameEl = document.getElementById('uploadCardFileName');
      const fSizeEl = document.getElementById('uploadCardFileSize');
      const fFormatEl = document.getElementById('uploadCardDetectedFormat');
      if (fNameEl) fNameEl.textContent = f.name;
      if (fSizeEl) fSizeEl.textContent = `${sizeKb} KB`;
      if (fFormatEl) fFormatEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${escapeHtml(detected)}</span>`;
      fileCard.style.display = 'flex';
    }

    // Auto-fill document title if empty or default
    const docNameInput = document.getElementById('auditDocName');
    if (docNameInput && (!docNameInput.value.trim() || docNameInput.value === 'Q4 Settlement Launch Brief')) {
      const baseName = f.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
      docNameInput.value = baseName.charAt(0).toUpperCase() + baseName.slice(1);
    }

    if (previewBar) {
      previewBar.style.display = 'flex';
      previewBar.innerHTML = `
        <span>Attached: <strong>${escapeHtml(f.name)}</strong> (${sizeKb} KB)</span>
        <button type="button" class="btn btn-sm" id="removeAttachedFileBtn">Remove file</button>
      `;
      const btn = document.getElementById('removeAttachedFileBtn');
      if (btn) {
        btn.addEventListener('click', () => {
          fileInput.value = '';
          previewBar.style.display = 'none';
          if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
          syncVisualCheckControlState();
        });
      }
    }
    syncVisualCheckControlState();
    updateRunAuditBtnState();
  });

  document.getElementById('auditFgColor').addEventListener('input', syncVisualCheckControlState);
  document.getElementById('auditBgColor').addEventListener('input', syncVisualCheckControlState);
  document.getElementById('auditHasVisualAsset').addEventListener('change', syncVisualCheckControlState);

  // Honest processing mode indicator is updated via updateProcessingModeUI()

  document.getElementById('clearAuditFormBtn').addEventListener('click', () => {
    const hasContent = Boolean(
      (document.getElementById('auditContentText') && document.getElementById('auditContentText').value.trim()) ||
      (fileInput && fileInput.files && fileInput.files.length > 0)
    );
    const doClear = () => {
      document.getElementById('auditDocName').value = '';
      document.getElementById('auditContentText').value = '';
      document.getElementById('auditFgColor').value = '';
      document.getElementById('auditBgColor').value = '';
      document.getElementById('auditAltText').value = '';
      updateRunAuditBtnState();
      if (fileInput) fileInput.value = '';
      if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
      if (previewBar) previewBar.style.display = 'none';
      document.getElementById('auditHasVisualAsset').checked = false;
      syncVisualCheckControlState();
    };

    if (hasContent) {
      openModalDialog({
        title: 'Clear audit form?',
        bodyHtml: '<p>Are you sure you want to clear the content and reset form fields? This action cannot be undone.</p>',
        confirmLabel: 'Clear form',
        cancelLabel: 'Keep content',
        onConfirm: doClear,
      });
    } else {
      doClear();
    }
  });

  document.getElementById('returnToResultsBtn').addEventListener('click', () => {
    if (AppState.currentAudit) {
      AppState.auditStage = 'results';
      renderAuditWorkspace();
    }
  });

  document.getElementById('editContentBtn').addEventListener('click', () => {
    if (AppState.currentAudit) {
      document.getElementById('auditDocName').value = AppState.currentAudit.document_name;
      document.getElementById('auditContentText').value = AppState.currentAudit.current_content;
      document.getElementById('auditFgColor').value = AppState.currentAudit.fg_color || '';
      document.getElementById('auditBgColor').value = AppState.currentAudit.bg_color || '';
      document.getElementById('auditAltText').value = AppState.currentAudit.image_alt_text || '';
      document.getElementById('auditHasVisualAsset').checked = Boolean(AppState.currentAudit.has_visual_asset);
      syncVisualCheckControlState();
    }
    AppState.auditStage = 'input';
    renderAuditWorkspace();
  });

  document.getElementById('startAnotherAuditBtn').addEventListener('click', () => {
    AppState.auditStage = 'input';
    renderAuditWorkspace();
  });

  document.getElementById('rerunAuditBtn').addEventListener('click', async () => {
    if (!AppState.currentAudit) return;
    const btn = document.getElementById('rerunAuditBtn');
    btn.disabled = true;
    btn.textContent = AppState.processingMode === 'local' ? 'Auditing locally...' : 'Running audit...';
    try {
      const updated = await apiFetch(`/api/audits/${encodeURIComponent(AppState.currentAudit.id)}/rerun`, {
        method: 'POST',
      });
      AppState.currentAudit = updated;
      AppState.selectedFindingId = null;
      renderAuditWorkspace();
      await refreshOverview();
      showToast(`Reran audit ${updated.id} (${updated.findings.length} finding(s)).`);
    } catch (err) {
      showToast(`Rerun failed: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Rerun audit';
    }
  });

  const runAuditBtnEl = document.getElementById('runAuditBtn');
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
  });

  // Rendered vs Source format toggle
  document.getElementById('viewRenderedBtn').addEventListener('click', () => {
    AppState.sourceFormatView = 'rendered';
    document.getElementById('viewRenderedBtn').classList.add('active');
    document.getElementById('viewRawSourceBtn').classList.remove('active');
    renderSourceContentPanel();
  });

  document.getElementById('viewRawSourceBtn').addEventListener('click', () => {
    AppState.sourceFormatView = 'source';
    document.getElementById('viewRawSourceBtn').classList.add('active');
    document.getElementById('viewRenderedBtn').classList.remove('active');
    renderSourceContentPanel();
  });

  // Working vs Original content toggle
  document.getElementById('showWorkingContentBtn').addEventListener('click', () => {
    AppState.sourceViewMode = 'working';
    document.getElementById('showWorkingContentBtn').classList.add('active');
    document.getElementById('showOriginalContentBtn').classList.remove('active');
    renderSourceContentPanel();
  });

  document.getElementById('showOriginalContentBtn').addEventListener('click', () => {
    AppState.sourceViewMode = 'original';
    document.getElementById('showOriginalContentBtn').classList.add('active');
    document.getElementById('showWorkingContentBtn').classList.remove('active');
    renderSourceContentPanel();
  });

  // Findings filters
  document.getElementById('pillarFilterSelect').addEventListener('change', (e) => {
    AppState.selectedPillarFilter = e.target.value;
    renderSixPillarsBar();
    renderFindingsCenterPanel();
  });

  document.getElementById('severityFilterSelect').addEventListener('change', (e) => {
    AppState.selectedSeverityFilter = e.target.value;
    renderFindingsCenterPanel();
  });

  document.getElementById('statusFilterSelect').addEventListener('change', (e) => {
    AppState.selectedStatusFilter = e.target.value;
    renderFindingsCenterPanel();
  });

  document.getElementById('findingSearchInput').addEventListener('input', (e) => {
    AppState.findingSearchQuery = e.target.value.trim().toLowerCase();
    renderFindingsCenterPanel();
  });

  // Mobile panel tabs
  document.querySelectorAll('#mobilePanelTabs button[data-mob-panel]').forEach((btn) => {
    btn.addEventListener('click', () => {
      AppState.activeMobilePanel = btn.getAttribute('data-mob-panel');
      updateMobilePanelVisibility();
    });
  });

  // Workflow transitions
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
  });

  document.getElementById('workflowOverrideCheckbox').addEventListener('change', () => {
    updateWorkspaceApprovalGuard();
  });
  document.getElementById('workflowCommentInput').addEventListener('input', () => {
    updateWorkspaceApprovalGuard();
  });
}

function updateMobilePanelVisibility() {
  const pSource = document.getElementById('panelSource');
  const pFindings = document.getElementById('panelFindings');
  const pCorrection = document.getElementById('panelCorrection');
  if (!pSource || !pFindings || !pCorrection) return;

  document.querySelectorAll('#mobilePanelTabs button[data-mob-panel]').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-mob-panel') === AppState.activeMobilePanel);
  });

  pSource.classList.toggle('mobile-hidden-panel', AppState.activeMobilePanel !== 'source');
  pFindings.classList.toggle('mobile-hidden-panel', AppState.activeMobilePanel !== 'findings');
  pCorrection.classList.toggle('mobile-hidden-panel', AppState.activeMobilePanel !== 'correction');
}

function loadSamplePreset(presetNum) {
  if (presetNum === 1) {
    document.getElementById('auditDocName').value = 'Q4 Enterprise Settlement Launch Brief (Demo)';
    document.getElementById('auditInputFormat').value = 'html';
    document.getElementById('auditContentText').value =
      `<h2>Launch Faster with Instant Payouts</h2>\n` +
      `<h4>Key Settlement Highlights</h4>\n` +
      `<p>Our platform guarantees 95% faster processing for cross-border treasury teams. Using our proprietary AI Engine, finance leaders can execute zero-touch autonomous settlement with guaranteed zero risk.</p>\n` +
      `<p>Unlike legacy banking rails, our frictionless synergetic paradigm shift redefines global liquidity across 65 currencies.</p>`;
    document.getElementById('auditFgColor').value = '#94A3B8';
    document.getElementById('auditBgColor').value = '#FFFFFF';
    document.getElementById('auditAltText').value = '';
    document.getElementById('auditHasVisualAsset').checked = true;
    document.getElementById('visualMetadataDetails').open = true;
    syncVisualCheckControlState();
    showToast('Loaded demo example 1 into New audit form.');
  } else if (presetNum === 2) {
    document.getElementById('auditDocName').value = 'Orbital Card Routing Note (Demo)';
    document.getElementById('auditInputFormat').value = 'markdown';
    document.getElementById('auditContentText').value =
      `# NovaPay Orbital Treasury Update\n\n` +
      `Our platform reduces satellite orbital latency by 83% across lunar relays and is #1 in the world for interplanetary clearing.`;
    document.getElementById('auditFgColor').value = '';
    document.getElementById('auditBgColor').value = '';
    document.getElementById('auditAltText').value = '';
    document.getElementById('auditHasVisualAsset').checked = false;
    syncVisualCheckControlState();
    showToast('Loaded demo example 2 (unverified claim without Brand Vault fact).');
  } else if (presetNum === 3) {
    document.getElementById('auditDocName').value = 'Approved Q4 Enterprise Treasury Fact Sheet (Demo)';
    document.getElementById('auditInputFormat').value = 'markdown';
    document.getElementById('auditContentText').value =
      `# NovaPay Enterprise Treasury Release\n\n` +
      `## Verified Settlement Performance\n\n` +
      `Our platform delivers up to 64% faster processing across 42 supported currencies compared to legacy T+2 SWIFT batching (2026 Q3 Treasury Benchmark Report). Our Local Governance Engine operates with human-approved policy guardrails and maintains 99.99% contractual uptime SLA.`;
    document.getElementById('auditFgColor').value = '#17191C';
    document.getElementById('auditBgColor').value = '#FFFFFF';
    document.getElementById('auditAltText').value = 'NovaPay Enterprise Treasury settlement architecture diagram';
    document.getElementById('auditHasVisualAsset').checked = true;
    syncVisualCheckControlState();
    showToast('Loaded demo example 3 (compliant draft).');
  }
}

async function executeTextAudit() {
  let docName = document.getElementById('auditDocName').value.trim();
  const content = document.getElementById('auditContentText').value;
  if (!docName) {
    docName = 'Draft Marketing Document';
    document.getElementById('auditDocName').value = docName;
  }
  if (!content.trim()) {
    showToast('Please enter content to audit.');
    return;
  }

  const errBanner = document.getElementById('auditFormErrorBanner');
  clearInlineError(errBanner);

  if (!AppState.sessionAvailable) {
    showInlineError(errBanner, 'Cannot submit audit: server connection is unavailable. Please click "Retry connection" in the top banner.');
    return;
  }

  const runBtn = document.getElementById('runAuditBtn');
  runBtn.disabled = true;
  runBtn.innerHTML = '<span>Auditing...</span>';

  try {
    const payload = {
      brand_id: AppState.activeBrandId,
      document_name: docName,
      input_format: document.getElementById('auditInputFormat').value,
      content: content,
      fg_color: document.getElementById('auditFgColor').value.trim(),
      bg_color: document.getElementById('auditBgColor').value.trim(),
      image_alt_text: document.getElementById('auditAltText').value.trim(),
      has_visual_asset: document.getElementById('auditHasVisualAsset').checked,
      confidential_mode: true,
    };
    const audit = await apiFetch('/api/audits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    AppState.currentAudit = audit;
    AppState.auditStage = 'results';
    AppState.sourceViewMode = 'working';
    AppState.sourceFormatView = 'rendered';
    AppState.selectedPillarFilter = 'ALL';
    AppState.selectedSeverityFilter = 'ALL';
    AppState.selectedStatusFilter = 'ALL';
    AppState.findingSearchQuery = '';
    AppState.selectedFindingId = null;
    renderAuditWorkspace();
    await refreshOverview();
    showToast(`Audit ${audit.id} saved (${audit.findings.length} finding(s)).`);
  } catch (err) {
    showInlineError(errBanner, `Audit failed: ${err.message}`, () => executeTextAudit());
    showToast(`Audit failed: ${err.message}`);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = '<span>Run audit</span>';
  }
}

async function executeFileUploadAudit(file) {
  const errBanner = document.getElementById('auditFormErrorBanner');
  clearInlineError(errBanner);

  if (!AppState.sessionAvailable) {
    showInlineError(errBanner, 'Cannot upload file: server connection is unavailable. Please click "Retry connection" in the top banner.');
    return;
  }

  const runBtn = document.getElementById('runAuditBtn');
  runBtn.disabled = true;
  runBtn.innerHTML = '<span>Auditing...</span>';

  try {
    const fd = new FormData();
    fd.append('brand_id', AppState.activeBrandId);
    fd.append('document_name', document.getElementById('auditDocName').value.trim() || file.name);
    fd.append('fg_color', document.getElementById('auditFgColor').value.trim());
    fd.append('bg_color', document.getElementById('auditBgColor').value.trim());
    fd.append('image_alt_text', document.getElementById('auditAltText').value.trim());
    fd.append('confidential_mode', 'true');
    fd.append('file', file);

    const audit = await apiFetch('/api/audits/upload', {
      method: 'POST',
      body: fd,
    });
    AppState.currentAudit = audit;
    AppState.auditStage = 'results';
    AppState.sourceViewMode = 'working';
    AppState.sourceFormatView = 'rendered';
    AppState.selectedPillarFilter = 'ALL';
    AppState.selectedFindingId = null;
    renderAuditWorkspace();
    await refreshOverview();
    showToast(`Uploaded "${file.name}" — Audit ${audit.id} saved.`);
  } catch (err) {
    showInlineError(errBanner, `Upload audit failed: ${err.message}`, () => executeFileUploadAudit(file));
    showToast(`Upload audit failed: ${err.message}`);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = '<span>Run audit</span>';
  }
}

// ============================================================================
// GUIDED "NEW AUDIT" WIZARD (SLICE 1)
// ============================================================================

async function ensureWizardOptionsLoaded() {
  if (AppState.wizardOptions) return AppState.wizardOptions;
  try {
    const data = await apiFetch('/api/wizard/options');
    AppState.wizardOptions = data;
    return data;
  } catch (err) {
    console.warn('Failed to fetch wizard options, falling back to local defaults', err);
    return null;
  }
}

function showWizardAlert(type, message) {
  const alert = document.getElementById('wizFeedbackAlert');
  if (!alert) return;
  alert.style.display = 'block';
  if (type === 'error') {
    alert.className = 'banner-error';
    alert.style.background = '#FEF2F2';
    alert.style.color = '#991B1B';
    alert.style.padding = '10px 14px';
    alert.style.borderRadius = '8px';
    alert.style.border = '1px solid #FECACA';
  } else {
    alert.className = 'banner-info';
    alert.style.background = '#F0FDF4';
    alert.style.color = '#166534';
    alert.style.padding = '10px 14px';
    alert.style.borderRadius = '8px';
    alert.style.border = '1px solid #BBF7D0';
  }
  alert.textContent = message;
}

function getSampleTextFallback(industry) {
  if (industry === 'finance') {
    return "Our institutional fund guarantees 18% returns with guaranteed zero risk capital preservation! Traditional banks are destroying your wealth every day. Please do the needful and check our rates.";
  }
  if (industry === 'tech') {
    return "Our unhackable cloud has zero downtime ever and replaces your entire engineering team permanently! This revolutionary miracle product changes everything forever. Customise your dashboard colour today.";
  }
  if (industry === 'health') {
    return "Our miracle cure guarantees a 100% cure rate and replaces doctors worldwide! Diagnose yourself without a physician using our autonomous doctor software.";
  }
  if (industry === 'ecommerce') {
    return "Lowest prices anywhere in the world guaranteed! Only 2 items left—order in 3 seconds or lose it forever during our insane fire sale with a hassle-free lifetime return guarantee with zero conditions.";
  }
  return "We are proud to provide the #1 in the world business consulting service with guaranteed zero risk. Act now or suffer the consequences before it's too late! Our synergistic paradigm delivers silver bullet results.";
}

async function renderWizard() {
  const container = document.getElementById('wizardStepContent');
  if (!container) return;

  await ensureWizardOptionsLoaded();

  const step = AppState.wizardStep || 1;
  const totalSteps = 8;
  const pct = Math.round((step / totalSteps) * 100);

  const fill = document.getElementById('wizardProgressFill');
  const counter = document.getElementById('wizardStepCounter');
  if (fill) fill.style.width = `${pct}%`;
  if (counter) counter.textContent = `Step ${step} of ${totalSteps}`;

  const headerTitle = document.getElementById('wizardHeaderTitle');
  const headerSub = document.getElementById('wizardHeaderSubtitle');

  // Step 1: Q1 What would you like to check?
  if (step === 1) {
    if (headerTitle) headerTitle.textContent = 'What would you like to check?';
    if (headerSub) headerSub.textContent = 'Select the type of content you are preparing to audit.';

    const q = (AppState.wizardOptions?.questions || [])[0] || {
      options: [
        { id: 'webpage', label: 'Website page or blog post', description: 'Landing pages, articles, and documentation.' },
        { id: 'email', label: 'Marketing email or newsletter', description: 'Promotional emails, outreach sequences, and newsletters.' },
        { id: 'social', label: 'Social media post', description: 'Short updates, announcements, and promotional blurbs.' },
        { id: 'ad', label: 'Ad or promotion', description: 'Paid digital banners, PPC headlines, and campaign copy.' },
        { id: 'press_release', label: 'Press release or announcement', description: 'Official company milestones, statements, and media notes.' },
        { id: 'product_desc', label: 'Product description', description: 'Feature overviews, catalogue copy, and packaging text.' },
        { id: 'policy', label: 'Policy or legal page', description: 'Terms of service, privacy statements, and customer policies.' },
        { id: 'report', label: 'Report or presentation', description: 'Whitepapers, executive slides, and research summaries.' },
        { id: 'image_logo', label: 'Image or logo', description: 'Visual assets, wordmarks, colour palettes, and banner graphics.' },
      ]
    };

    container.innerHTML = `
      <div class="wizard-tiles-grid">
        ${q.options.map(opt => `
          <button type="button" class="wizard-tile ${AppState.wizardAnswers.content_type === opt.id ? 'selected' : ''}" data-opt-id="${opt.id}" role="radio" aria-checked="${AppState.wizardAnswers.content_type === opt.id}">
            <div class="wizard-tile-header">
              <span class="wizard-tile-title">${escapeHtml(opt.label)}</span>
              <span class="wizard-tile-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
            </div>
            <p class="wizard-tile-desc">${escapeHtml(opt.description)}</p>
          </button>
        `).join('')}
      </div>
      <div class="wizard-nav-row" style="justify-content: flex-end;">
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Next &rarr;</button>
      </div>
    `;

    container.querySelectorAll('.wizard-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        AppState.wizardAnswers.content_type = tile.getAttribute('data-opt-id');
        container.querySelectorAll('.wizard-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        setTimeout(() => {
          AppState.wizardStep = 2;
          renderWizard();
        }, 120);
      });
    });

    const nextBtn = document.getElementById('wizardNextBtn');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        AppState.wizardStep = 2;
        renderWizard();
      });
    }
    return;
  }

  // Step 2: Q2 What kind of organisation is this for?
  if (step === 2) {
    if (headerTitle) headerTitle.textContent = 'What kind of organisation is this for?';
    if (headerSub) headerSub.textContent = 'Applies industry-specific compliance rules, prohibited terms, and claims checks.';

    const q = (AppState.wizardOptions?.questions || [])[1] || {
      options: [
        { id: 'tech', label: 'Technology or software', description: 'SaaS platforms, developer tools, AI products, and tech infrastructure.' },
        { id: 'finance', label: 'Bank, finance or insurance', description: 'Financial services, treasury management, fintech, and insurance.' },
        { id: 'health', label: 'Health, medical or wellness', description: 'Clinical systems, medical devices, wellness apps, and diagnostic tools.' },
        { id: 'ecommerce', label: 'Shop or e-commerce', description: 'Retail storefronts, consumer brands, and online shopping portals.' },
        { id: 'public_nonprofit', label: 'School, university or government', description: 'Educational institutions, civic agencies, charities, and non-profits.' },
        { id: 'general', label: 'Something else', description: 'General business services, consulting, agency work, and other trades.' },
      ]
    };

    container.innerHTML = `
      <div class="wizard-tiles-grid">
        ${q.options.map(opt => `
          <button type="button" class="wizard-tile ${AppState.wizardAnswers.industry === opt.id ? 'selected' : ''}" data-opt-id="${opt.id}" role="radio" aria-checked="${AppState.wizardAnswers.industry === opt.id}">
            <div class="wizard-tile-header">
              <span class="wizard-tile-title">${escapeHtml(opt.label)}</span>
              <span class="wizard-tile-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
            </div>
            <p class="wizard-tile-desc">${escapeHtml(opt.description)}</p>
          </button>
        `).join('')}
      </div>
      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back</button>
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Next &rarr;</button>
      </div>
    `;

    container.querySelectorAll('.wizard-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        AppState.wizardAnswers.industry = tile.getAttribute('data-opt-id');
        container.querySelectorAll('.wizard-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        setTimeout(() => {
          AppState.wizardStep = 3;
          renderWizard();
        }, 120);
      });
    });

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 1;
      renderWizard();
    });
    document.getElementById('wizardNextBtn').addEventListener('click', () => {
      AppState.wizardStep = 3;
      renderWizard();
    });
    return;
  }

  // Step 3: Q3 Is this for a special occasion?
  if (step === 3) {
    if (headerTitle) headerTitle.textContent = 'Is this for a special occasion?';
    if (headerSub) headerSub.textContent = 'Calibrates urgency, novelty, and sensitivity rules for this specific message.';

    const q = (AppState.wizardOptions?.questions || [])[2] || {
      options: [
        { id: 'everyday', label: 'Just everyday content', description: 'Routine communications, ongoing product information, and standard updates.' },
        { id: 'launch', label: 'Launching something new', description: 'Product debuts, new feature introductions, and major releases.' },
        { id: 'sale', label: 'Sale or discount', description: 'Promotional events, limited-time savings, and seasonal deals.' },
        { id: 'incident', label: 'Handling a problem or incident', description: 'Service downtime notes, incident retrospectives, and customer apology notices.' },
        { id: 'investor', label: 'Investor or regulatory update', description: 'Quarterly shareholder letters, earnings summaries, and compliance filings.' },
        { id: 'seasonal', label: 'Festival or season', description: 'Holiday campaigns, festival greetings, and seasonal celebrations.' },
      ]
    };

    container.innerHTML = `
      <div class="wizard-tiles-grid">
        ${q.options.map(opt => `
          <button type="button" class="wizard-tile ${AppState.wizardAnswers.occasion === opt.id ? 'selected' : ''}" data-opt-id="${opt.id}" role="radio" aria-checked="${AppState.wizardAnswers.occasion === opt.id}">
            <div class="wizard-tile-header">
              <span class="wizard-tile-title">${escapeHtml(opt.label)}</span>
              <span class="wizard-tile-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
            </div>
            <p class="wizard-tile-desc">${escapeHtml(opt.description)}</p>
          </button>
        `).join('')}
      </div>
      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back</button>
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Next &rarr;</button>
      </div>
    `;

    container.querySelectorAll('.wizard-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        AppState.wizardAnswers.occasion = tile.getAttribute('data-opt-id');
        container.querySelectorAll('.wizard-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        setTimeout(() => {
          AppState.wizardStep = 4;
          renderWizard();
        }, 120);
      });
    });

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 2;
      renderWizard();
    });
    document.getElementById('wizardNextBtn').addEventListener('click', () => {
      AppState.wizardStep = 4;
      renderWizard();
    });
    return;
  }

  // Step 4: Q4 Where will most readers be?
  if (step === 4) {
    if (headerTitle) headerTitle.textContent = 'Where will most readers be?';
    if (headerSub) headerSub.textContent = 'Enforces regional spelling, currency notations, and local communication standards.';

    const q = (AppState.wizardOptions?.questions || [])[3] || {
      options: [
        { id: 'en_in', label: 'India', description: '₹ / INR currency conventions, lakh/crore formats, and Indian English spelling.' },
        { id: 'en_us', label: 'United States', description: 'American English spelling (color, organize) and $ / USD notation.' },
        { id: 'en_gb', label: 'United Kingdom', description: 'British English spelling (colour, organise) and £ / GBP notation.' },
        { id: 'en_ca', label: 'Canada', description: 'Canadian English spelling standards and CAD currency clarity.' },
        { id: 'en_au', label: 'Australia', description: 'Australian English spelling and AUD GST-inclusive conventions.' },
        { id: 'global', label: 'Worldwide', description: 'International plain English with standard ISO currency codes.' },
      ]
    };

    container.innerHTML = `
      <div class="wizard-tiles-grid">
        ${q.options.map(opt => `
          <button type="button" class="wizard-tile ${AppState.wizardAnswers.locale === opt.id ? 'selected' : ''}" data-opt-id="${opt.id}" role="radio" aria-checked="${AppState.wizardAnswers.locale === opt.id}">
            <div class="wizard-tile-header">
              <span class="wizard-tile-title">${escapeHtml(opt.label)}</span>
              <span class="wizard-tile-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
            </div>
            <p class="wizard-tile-desc">${escapeHtml(opt.description)}</p>
          </button>
        `).join('')}
      </div>
      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back</button>
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Next &rarr;</button>
      </div>
    `;

    container.querySelectorAll('.wizard-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        AppState.wizardAnswers.locale = tile.getAttribute('data-opt-id');
        container.querySelectorAll('.wizard-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        setTimeout(() => {
          AppState.wizardStep = 5;
          renderWizard();
        }, 120);
      });
    });

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 3;
      renderWizard();
    });
    document.getElementById('wizardNextBtn').addEventListener('click', () => {
      AppState.wizardStep = 5;
      renderWizard();
    });
    return;
  }

  // Step 5: Q5 How should it sound?
  if (step === 5) {
    if (headerTitle) headerTitle.textContent = 'How should it sound?';
    if (headerSub) headerSub.textContent = 'Sets reading ease targets and vocabulary formality benchmarks.';

    const q = (AppState.wizardOptions?.questions || [])[4] || {
      options: [
        { id: 'professional', label: 'Professional', description: 'Authoritative, dignified, and objective corporate communication.' },
        { id: 'friendly', label: 'Friendly', description: 'Warm, conversational, and approachable community voice.' },
        { id: 'clear_simple', label: 'Clear and simple', description: 'Plain language with raised reading ease (65+) and short sentences.' },
        { id: 'bold', label: 'Bold and energetic', description: 'Confident, spirited, and action-driven brand expression.' },
      ]
    };

    container.innerHTML = `
      <div class="wizard-tiles-grid">
        ${q.options.map(opt => `
          <button type="button" class="wizard-tile ${AppState.wizardAnswers.tone === opt.id ? 'selected' : ''}" data-opt-id="${opt.id}" role="radio" aria-checked="${AppState.wizardAnswers.tone === opt.id}">
            <div class="wizard-tile-header">
              <span class="wizard-tile-title">${escapeHtml(opt.label)}</span>
              <span class="wizard-tile-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
            </div>
            <p class="wizard-tile-desc">${escapeHtml(opt.description)}</p>
          </button>
        `).join('')}
      </div>
      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back</button>
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Next &rarr;</button>
      </div>
    `;

    container.querySelectorAll('.wizard-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        AppState.wizardAnswers.tone = tile.getAttribute('data-opt-id');
        container.querySelectorAll('.wizard-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        setTimeout(() => {
          AppState.wizardStep = 6;
          renderWizard();
        }, 120);
      });
    });

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 4;
      renderWizard();
    });
    document.getElementById('wizardNextBtn').addEventListener('click', () => {
      AppState.wizardStep = 6;
      renderWizard();
    });
    return;
  }

  // Step 6: Q6 (Optional) Company name & words you never want used
  if (step === 6) {
    if (headerTitle) headerTitle.textContent = 'Organisation details (optional)';
    if (headerSub) headerSub.textContent = 'Optionally add your brand name and any custom words you never want used in your content.';

    container.innerHTML = `
      <div style="max-width: 600px; margin: 20px 0 28px 0;">
        <div class="form-group" style="margin-bottom: 20px;">
          <label for="wizCompanyName" style="font-size: 13.5px; font-weight: 600; color: var(--primary-ink); display: block; margin-bottom: 6px;">Your company or product name</label>
          <input type="text" id="wizCompanyName" class="form-control" placeholder="e.g., NovaPay, Acme Labs, Orbit Software" value="${escapeHtml(AppState.wizardAnswers.company_name || '')}" />
          <div class="form-helper">Used to label your generated compliance checks.</div>
        </div>

        <div class="form-group">
          <label for="wizNeverUseWords" style="font-size: 13.5px; font-weight: 600; color: var(--primary-ink); display: block; margin-bottom: 6px;">Words you never want used (separate with commas)</label>
          <input type="text" id="wizNeverUseWords" class="form-control" placeholder="e.g., cheap, guru, magic, unhackable" value="${escapeHtml(AppState.wizardAnswers.never_use_words || '')}" />
          <div class="form-helper">Any flagged words will be automatically checked and reported as issues.</div>
        </div>
      </div>
      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back</button>
        <button type="button" class="btn btn-accent" id="wizardNextBtn">Review your checks &rarr;</button>
      </div>
    `;

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 5;
      renderWizard();
    });
    document.getElementById('wizardNextBtn').addEventListener('click', async () => {
      const nameInput = document.getElementById('wizCompanyName');
      const wordsInput = document.getElementById('wizNeverUseWords');
      if (nameInput) AppState.wizardAnswers.company_name = nameInput.value.trim();
      if (wordsInput) AppState.wizardAnswers.never_use_words = wordsInput.value.trim();
      AppState.wizardStep = 7;
      await renderWizard();
    });
    return;
  }

  // Step 7: Review Screen ("Here's what we'll check")
  if (step === 7) {
    if (headerTitle) headerTitle.textContent = "Here's what we'll check";
    if (headerSub) headerSub.textContent = 'Generated from your answers. Verified automatically using server-enforced compliance engines.';

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; padding: 40px;">
        <span style="font-size: 14px; color: var(--text-secondary);">Building your compliance checks...</span>
      </div>
    `;

    try {
      const preview = await apiFetch('/api/wizard/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(AppState.wizardAnswers),
      });
      AppState.wizardPreview = preview;
      AppState.wizardSampleText = preview.sample_text || '';

      container.innerHTML = `
        <div style="margin-top: 8px; margin-bottom: 20px;">
          <div style="display: inline-flex; align-items: center; gap: 8px; background: #EEF2F6; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; color: #1E293B;">
            <span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="color: var(--primary-action);"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></span>
            <span>${escapeHtml(preview.profile_label)}</span>
          </div>
        </div>

        <div class="wizard-review-box">
          <div style="font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--primary-ink);">
            The following verification standards will be applied:
          </div>
          <div class="wizard-review-list">
            ${(preview.summary || []).map(bullet => `
              <div class="wizard-bullet-item">
                <span class="wizard-bullet-icon"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></span>
                <span>${escapeHtml(bullet)}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="wizard-nav-row">
          <button type="button" class="btn" id="wizardChangeAnswersBtn">&larr; Change my answers</button>
          <button type="button" class="btn btn-accent" id="wizardLooksGoodBtn">Looks good, add content &rarr;</button>
        </div>
      `;

      document.getElementById('wizardChangeAnswersBtn').addEventListener('click', () => {
        AppState.wizardStep = 1;
        renderWizard();
      });

      document.getElementById('wizardLooksGoodBtn').addEventListener('click', () => {
        AppState.wizardStep = 8;
        renderWizard();
      });
    } catch (err) {
      container.innerHTML = `
        <div class="banner-error" style="margin: 20px 0; padding: 16px; border-radius: 8px; background: #FEF2F2; color: #991B1B;">
          <strong>Error loading checks:</strong> ${escapeHtml(err.message || 'Please verify the server connection.')}
        </div>
        <div class="wizard-nav-row">
          <button type="button" class="btn" id="wizardChangeAnswersBtn">&larr; Change answers</button>
          <button type="button" class="btn btn-accent" id="wizardRetryPreviewBtn">Retry</button>
        </div>
      `;
      document.getElementById('wizardChangeAnswersBtn').addEventListener('click', () => {
        AppState.wizardStep = 1;
        renderWizard();
      });
      document.getElementById('wizardRetryPreviewBtn').addEventListener('click', () => {
        renderWizard();
      });
    }
    return;
  }

  // Step 8: Add-content screen ("Add your content")
  if (step === 8) {
    if (headerTitle) headerTitle.textContent = 'Add your content';
    if (headerSub) headerSub.textContent = `Audit your content against ${AppState.wizardPreview?.profile_label || 'your newly configured checks'}.`;

    const isImageMode = AppState.wizardAnswers.content_type === 'image_logo';
    const defaultDocTitle = AppState.wizardAnswers.company_name
      ? `${AppState.wizardAnswers.company_name} Campaign Draft`
      : 'Campaign Draft Review';

    container.innerHTML = `
      <div style="margin-bottom: 20px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
          <div>
            <label for="wizAuditDocTitle" style="font-size: 13.5px; font-weight: 600; color: var(--primary-ink); display: block; margin-bottom: 4px;">Document title</label>
            <input type="text" id="wizAuditDocTitle" class="form-control" style="width: 320px; max-width: 100%;" value="${escapeHtml(defaultDocTitle)}" />
          </div>
          <button type="button" class="btn btn-sm btn-ghost" id="wizTryExampleBtn" style="color: var(--primary-action); border-color: var(--primary-action);">
            Try an example with a few mistakes
          </button>
        </div>

        <!-- Ingestion Method Tabs -->
        <div style="margin-bottom: 14px;">
          <div class="segmented-toggle" role="tablist">
            <button type="button" class="segmented-btn active" id="wizPasteTabBtn" role="tab" aria-selected="true">Paste your text</button>
            <button type="button" class="segmented-btn" id="wizUploadTabBtn" role="tab" aria-selected="false">Upload a file (5 MB limit)</button>
          </div>
        </div>

        <!-- Paste Text Ingestion -->
        <div id="wizPasteArea">
          <textarea id="wizContentText" class="form-control" rows="8" placeholder="Paste your text or marketing copy here..."></textarea>
        </div>

        <!-- File Upload Ingestion -->
        <div id="wizUploadArea" style="display: none;">
          <div class="file-dropzone" id="wizFileDropzone" tabindex="0" role="button" aria-label="Drop or click to upload a file">
            <div style="font-size: 14px; font-weight: 600; color: var(--primary-ink);">Click to select or drag and drop a file</div>
            <div class="form-helper" style="margin-top: 4px;">Supported formats: .txt, .md, .html, .docx, .pdf, .svg, .png, .jpg (Max 5 MB)</div>
            <input type="file" id="wizFileInput" style="display: none;" accept=".txt,.md,.html,.htm,.docx,.pdf,.svg,.png,.jpg,.jpeg" />
          </div>
          <div id="wizFileCard" class="file-card" style="display: none; margin-top: 12px;">
            <div class="file-card-info">
              <div>
                <div class="file-card-name" id="wizFileName">document.txt</div>
                <div class="file-card-size" id="wizFileSize">0 KB</div>
              </div>
            </div>
            <button type="button" class="btn btn-sm btn-danger-outline" id="wizRemoveFileBtn">Remove</button>
          </div>
        </div>

        <!-- Optional Image Fields if Q1 == image_logo -->
        ${isImageMode ? `
          <div style="margin-top: 16px; padding: 16px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;">
            <div style="font-size: 13.5px; font-weight: 600; margin-bottom: 12px;">Image & Brand Colour Specifications</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
              <div>
                <label for="wizFgColor" style="font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 4px;">Foreground Hex (#RRGGBB)</label>
                <input type="text" id="wizFgColor" class="form-control" placeholder="#17191C" value="#17191C" />
              </div>
              <div>
                <label for="wizBgColor" style="font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 4px;">Background Hex (#RRGGBB)</label>
                <input type="text" id="wizBgColor" class="form-control" placeholder="#FFFFFF" value="#FFFFFF" />
              </div>
              <div style="grid-column: 1 / -1;">
                <label for="wizAltText" style="font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 4px;">Image Alternative Text</label>
                <input type="text" id="wizAltText" class="form-control" placeholder="Describe the image asset for accessibility compliance" />
              </div>
            </div>
          </div>
        ` : ''}

        <div id="wizFeedbackAlert" style="display: none; margin-top: 12px;"></div>
      </div>

      <div class="wizard-nav-row">
        <button type="button" class="btn" id="wizardBackBtn">&larr; Back to review</button>
        <button type="button" class="btn btn-accent btn-lg" id="wizardRunCheckBtn" style="padding: 10px 24px; font-weight: 600;">
          Check my content &rarr;
        </button>
      </div>
    `;

    // Try Example Button
    let activeUploadedFile = null;
    const tryExBtn = document.getElementById('wizTryExampleBtn');
    const textArea = document.getElementById('wizContentText');
    const docTitleInput = document.getElementById('wizAuditDocTitle');

    if (tryExBtn && textArea) {
      tryExBtn.addEventListener('click', () => {
        const sample = AppState.wizardSampleText || getSampleTextFallback(AppState.wizardAnswers.industry);
        textArea.value = sample;
        if (docTitleInput) {
          docTitleInput.value = `${AppState.wizardPreview?.profile_label || 'Campaign'} Sample Review`;
        }
        showWizardAlert('info', 'Loaded realistic sample copy containing intentional compliance errors.');
      });
    }

    // Toggle Paste / Upload
    const pasteTabBtn = document.getElementById('wizPasteTabBtn');
    const uploadTabBtn = document.getElementById('wizUploadTabBtn');
    const pasteArea = document.getElementById('wizPasteArea');
    const uploadArea = document.getElementById('wizUploadArea');

    if (pasteTabBtn && uploadTabBtn) {
      pasteTabBtn.addEventListener('click', () => {
        pasteTabBtn.classList.add('active');
        pasteTabBtn.setAttribute('aria-selected', 'true');
        uploadTabBtn.classList.remove('active');
        uploadTabBtn.setAttribute('aria-selected', 'false');
        if (pasteArea) pasteArea.style.display = 'block';
        if (uploadArea) uploadArea.style.display = 'none';
      });

      uploadTabBtn.addEventListener('click', () => {
        uploadTabBtn.classList.add('active');
        uploadTabBtn.setAttribute('aria-selected', 'true');
        pasteTabBtn.classList.remove('active');
        pasteTabBtn.setAttribute('aria-selected', 'false');
        if (pasteArea) pasteArea.style.display = 'none';
        if (uploadArea) uploadArea.style.display = 'block';
      });
    }

    // Upload handling
    const dropzone = document.getElementById('wizFileDropzone');
    const fileInput = document.getElementById('wizFileInput');
    const fileCard = document.getElementById('wizFileCard');
    const fileName = document.getElementById('wizFileName');
    const fileSize = document.getElementById('wizFileSize');
    const removeBtn = document.getElementById('wizRemoveFileBtn');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());
      dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
      dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length) {
          handleFile(e.dataTransfer.files[0]);
        }
      });
      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length) {
          handleFile(fileInput.files[0]);
        }
      });
    }

    function handleFile(file) {
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        showWizardAlert('error', 'File size exceeds maximum 5 MB limit.');
        return;
      }
      activeUploadedFile = file;
      if (fileName) fileName.textContent = file.name;
      if (fileSize) fileSize.textContent = `${Math.round(file.size / 1024)} KB`;
      if (fileCard) fileCard.style.display = 'flex';
      if (dropzone) dropzone.style.display = 'none';
      if (docTitleInput && (!docTitleInput.value || docTitleInput.value === defaultDocTitle)) {
        docTitleInput.value = file.name.replace(/\.[^/.]+$/, '');
      }
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        activeUploadedFile = null;
        if (fileInput) fileInput.value = '';
        if (fileCard) fileCard.style.display = 'none';
      updateRunAuditBtnState();
        if (dropzone) dropzone.style.display = 'block';
      });
    }

    document.getElementById('wizardBackBtn').addEventListener('click', () => {
      AppState.wizardStep = 7;
      renderWizard();
    });

    // Run Audit
    const runBtn = document.getElementById('wizardRunCheckBtn');
    if (runBtn) {
      runBtn.addEventListener('click', async () => {
        const isPaste = pasteTabBtn.classList.contains('active');
        const textContent = (textArea ? textArea.value : '').trim();
        const docName = (docTitleInput ? docTitleInput.value : '').trim() || 'Audited Document';

        if (isPaste && !textContent) {
          showWizardAlert('error', 'Please paste your text or click "Try an example" above.');
          return;
        }
        if (!isPaste && !activeUploadedFile) {
          showWizardAlert('error', 'Please select a file to upload or switch to "Paste your text".');
          return;
        }

        runBtn.disabled = true;
        runBtn.textContent = 'Creating profile & auditing...';

        try {
          // 1. Create Profile in DB
          const profileRes = await apiFetch('/api/wizard/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(AppState.wizardAnswers),
          });

          const newBrandId = profileRes.brand_id;
          AppState.activeBrandId = newBrandId;

          // Reload brands list so topbar shows new profile
          try {
            const brandsData = await apiFetch('/api/brands');
            AppState.brands = brandsData.brands || [];
            updateTopbarContext();
          } catch (e) {
            console.warn('Failed to refresh brands list', e);
          }

          // 2. Run Audit
          let auditResult = null;
          if (isPaste) {
            const payload = {
              brand_id: newBrandId,
              document_name: docName,
              content: textContent,
              input_format: 'plain_text',
            };
            if (isImageMode) {
              payload.fg_color = document.getElementById('wizFgColor')?.value || '#17191C';
              payload.bg_color = document.getElementById('wizBgColor')?.value || '#FFFFFF';
              payload.image_alt_text = document.getElementById('wizAltText')?.value || '';
              payload.has_visual_asset = true;
            }
            auditResult = await apiFetch('/api/audits', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
          } else {
            const formData = new FormData();
            formData.append('brand_id', newBrandId);
            formData.append('document_name', docName);
            formData.append('file', activeUploadedFile);
            if (isImageMode) {
              formData.append('fg_color', document.getElementById('wizFgColor')?.value || '#17191C');
              formData.append('bg_color', document.getElementById('wizBgColor')?.value || '#FFFFFF');
              formData.append('image_alt_text', document.getElementById('wizAltText')?.value || '');
              formData.append('has_visual_asset', 'true');
            }
            auditResult = await apiFetch('/api/audits/upload', {
              method: 'POST',
              body: formData,
            });
          }

          // 3. Navigate to results stage
          AppState.currentAudit = auditResult;
          AppState.auditStage = 'results';
          AppState.wizardMode = false;
          renderAuditWorkspace();
          showToast(`Audit complete for ${docName}`);
        } catch (err) {
          runBtn.disabled = false;
          runBtn.textContent = 'Check my content →';
          showWizardAlert('error', err.message || 'Audit failed. Please try again.');
        }
      });
    }
  }
}

function renderAuditWorkspace() {
  const wizardStage = document.getElementById('wizardStage');
  const inputStage = document.getElementById('auditInputStage');
  const resultsStage = document.getElementById('auditResultsStage');
  const backBtn = document.getElementById('returnToResultsBtn');

  if (backBtn) {
    backBtn.style.display = AppState.currentAudit ? 'inline-flex' : 'none';
  }

  if (!AppState.currentAudit || AppState.auditStage === 'input') {
    if (resultsStage) resultsStage.style.display = 'none';
    if (AppState.wizardMode) {
      if (wizardStage) wizardStage.style.display = 'block';
      if (inputStage) inputStage.style.display = 'none';
      document.getElementById('topbarViewTitle').textContent = 'Guided audit setup';
      renderWizard();
    } else {
      if (wizardStage) wizardStage.style.display = 'none';
      if (inputStage) inputStage.style.display = 'block';
      document.getElementById('topbarViewTitle').textContent = 'New audit';
      syncVisualCheckControlState();
    }
    return;
  }

  if (wizardStage) wizardStage.style.display = 'none';
  if (inputStage) inputStage.style.display = 'none';
  if (resultsStage) resultsStage.style.display = 'block';
  document.getElementById('topbarViewTitle').textContent = 'Audit results';

  const audit = AppState.currentAudit;
  const certBtn = document.getElementById('resultsCertificateBtn');
  if (certBtn) {
    certBtn.style.display = audit.overall_status === 'Approved' ? 'inline-flex' : 'none';
  }
  const openCount = audit.open_findings_count ?? (audit.findings || []).filter((f) => ['open', 'needs_review'].includes(f.review_state)).length;

  const activeBrand = AppState.brands.find((b) => b.id === audit.brand_id);
  const profileHeading = (activeBrand && activeBrand.name && activeBrand.id.startsWith('wiz-'))
    ? `${activeBrand.name} · ${audit.document_name}`
    : `New audit / ${audit.document_name}`;

  document.getElementById('resultsBreadcrumbDocName').textContent = profileHeading;
  const procLabel = AppState.processingMode === 'local' ? 'Local processing' : 'Hosted engine';
  document.getElementById('resultsSummarySubtitle').textContent =
    `${openCount} issue(s) need attention · ${procLabel} (${audit.runtime_ms} ms) · Saved ${formatTimestamp(audit.updated_at)}`;

  updateMobilePanelVisibility();
  renderSixPillarsBar();
  renderSourceContentPanel();
  renderFindingsCenterPanel();
  renderCorrectionRightPanel();
}

function renderSixPillarsBar() {
  const bar = document.getElementById('sixPillarsBar');
  const states = (AppState.currentAudit && AppState.currentAudit.pillar_states) || {};

  bar.innerHTML = SIX_PILLARS.map((pillar) => {
    const st = states[pillar] || 'Not Checked';
    const isActive = AppState.selectedPillarFilter === pillar;
    return `
      <div class="pillar-chip ${isActive ? 'active-filter' : ''}" data-pillar="${escapeHtml(pillar)}" role="button" tabindex="0">
        <span class="pillar-chip-name">${escapeHtml(pillar)}</span>
        <div>${renderStateBadge(st)}</div>
      </div>
    `;
  }).join('');

  bar.querySelectorAll('.pillar-chip').forEach((chip) => {
    const activate = () => {
      const clicked = chip.getAttribute('data-pillar');
      AppState.selectedPillarFilter = AppState.selectedPillarFilter === clicked ? 'ALL' : clicked;
      document.getElementById('pillarFilterSelect').value = AppState.selectedPillarFilter;
      renderSixPillarsBar();
      renderFindingsCenterPanel();
    };
    chip.addEventListener('click', activate);
    chip.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        activate();
      }
    });
  });
}

function renderSourceContentPanel() {
  const idBadge = document.getElementById('activeAuditIdBadge');
  const metaEl = document.getElementById('sourcePanelMetadata');
  const viewer = document.getElementById('sourceContentViewer');

  if (!AppState.currentAudit) return;

  const audit = AppState.currentAudit;
  const revCount = (audit.revisions || []).length || 1;
  idBadge.textContent = `${audit.id} · v${revCount}`;

  const isIdentical = audit.original_content === audit.current_content;
  const versionLabel = AppState.sourceViewMode === 'working'
    ? (isIdentical ? 'Working copy (no edits yet)' : `Revised working copy (v${revCount})`)
    : 'Original submitted snapshot (v1)';

  metaEl.innerHTML = `
    <strong>${escapeHtml(versionLabel)}</strong> &bull;
    Format: <span class="mono-id">${escapeHtml(audit.input_format)}</span>
  `;

  const text = AppState.sourceViewMode === 'working' ? audit.current_content : audit.original_content;
  const activeFindings = (audit.findings || []).filter(
    (f) =>
      AppState.sourceViewMode === 'working' &&
      ['open', 'needs_review'].includes(f.review_state) &&
      f.start_index >= 0 &&
      f.end_index > f.start_index &&
      f.end_index <= text.length
  );

  viewer.classList.toggle('raw-source-mode', AppState.sourceFormatView === 'source');
  if (audit.visual_metadata && Array.isArray(audit.visual_metadata.cells)) {
    const docHtml = renderSafeDocumentHtml(
      text,
      activeFindings,
      AppState.selectedFindingId,
      AppState.sourceFormatView
    );
    renderVisualHeatmapInspector(viewer, audit, docHtml);
    return;
  }
  viewer.innerHTML = renderSafeDocumentHtml(
    text,
    activeFindings,
    AppState.selectedFindingId,
    AppState.sourceFormatView
  );

  viewer.querySelectorAll('.source-highlight').forEach((mark) => {
    mark.addEventListener('click', () => {
      AppState.selectedFindingId = mark.getAttribute('data-finding-id');
      renderSourceContentPanel();
      renderFindingsCenterPanel();
      renderCorrectionRightPanel();
      scrollRailToSelectedFinding();
    });
  });
}

function scrollSourceToSelectedFinding() {
  const viewer = document.getElementById('sourceContentViewer');
  if (!viewer || !AppState.selectedFindingId) return;
  const activeMark = viewer.querySelector(`.source-highlight.selected-span, .source-highlight[data-finding-id="${AppState.selectedFindingId}"]`);
  if (activeMark) {
    activeMark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    activeMark.focus?.();
  }
}

function scrollRailToSelectedFinding() {
  const container = document.getElementById('findingsListContainer');
  if (!container || !AppState.selectedFindingId) return;
  const activeCard = container.querySelector(`.finding-rail-card[data-finding-id="${AppState.selectedFindingId}"]`);
  if (activeCard) {
    activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function selectFindingByIndex(index) {
  if (!AppState.currentAudit || !AppState.currentAudit.findings) return;
  const list = AppState.currentAudit.findings;
  if (index < 0 || index >= list.length) return;
  AppState.selectedFindingId = list[index].id;
  renderSourceContentPanel();
  renderFindingsCenterPanel();
  renderCorrectionRightPanel();
  scrollSourceToSelectedFinding();
  scrollRailToSelectedFinding();
}

function handleResultsKeyNavigation(e) {
  // Ignore any key event with Ctrl, Meta, or Alt held (e.g., Ctrl+A selects text, Ctrl+K only opens palette)
  if (e.ctrlKey || e.metaKey || e.altKey) {
    return;
  }
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable) {
    return;
  }
  const modal = document.getElementById('commandPaletteModal');
  if (modal && modal.style.display !== 'none') {
    return;
  }
  const dialogRoot = document.getElementById('modalRoot');
  if (dialogRoot && dialogRoot.style.display !== 'none') {
    return;
  }
  if (AppState.activeView !== 'new-audit' || AppState.auditStage !== 'results' || !AppState.currentAudit) {
    return;
  }

  const findings = (AppState.currentAudit.findings || []);
  if (findings.length === 0) return;

  const key = e.key.toLowerCase();
  const currentIndex = findings.findIndex((f) => f.id === AppState.selectedFindingId);

  if (key === 'j' || key === 'arrowdown') {
    e.preventDefault();
    const nextIdx = (currentIndex >= 0 && currentIndex < findings.length - 1) ? currentIndex + 1 : 0;
    selectFindingByIndex(nextIdx);
  } else if (key === 'k' || key === 'arrowup') {
    e.preventDefault();
    const prevIdx = (currentIndex > 0) ? currentIndex - 1 : findings.length - 1;
    selectFindingByIndex(prevIdx);
  } else if (key === 'a') {
    // Act ONLY on an explicitly selected finding (never default to the first)
    if (currentIndex < 0) return;
    const curr = findings[currentIndex];
    if (curr && curr.suggested_correction && !['accepted', 'modified', 'dismissed'].includes(curr.review_state)) {
      e.preventDefault();
      submitFindingDecision(curr.id, { decision: 'accept', reviewer_role: AppState.activeRole });
    }
  } else if (key === 'd') {
    // Act ONLY on an explicitly selected finding (never default to the first)
    if (currentIndex < 0) return;
    const curr = findings[currentIndex];
    if (curr && !['accepted', 'modified', 'dismissed'].includes(curr.review_state)) {
      e.preventDefault();
      const box = document.getElementById(`dismissBox_${curr.id}`);
      if (box) {
        box.style.display = 'block';
        document.getElementById(`dismissInput_${curr.id}`)?.focus();
      }
    }
  }
}

function renderFindingsCenterPanel() {
  const container = document.getElementById('findingsListContainer');
  const countBadge = document.getElementById('findingsCountBadge');
  if (!AppState.currentAudit) return;

  const allFindings = AppState.currentAudit.findings || [];
  const q = AppState.findingSearchQuery;

  const filtered = allFindings.filter((f) => {
    // Always keep the currently selected finding visible so filters never hide the active review item
    if (f.id === AppState.selectedFindingId) return true;
    if (AppState.selectedPillarFilter !== 'ALL' && f.pillar !== AppState.selectedPillarFilter) return false;
    if (AppState.selectedSeverityFilter !== 'ALL' && f.severity !== AppState.selectedSeverityFilter) return false;
    if (AppState.selectedStatusFilter !== 'ALL' && f.review_state !== AppState.selectedStatusFilter) return false;
    if (q) {
      const hay = `${f.id} ${f.issue_type} ${f.flagged_text} ${f.explanation} ${f.rule_or_fact_id}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  countBadge.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${filtered.length} of ${allFindings.length} finding(s)</span>`;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <h3>No findings match the current filter</h3>
        <p>${allFindings.length === 0
          ? 'All checked pillars passed without violations.'
          : 'Clear the pillar, severity, or status filters above to view all findings.'}</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map((f) => {
    const isSelected = f.id === AppState.selectedFindingId;
    const spanText = f.start_index >= 0
      ? `Paragraph ${escapeHtml(f.paragraph_ref.replace(/^P/, ''))}, characters ${f.start_index}–${f.end_index}`
      : `${escapeHtml(f.paragraph_ref)}`;
    
    // Label similarity strictly as "retrieval similarity (cosine, 0-1)" (never probability/confidence)
    const simHtml = (f.similarity_score !== null && f.similarity_score !== undefined)
      ? `<div style="margin-top: 4px;"><strong>retrieval similarity (cosine, 0-1):</strong> <span class="mono-id">${Number(f.similarity_score).toFixed(2)}</span> <span style="font-size: 11.5px; color: var(--slate-700);">(topical retrieval similarity, not factual truth probability)</span></div>`
      : '';

    const hasSuggested = Boolean(f.suggested_correction && f.suggested_correction.trim());
    const isResolved = ['accepted', 'modified', 'dismissed'].includes(f.review_state);

    return `
      <div class="finding-rail-card ${isSelected ? 'selected' : ''}" data-finding-id="${escapeHtml(f.id)}" tabindex="0" role="region" aria-label="Finding ${escapeHtml(f.id)}: ${escapeHtml(f.issue_type)}">
        <div class="finding-card-top" style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span class="mono-id" style="font-weight: 600;">${escapeHtml(f.pillar)}</span>
            ${renderStateBadge(f.severity)}
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            ${renderStateBadge(f.review_state)}
            <button type="button" class="id-chip copy-id-chip" data-copy-text="${escapeHtml(f.id)}" title="Copy finding ID">${escapeHtml(f.id)}</button>
          </div>
        </div>

        <div class="finding-issue-title" style="font-size: 14px; font-weight: 700; color: var(--primary-ink); margin-top: 2px;">
          ${escapeHtml(f.issue_type)}
        </div>

        <div class="finding-excerpt-box">
          "${escapeHtml(f.flagged_text)}"
        </div>

        <div class="finding-explanation-text">
          ${escapeHtml(f.explanation)}
        </div>

        <div class="evidence-box" style="background: var(--slate-50); border: 1px solid var(--border-color); border-radius: var(--radius-control); padding: 10px 12px; font-size: 12.5px;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <strong>Cited rule/fact:</strong>
            <button type="button" class="id-chip copy-id-chip" data-copy-text="${escapeHtml(f.rule_or_fact_id)}" title="Copy rule/fact ID">${escapeHtml(f.rule_or_fact_id)}</button>
          </div>
          <div><strong>Evidence / source:</strong> ${escapeHtml(f.source_evidence)}</div>
        </div>

        <!-- Technical detection details -->
        <details class="collapsible-details" style="font-size: 12px;">
          <summary style="cursor: pointer; color: var(--slate-600); font-weight: 500;">Technical detection details</summary>
          <div class="collapsible-details-body" style="padding-top: 8px; color: var(--slate-700); line-height: 1.5;">
            <div><strong>Location:</strong> ${spanText}</div>
            <div style="margin-top: 2px;"><strong>Detection method:</strong> ${escapeHtml(f.detection_method)}</div>
            <div style="margin-top: 2px;"><strong>Engine tier:</strong> ${escapeHtml(f.engine_source)}</div>
            ${simHtml}
          </div>
        </details>

        <!-- What the system does NOT know (Honest disclosure boundary) -->
        <div class="honest-boundary-notice">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <div>
            <strong>What the system does not know:</strong>
            Deterministic &amp; lexical checks verify text against active guidelines. The engine cannot infer external trademark licenses, context parody, or signed contractual agreements superseding standard guidelines.
          </div>
        </div>

        <!-- Suggested fix preview -->
        ${hasSuggested ? `
          <div style="font-size: 12.5px; padding: 8px 10px; background: var(--status-success-bg); border: 1px solid var(--status-success-border); border-radius: var(--radius-control); color: var(--slate-800);">
            <strong>Suggested fix:</strong> "${escapeHtml(f.suggested_correction)}"
          </div>
        ` : ''}

        <!-- Direct Actions on finding card -->
        <div class="finding-card-actions-row">
          <button type="button" class="btn btn-sm btn-accent direct-accept-btn" data-finding-id="${escapeHtml(f.id)}" ${(!hasSuggested || isResolved) ? 'disabled' : ''} title="${!hasSuggested ? 'No automated suggestion available; click Edit fix' : 'Accept verified correction'}">
            Accept fix
          </button>
          <button type="button" class="btn btn-sm btn-ghost direct-edit-toggle-btn" data-finding-id="${escapeHtml(f.id)}" style="border: 1px solid var(--border-color);" ${isResolved ? 'disabled' : ''}>
            Edit fix
          </button>
          <button type="button" class="btn btn-sm btn-danger-outline direct-dismiss-toggle-btn" data-finding-id="${escapeHtml(f.id)}" ${isResolved ? 'disabled' : ''}>
            Dismiss
          </button>
          <button type="button" class="btn btn-sm btn-ghost direct-review-btn" data-finding-id="${escapeHtml(f.id)}" style="color: var(--slate-600);" ${f.review_state === 'needs_review' ? 'disabled' : ''}>
            Mark for human review
          </button>
        </div>

        <!-- Expandable Edit Form -->
        <div class="inline-edit-box" id="editBox_${escapeHtml(f.id)}" style="display: none; padding-top: 10px; border-top: 1px dashed var(--border-color);">
          <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">Custom replacement text:</label>
          <textarea class="form-control inline-edit-textarea" id="editTextarea_${escapeHtml(f.id)}" rows="2" style="font-size: 13px; margin-bottom: 8px;">${escapeHtml(f.suggested_correction || f.flagged_text)}</textarea>
          <div style="display: flex; gap: 6px;">
            <button type="button" class="btn btn-sm btn-accent save-custom-edit-btn" data-finding-id="${escapeHtml(f.id)}">Apply edit</button>
            <button type="button" class="btn btn-sm btn-ghost cancel-custom-edit-btn" data-finding-id="${escapeHtml(f.id)}">Cancel</button>
          </div>
        </div>

        <!-- Expandable Dismiss Form -->
        <div class="inline-dismiss-box" id="dismissBox_${escapeHtml(f.id)}" style="display: none; padding-top: 10px; border-top: 1px dashed var(--border-color);">
          <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">Reason for dismissal (required):</label>
          <input type="text" class="form-control inline-dismiss-input" id="dismissInput_${escapeHtml(f.id)}" placeholder="e.g., Campaign disclaimer approved by legal counsel" value="${escapeHtml(f.decision_note || '')}" style="font-size: 13px; margin-bottom: 8px;" />
          <div style="display: flex; gap: 6px;">
            <button type="button" class="btn btn-sm btn-danger-outline confirm-dismiss-btn" data-finding-id="${escapeHtml(f.id)}">Confirm dismissal</button>
            <button type="button" class="btn btn-sm btn-ghost cancel-dismiss-btn" data-finding-id="${escapeHtml(f.id)}">Cancel</button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Wire card click selection
  container.querySelectorAll('.finding-rail-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea') || e.target.closest('details')) {
        return;
      }
      AppState.selectedFindingId = card.getAttribute('data-finding-id');
      renderSourceContentPanel();
      renderFindingsCenterPanel();
      renderCorrectionRightPanel();
      scrollSourceToSelectedFinding();
    });
  });

  // Wire direct action buttons
  container.querySelectorAll('.direct-accept-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      await submitFindingDecision(findingId, {
        decision: 'accept',
        reviewer_role: AppState.activeRole,
      });
    });
  });

  container.querySelectorAll('.direct-edit-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const box = document.getElementById(`editBox_${findingId}`);
      if (box) {
        box.style.display = box.style.display === 'none' ? 'block' : 'none';
        if (box.style.display === 'block') {
          document.getElementById(`editTextarea_${findingId}`)?.focus();
        }
      }
    });
  });

  container.querySelectorAll('.save-custom-edit-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const customText = document.getElementById(`editTextarea_${findingId}`).value.trim();
      if (!customText) {
        showToast('Enter replacement text before applying an edited suggestion.');
        return;
      }
      await submitFindingDecision(findingId, {
        decision: 'modify',
        modified_replacement: customText,
        reviewer_role: AppState.activeRole,
      });
    });
  });

  container.querySelectorAll('.cancel-custom-edit-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const box = document.getElementById(`editBox_${findingId}`);
      if (box) box.style.display = 'none';
    });
  });

  container.querySelectorAll('.direct-dismiss-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const box = document.getElementById(`dismissBox_${findingId}`);
      if (box) {
        box.style.display = box.style.display === 'none' ? 'block' : 'none';
        if (box.style.display === 'block') {
          document.getElementById(`dismissInput_${findingId}`)?.focus();
        }
      }
    });
  });

  container.querySelectorAll('.confirm-dismiss-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const reason = document.getElementById(`dismissInput_${findingId}`).value.trim();
      if (!reason) {
        showToast('A written reason is required to dismiss a finding.');
        return;
      }
      await submitFindingDecision(findingId, {
        decision: 'dismiss',
        reason: reason,
        reviewer_role: AppState.activeRole,
      });
    });
  });

  container.querySelectorAll('.cancel-dismiss-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      const box = document.getElementById(`dismissBox_${findingId}`);
      if (box) box.style.display = 'none';
    });
  });

  container.querySelectorAll('.direct-review-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const findingId = btn.getAttribute('data-finding-id');
      await submitFindingDecision(findingId, {
        decision: 'needs_review',
        reason: 'Marked for human review by team',
        reviewer_role: AppState.activeRole,
      });
    });
  });
}

function updateWorkspaceApprovalGuard() {
  if (!AppState.currentAudit) return;
  const audit = AppState.currentAudit;
  const openCount = audit.open_findings_count ?? (audit.findings || []).filter((f) => ['open', 'needs_review'].includes(f.review_state)).length;
  const approveBtn = document.getElementById('workspaceApproveBtn');
  const overrideCheck = document.getElementById('workflowOverrideCheckbox');
  const commentInput = document.getElementById('workflowCommentInput');
  const noticeEl = document.getElementById('workflowUnresolvedNotice');
  const overrideRow = document.getElementById('workflowOverrideRow');

  if (!approveBtn) return;

  const historicalSubmitterIds = new Set();
  if (audit.submitted_by_user_id) {
    historicalSubmitterIds.add(audit.submitted_by_user_id);
  }
  (audit.approvals || []).forEach((ap) => {
    if (ap.new_state === 'In Review' && ap.approver_user_id) {
      historicalSubmitterIds.add(ap.approver_user_id);
    }
  });

  if (AppState.demoMode && historicalSubmitterIds.size > 0 && !AppState.userId) {
    overrideRow.style.display = openCount > 0 ? 'flex' : 'none';
    const signMsg = 'Sign in as a demo user to approve this audit.';
    noticeEl.innerHTML = `<span style="color: var(--status-error); font-weight: 600;">${escapeHtml(signMsg)}</span>`;
    approveBtn.disabled = true;
    approveBtn.title = signMsg;
    return;
  }

  const isSubmitter = Boolean(
    AppState.demoMode &&
    AppState.userId &&
    historicalSubmitterIds.has(AppState.userId)
  );

  if (isSubmitter) {
    overrideRow.style.display = openCount > 0 ? 'flex' : 'none';
    const submitterLabel = audit.submitted_by_name || AppState.userName || AppState.userId;
    const sodMsg = `Separation of duties: ${submitterLabel} submitted this audit for review and cannot approve it. Sign in as a different Reviewer or Brand Administrator to approve.`;
    noticeEl.innerHTML = `<span style="color: var(--status-error); font-weight: 600;">${escapeHtml(sodMsg)}</span>`;
    approveBtn.disabled = true;
    approveBtn.title = sodMsg;
    return;
  }

  const submittedInfoHtml = audit.submitted_by_name
    ? `<div style="margin-bottom: 4px; color: var(--text-secondary);">Submitted for review by: <strong>${escapeHtml(audit.submitted_by_name)}</strong></div>`
    : '';

  if (openCount === 0) {
    overrideRow.style.display = 'none';
    noticeEl.innerHTML = `${submittedInfoHtml}<span style="color: var(--status-success); font-weight: 600;">All findings are resolved. Document is ready for Reviewer approval.</span>`;
    approveBtn.disabled = false;
    approveBtn.title = 'Approve document for publication';
  } else {
    overrideRow.style.display = 'flex';
    const canOverride = overrideCheck.checked && commentInput.value.trim().length > 0;
    noticeEl.innerHTML = `${submittedInfoHtml}<span style="color: var(--status-error); font-weight: 600;">${openCount} unresolved finding(s) remain.</span> Resolve all findings first, or record an authorised override with a mandatory written justification.`;
    approveBtn.disabled = !canOverride;
    approveBtn.title = canOverride
      ? 'Approve with authorised override'
      : 'Disabled until all findings are resolved or an authorised override justification is entered';
  }
}

function renderCorrectionRightPanel() {
  const body = document.getElementById('correctionPanelBody');
  const wfBox = document.getElementById('workflowTransitionBox');
  const wfBadge = document.getElementById('activeWorkflowStateBadge');

  clearInlineError(document.getElementById('findingDecisionErrorBanner'));
  clearInlineError(document.getElementById('workflowErrorBanner'));

  if (!AppState.currentAudit) {
    wfBox.style.display = 'none';
    return;
  }

  wfBox.style.display = 'block';
  const audit = AppState.currentAudit;
  wfBadge.innerHTML = renderStateBadge(audit.overall_status);
  updateWorkspaceApprovalGuard();

  const finding = (audit.findings || []).find((f) => f.id === AppState.selectedFindingId);
  if (!finding) {
    body.innerHTML = `
      <div class="empty-state-box">
        <h3>Select a finding</h3>
        <p>Select any highlighted phrase in the document or any finding card to review its suggested fix.</p>
      </div>
    `;
    return;
  }

  const hasSuggested = Boolean(finding.suggested_correction && finding.suggested_correction.trim());
  const proposedText = hasSuggested
    ? finding.suggested_correction
    : 'No verified replacement found. Verify the claim or edit manually below.';

  body.innerHTML = `
    <div style="margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
      <span class="mono-id">${escapeHtml(finding.id)} · ${escapeHtml(finding.rule_or_fact_id)}</span>
      ${renderStateBadge(finding.review_state)}
    </div>

    <div class="diff-comparison-grid">
      <div class="diff-pane diff-before">
        <span class="diff-pane-label">Original</span>
        <div>${escapeHtml(finding.flagged_text)}</div>
      </div>
      <div class="diff-pane ${hasSuggested ? 'diff-after' : 'diff-neutral'}">
        <span class="diff-pane-label">Suggested action</span>
        <div>${escapeHtml(proposedText)}</div>
      </div>
    </div>

    <div class="form-group" style="margin-bottom: 12px;">
      <label for="modifySuggestionInput">Edit replacement text</label>
      <textarea id="modifySuggestionInput" class="form-control" style="min-height: 76px;">${escapeHtml(finding.suggested_correction || finding.flagged_text)}</textarea>
    </div>

    <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
      <button type="button" class="btn btn-accent" id="acceptCorrectionBtn" ${!hasSuggested ? 'disabled title="No automated suggestion available; use Edit suggestion below"' : ''}>
        Accept correction
      </button>
      <button type="button" class="btn" id="modifyCorrectionBtn">
        Apply edited suggestion
      </button>
    </div>

    <div style="padding-top: 12px; border-top: 1px solid var(--border-color);">
      <div class="form-group" style="margin-bottom: 8px;">
        <label for="dismissReasonInput">Dismiss with reason (required for dismissal)</label>
        <input type="text" id="dismissReasonInput" class="form-control" placeholder="Explain channel exception or context..." value="${escapeHtml(finding.decision_note || '')}" />
      </div>
      <button type="button" class="btn btn-danger-outline btn-sm" id="dismissFindingBtn" style="width: 100%;">Dismiss with reason</button>
    </div>
  `;

  document.getElementById('acceptCorrectionBtn').addEventListener('click', async () => {
    await submitFindingDecision(finding.id, {
      decision: 'accept',
      reviewer_role: AppState.activeRole,
    });
  });

  document.getElementById('modifyCorrectionBtn').addEventListener('click', async () => {
    const customText = document.getElementById('modifySuggestionInput').value.trim();
    if (!customText) {
      showToast('Enter replacement text before applying an edited suggestion.');
      return;
    }
    await submitFindingDecision(finding.id, {
      decision: 'modify',
      modified_replacement: customText,
      reviewer_role: AppState.activeRole,
    });
  });

  document.getElementById('dismissFindingBtn').addEventListener('click', async () => {
    const reason = document.getElementById('dismissReasonInput').value.trim();
    if (!reason) {
      showToast('A written reason is required to dismiss a finding.');
      return;
    }
    await submitFindingDecision(finding.id, {
      decision: 'dismiss',
      reason: reason,
      reviewer_role: AppState.activeRole,
    });
  });
}

async function submitFindingDecision(findingId, payload) {
  if (!AppState.currentAudit) return;
  const errBanner = document.getElementById('findingDecisionErrorBanner');
  clearInlineError(errBanner);
  if (!AppState.sessionAvailable) {
    showInlineError(errBanner, 'Cannot save decision: server session is unavailable.');
    return;
  }
  try {
    const updated = await apiFetch(
      `/api/audits/${encodeURIComponent(AppState.currentAudit.id)}/findings/${encodeURIComponent(findingId)}/decision`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
    AppState.currentAudit = updated;
    const nextOpen = (updated.findings || []).find((f) => ['open', 'needs_review'].includes(f.review_state));
    if (nextOpen) {
      AppState.selectedFindingId = nextOpen.id;
    }
    renderAuditWorkspace();
    await refreshOverview();
    showToast(`Saved ${payload.decision} decision for ${findingId}.`);
  } catch (err) {
    showInlineError(errBanner, `Could not save decision: ${err.message}`, () => submitFindingDecision(findingId, payload));
    showToast(`Could not save decision: ${err.message}`);
  }
}

async function transitionCurrentAuditWorkflow(newState) {
  if (!AppState.currentAudit) return;
  const errBanner = document.getElementById('workflowErrorBanner');
  clearInlineError(errBanner);
  if (!AppState.sessionAvailable) {
    showInlineError(errBanner, 'Cannot update workflow state: server session is unavailable.');
    return;
  }
  const comment = document.getElementById('workflowCommentInput').value.trim();
  const overrideAck = document.getElementById('workflowOverrideCheckbox').checked;

  try {
    const updated = await apiFetch(`/api/audits/${encodeURIComponent(AppState.currentAudit.id)}/workflow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_state: newState,
        approver_role: AppState.activeRole,
        comment: comment,
        override_acknowledged: overrideAck,
      }),
    });
    AppState.currentAudit = updated;
    renderAuditWorkspace();
    await refreshOverview();
    showToast(`Audit ${updated.id} status saved as "${newState}".`);
  } catch (err) {
    showInlineError(errBanner, `Approval safeguard: ${err.message}`, () => transitionCurrentAuditWorkflow(newState));
    showToast(`Approval safeguard: ${err.message}`);
  }
}

// ============================================================================
// VIEW 3: BRAND VAULT (SECTION 06 — 5 SHORT TABS, COLLAPSED ADD FORMS)
// ============================================================================

function bindBrandVaultEvents() {
  document.querySelectorAll('.tab-btn[data-vault-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!confirmDiscardUnsavedChanges()) return;
      AppState.activeVaultTab = btn.getAttribute('data-vault-tab');
      document.querySelectorAll('.tab-btn[data-vault-tab]').forEach((b) => {
        b.classList.toggle('active', b === btn);
      });
      renderBrandVaultTab();
    });
  });

  const searchInput = document.getElementById('vaultSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      AppState.vaultSearchQuery = e.target.value.trim().toLowerCase();
      renderBrandVaultTab();
    });
  }

  const scopeEl = document.getElementById('vaultSearchScope');
  if (scopeEl) {
    scopeEl.addEventListener('change', (e) => {
      AppState.vaultSearchScope = e.target.value;
      renderBrandVaultTab();
    });
  }

  const redoBtn = document.getElementById('vaultRedoSetupBtn');
  if (redoBtn && !redoBtn._bound) {
    redoBtn._bound = true;
    redoBtn.addEventListener('click', () => {
      if (!confirmDiscardUnsavedChanges()) return;
      AppState.auditStage = 'input';
      AppState.wizardMode = true;
      AppState.wizardStep = 1;
      switchView('new-audit');
    });
  }
}

function updateVaultSetupChip() {
  const lbl = document.getElementById('vaultSetupChipLabel');
  if (!lbl) return;
  if (AppState.vaultData && AppState.vaultData.brand) {
    const b = AppState.vaultData.brand;
    if (b.id && b.id.startsWith('profile_')) {
      lbl.textContent = b.name;
    } else if (b.industry) {
      lbl.textContent = `${b.name} (${b.industry})`;
    } else {
      lbl.textContent = b.name;
    }
  } else if (AppState.wizardAnswers) {
    const wa = AppState.wizardAnswers;
    const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
    lbl.textContent = `${capitalize(wa.industry)} (${wa.locale || 'Global'}, ${capitalize(wa.tone)})`;
  }
}

async function refreshBrandVaultDataOnly() {
  try {
    AppState.vaultData = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}`);
    AppState.lastRefreshed.vault = new Date().toISOString();
    AppState.vaultError = null;
  } catch (err) {
    AppState.vaultData = null;
    AppState.vaultError = err;
    throw err;
  }
}

async function refreshBrandVault() {
  const container = document.getElementById('vaultTabContent');
  if (container && !AppState.vaultData) {
    container.innerHTML = '<div class="card" style="padding: 32px; text-align: center; color: var(--text-secondary);">Loading Brand Vault guidelines...</div>';
  }
  try {
    await refreshBrandVaultDataOnly();
    renderBrandVaultTab();
  } catch (err) {
    renderBrandVaultTab();
  }
}

function renderBrandVaultTab() {
  const container = document.getElementById('vaultTabContent');
  if (AppState.vaultError && !AppState.vaultData) {
    const action = getApiErrorAction(AppState.vaultError);
    const lastTime = AppState.lastRefreshed.vault ? formatTimestamp(AppState.lastRefreshed.vault) : 'Never';
    container.innerHTML = `
      <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
        <h3 style="color: #B42318;">Could not retrieve Brand Vault guidelines</h3>
        <p style="color: #475467;">${escapeHtml(AppState.vaultError.message)}</p>
        ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
        ${AppState.vaultError.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(AppState.vaultError.requestId)}</div>` : ''}
        <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
        <button type="button" class="btn btn-sm btn-accent" id="retryVaultBtn" style="margin-top: 12px;">Retry</button>
      </div>
    `;
    const retryBtn = document.getElementById('retryVaultBtn');
    if (retryBtn) retryBtn.addEventListener('click', () => refreshBrandVault());
    return;
  }

  if (!AppState.vaultData) {
    container.innerHTML = '<div class="card" style="padding: 32px; text-align: center; color: var(--text-secondary);">Loading Brand Vault...</div>';
    return;
  }

  updateVaultSetupChip();

  // If user searches with "Search all Brand Vault" scope and a query is entered, show unified results banner
  const q = AppState.vaultSearchQuery;
  if (q && AppState.vaultSearchScope === 'all') {
    renderVaultGlobalSearchResults(container, q);
    return;
  }

  const tab = AppState.activeVaultTab;
  if (tab === 'voice') renderVaultVoiceTab(container);
  else if (tab === 'terminology') renderVaultTerminologyTab(container);
  else if (tab === 'facts') renderVaultFactsTab(container);
  else if (tab === 'visual') renderVaultVisualTab(container);
  else if (tab === 'accessibility') renderVaultAccessibilityTab(container);
}

function renderVaultGlobalSearchResults(container, q) {
  const rules = (AppState.vaultData.rules || []).filter((r) => `${r.id} ${r.title} ${r.description} ${r.pillar}`.toLowerCase().includes(q));
  const terms = (AppState.vaultData.terminology || []).filter((t) => `${t.id} ${t.prohibited_term} ${t.replacement_term} ${t.notes}`.toLowerCase().includes(q));
  const facts = (AppState.vaultData.verified_facts || []).filter((f) => `${f.id} ${f.statement} ${f.source_reference}`.toLowerCase().includes(q));
  const colors = (AppState.vaultData.colors || []).filter((c) => `${c.id} ${c.name} ${c.hex_code} ${c.usage_role}`.toLowerCase().includes(q));

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">All Brand Vault matches for "${escapeHtml(q)}"</h2>
        <span class="status-badge badge-neutral"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${rules.length + terms.length + facts.length + colors.length} match(es)</span></span>
      </div>
      <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
        Matches across Rules (${rules.length}), Terminology (${terms.length}), Verified facts (${facts.length}), and Visual tokens (${colors.length}). Switch search scope to "Search active tab" to edit records in place.
      </p>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Section</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            ${rules.map((r) => `<tr><td class="nowrap-col"><span class="mono-id">${escapeHtml(r.id)}</span></td><td>Voice &amp; rules</td><td><strong>${escapeHtml(r.title)}</strong> — ${escapeHtml(r.description)}</td></tr>`).join('')}
            ${terms.map((t) => `<tr><td class="nowrap-col"><span class="mono-id">${escapeHtml(t.id)}</span></td><td>Terminology</td><td>Replace <strong>${escapeHtml(t.prohibited_term)}</strong> with <strong>${escapeHtml(t.replacement_term)}</strong></td></tr>`).join('')}
            ${facts.map((f) => `<tr><td class="nowrap-col"><span class="mono-id">${escapeHtml(f.id)}</span></td><td>Verified facts</td><td>${escapeHtml(f.statement)} (${escapeHtml(f.verification_status)})</td></tr>`).join('')}
            ${colors.map((c) => `<tr><td class="nowrap-col"><span class="mono-id">${escapeHtml(c.id)}</span></td><td>Visual identity</td><td>${escapeHtml(c.name)} (${escapeHtml(c.hex_code)})</td></tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderVaultVoiceTab(container) {
  const b = AppState.vaultData.brand;
  const q = AppState.vaultSearchQuery;
  const rules = (AppState.vaultData.rules || []).filter((r) =>
    !q ||
    r.id.toLowerCase().includes(q) ||
    r.title.toLowerCase().includes(q) ||
    r.description.toLowerCase().includes(q) ||
    r.pillar.toLowerCase().includes(q)
  );

  const formOpen = AppState.vaultFormOpen.rule;

  container.innerHTML = `
    <div class="card" style="margin-bottom: 20px;">
      <div class="card-header">
        <div>
          <h2 class="card-title">Voice, tone &amp; messaging profile (v${b.version})</h2>
          ${b.is_demo ? '<span class="status-badge badge-warning" style="margin-top: 4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>Demo profile</span></span>' : ''}
        </div>
        <button type="button" class="btn btn-accent btn-sm" id="saveVoiceProfileBtn">Save voice profile</button>
      </div>
      <div class="input-form-grid" style="grid-template-columns: 1fr 1fr;">
        <div class="form-group">
          <label for="vaultVoiceDesc">Brand description</label>
          <textarea id="vaultVoiceDesc" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.description)}</textarea>
        </div>
        <div class="form-group">
          <label for="vaultVoiceTone">Tone principles</label>
          <textarea id="vaultVoiceTone" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.tone_principles)}</textarea>
        </div>
        <div class="form-group">
          <label for="vaultVoiceStyle">Writing style guidelines</label>
          <textarea id="vaultVoiceStyle" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.writing_style)}</textarea>
        </div>
        <div class="form-group">
          <label for="vaultVoiceMsg">Messaging principles</label>
          <textarea id="vaultVoiceMsg" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.messaging_principles)}</textarea>
        </div>
        <div class="form-group">
          <label for="vaultVoiceDo">Approved "Do" examples (one per line)</label>
          <textarea id="vaultVoiceDo" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml((b.do_examples_list || []).join('\n'))}</textarea>
        </div>
        <div class="form-group">
          <label for="vaultVoiceDont">Disallowed "Don't" examples (one per line)</label>
          <textarea id="vaultVoiceDont" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml((b.dont_examples_list || []).join('\n'))}</textarea>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Brand governance rules (${rules.length})</h2>
        <button type="button" class="btn btn-sm ${formOpen ? '' : 'btn-accent'}" id="toggleRuleFormBtn">
          ${formOpen ? 'Close form' : '+ Add rule'}
        </button>
      </div>

      <!-- Collapsed by default Add / Edit Rule Form -->
      <div id="ruleFormDrawer" style="display: ${formOpen ? 'block' : 'none'}; background: var(--bg-main); padding: 16px; border-radius: var(--radius-sm); margin-bottom: 16px; border: 1px solid var(--border-color);">
        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;" id="ruleFormHeading">Add brand rule</h3>
        <input type="hidden" id="editRuleIdInput" value="" />
        <div class="input-form-grid">
          <div class="form-group">
            <label for="newRulePillar">Audit pillar</label>
            <select id="newRulePillar" class="form-control">
              ${SIX_PILLARS.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label for="newRuleTitle">Rule title</label>
            <input type="text" id="newRuleTitle" class="form-control" placeholder="e.g., Avoid unqualified superlatives" />
          </div>
          <div class="form-group">
            <label for="newRuleSeverity">Severity</label>
            <select id="newRuleSeverity" class="form-control">
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
        </div>
        <div class="input-form-grid" style="grid-template-columns: 2fr 1fr;">
          <div class="form-group">
            <label for="newRuleDesc">Rule guidance</label>
            <input type="text" id="newRuleDesc" class="form-control" placeholder="Explain how writers should comply with this rule..." />
          </div>
          <div class="form-group">
            <label for="newRuleRegex">Detection pattern (optional regex)</label>
            <input type="text" id="newRuleRegex" class="form-control" placeholder="e.g., \\b(?:guaranteed|100%\\s+safe)\\b" />
          </div>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button type="button" class="btn btn-sm" id="cancelEditRuleBtn">Cancel</button>
          <button type="button" class="btn btn-accent btn-sm" id="submitRuleBtn">Save rule</button>
        </div>
      </div>

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Rule ID</th>
              <th>Rule title</th>
              <th>Pillar</th>
              <th>Severity</th>
              <th>Version</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${rules.map((r) => `
              <tr>
                <td class="nowrap-col"><span class="mono-id">${escapeHtml(r.id)}</span></td>
                <td>
                  <strong>${escapeHtml(r.title)}</strong>
                  <details class="collapsible-details" style="border-top: none; padding-top: 4px; margin-top: 2px;">
                    <summary>Guidance &amp; examples</summary>
                    <div class="collapsible-details-body">
                      <div>${escapeHtml(r.description)}</div>
                      ${r.do_example ? `<div style="margin-top: 4px;"><strong>Do:</strong> "${escapeHtml(r.do_example)}"</div>` : ''}
                      ${r.dont_example ? `<div style="margin-top: 2px;"><strong>Don't:</strong> "${escapeHtml(r.dont_example)}"</div>` : ''}
                    </div>
                  </details>
                </td>
                <td class="nowrap-col">${escapeHtml(r.pillar)}</td>
                <td class="nowrap-col">${renderStateBadge(r.severity)}</td>
                <td class="nowrap-col"><span class="mono-id">v${r.version}</span></td>
                <td class="nowrap-col">
                  <div style="display: flex; gap: 6px;">
                    <button type="button" class="btn btn-sm edit-rule-btn" data-id="${escapeHtml(r.id)}">Edit</button>
                    <button type="button" class="btn btn-sm btn-danger-outline delete-rule-btn" data-id="${escapeHtml(r.id)}">Delete</button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  container.querySelectorAll('.vault-watch').forEach((el) => {
    el.addEventListener('input', () => setUnsavedVaultChanges(true));
  });

  document.getElementById('toggleRuleFormBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.rule = !AppState.vaultFormOpen.rule;
    renderBrandVaultTab();
  });

  document.getElementById('cancelEditRuleBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.rule = false;
    renderBrandVaultTab();
  });

  document.getElementById('saveVoiceProfileBtn').addEventListener('click', async () => {
    const desc = document.getElementById('vaultVoiceDesc').value.trim();
    const tone = document.getElementById('vaultVoiceTone').value.trim();
    const style = document.getElementById('vaultVoiceStyle').value.trim();
    const msg = document.getElementById('vaultVoiceMsg').value.trim();
    if (desc.length < 5 || tone.length < 5 || style.length < 5 || msg.length < 5) {
      showToast('All voice profile fields must contain at least 5 characters.');
      return;
    }
    try {
      AppState.vaultData = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/voice`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: desc,
          tone_principles: tone,
          writing_style: style,
          messaging_principles: msg,
          do_examples: document.getElementById('vaultVoiceDo').value.split('\n').map((s) => s.trim()).filter(Boolean),
          dont_examples: document.getElementById('vaultVoiceDont').value.split('\n').map((s) => s.trim()).filter(Boolean),
        }),
      });
      setUnsavedVaultChanges(false);
      await loadBrandsAndInit();
      renderBrandVaultTab();
      showToast(`Saved voice profile for ${AppState.vaultData.brand.name} (v${AppState.vaultData.brand.version}).`);
    } catch (err) {
      showToast(`Validation error: ${err.message}`);
    }
  });

  document.getElementById('submitRuleBtn').addEventListener('click', async () => {
    const editId = document.getElementById('editRuleIdInput').value.trim();
    const title = document.getElementById('newRuleTitle').value.trim();
    const desc = document.getElementById('newRuleDesc').value.trim();
    if (title.length < 3 || desc.length < 5) {
      showToast('Rule title (>=3 chars) and guidance (>=5 chars) are required.');
      return;
    }
    const payload = {
      pillar: document.getElementById('newRulePillar').value,
      title,
      description: desc,
      severity: document.getElementById('newRuleSeverity').value,
      pattern_regex: document.getElementById('newRuleRegex').value.trim(),
      do_example: '',
      dont_example: '',
    };
    try {
      if (editId) {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/rules/${encodeURIComponent(editId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Updated rule ${editId}.`);
      } else {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Created rule ${res.rule_id}.`);
      }
      AppState.vaultFormOpen.rule = false;
      renderBrandVaultTab();
      await refreshOverview();
    } catch (err) {
      showToast(`Could not save rule: ${err.message}`);
    }
  });

  container.querySelectorAll('.edit-rule-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const r = (AppState.vaultData.rules || []).find((x) => x.id === btn.getAttribute('data-id'));
      if (!r) return;
      AppState.vaultFormOpen.rule = true;
      renderBrandVaultTab();
      document.getElementById('ruleFormHeading').textContent = `Edit rule ${r.id}`;
      document.getElementById('editRuleIdInput').value = r.id;
      document.getElementById('newRulePillar').value = r.pillar;
      document.getElementById('newRuleTitle').value = r.title;
      document.getElementById('newRuleDesc').value = r.description;
      document.getElementById('newRuleSeverity').value = r.severity;
    });
  });

  container.querySelectorAll('.delete-rule-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      openModalDialog({
        title: `Delete rule ${id}?`,
        bodyHtml: `Deleting <strong>${escapeHtml(id)}</strong> removes it from future audits. Existing saved audits retain their historical findings and version snapshots.`,
        confirmLabel: 'Delete rule',
        onConfirm: async () => {
          try {
            await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/rules/${encodeURIComponent(id)}`, {
              method: 'DELETE',
            });
            await refreshBrandVault();
            await refreshOverview();
            showToast(`Deleted rule ${id}.`);
          } catch (err) {
            showToast(`Delete failed: ${err.message}`);
          }
        },
      });
    });
  });
}

function renderVaultTerminologyTab(container) {
  const q = AppState.vaultSearchQuery;
  const terms = (AppState.vaultData.terminology || []).filter((t) =>
    !q ||
    t.id.toLowerCase().includes(q) ||
    t.prohibited_term.toLowerCase().includes(q) ||
    t.replacement_term.toLowerCase().includes(q) ||
    t.notes.toLowerCase().includes(q)
  );
  const formOpen = AppState.vaultFormOpen.term;

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Terminology &amp; capitalization rules (${terms.length})</h2>
        <button type="button" class="btn btn-sm ${formOpen ? '' : 'btn-accent'}" id="toggleTermFormBtn">
          ${formOpen ? 'Close form' : '+ Add terminology rule'}
        </button>
      </div>

      <div id="termFormDrawer" style="display: ${formOpen ? 'block' : 'none'}; background: var(--bg-main); padding: 16px; border-radius: var(--radius-sm); margin-bottom: 16px; border: 1px solid var(--border-color);">
        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;" id="termFormHeading">Add terminology rule</h3>
        <input type="hidden" id="editTermIdInput" value="" />
        <div class="input-form-grid">
          <div class="form-group">
            <label for="termProhibited">Prohibited term or phrase</label>
            <input type="text" id="termProhibited" class="form-control" placeholder="e.g., AI Engine" />
          </div>
          <div class="form-group">
            <label for="termReplacement">Approved replacement</label>
            <input type="text" id="termReplacement" class="form-control" placeholder="e.g., Local Governance Engine" />
          </div>
          <div class="form-group">
            <label for="termNotes">Guidance note</label>
            <input type="text" id="termNotes" class="form-control" placeholder="Explain naming or capitalization rule..." />
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 8px; flex-wrap: wrap; gap: 10px;">
          <div class="checkbox-row">
            <input type="checkbox" id="termCaseSensitive" />
            <label for="termCaseSensitive" style="font-size: 13px; cursor: pointer;">Enforce exact case-sensitive spelling</label>
          </div>
          <div style="display: flex; gap: 8px;">
            <button type="button" class="btn btn-sm" id="cancelTermEditBtn">Cancel</button>
            <button type="button" class="btn btn-accent btn-sm" id="saveTermBtn">Save terminology rule</button>
          </div>
        </div>
      </div>

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Prohibited term</th>
              <th>Approved replacement</th>
              <th>Matching</th>
              <th>Guidance</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${terms.map((t) => `
              <tr>
                <td class="nowrap-col"><span class="mono-id">${escapeHtml(t.id)}</span></td>
                <td class="nowrap-col"><span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>${escapeHtml(t.prohibited_term)}</span></span></td>
                <td class="nowrap-col"><span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>${escapeHtml(t.replacement_term)}</span></span></td>
                <td class="nowrap-col"><span class="mono-id">${t.case_sensitive ? 'Case-sensitive' : 'Case-insensitive'}</span></td>
                <td style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(t.notes)}</td>
                <td class="nowrap-col">
                  <div style="display: flex; gap: 6px;">
                    <button type="button" class="btn btn-sm edit-term-btn" data-id="${escapeHtml(t.id)}">Edit</button>
                    <button type="button" class="btn btn-sm btn-danger-outline delete-term-btn" data-id="${escapeHtml(t.id)}">Delete</button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  document.getElementById('toggleTermFormBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.term = !AppState.vaultFormOpen.term;
    renderBrandVaultTab();
  });

  document.getElementById('cancelTermEditBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.term = false;
    renderBrandVaultTab();
  });

  document.getElementById('saveTermBtn').addEventListener('click', async () => {
    const editId = document.getElementById('editTermIdInput').value.trim();
    const prohibited = document.getElementById('termProhibited').value.trim();
    const replacement = document.getElementById('termReplacement').value.trim();
    const notes = document.getElementById('termNotes').value.trim();
    if (!prohibited || !replacement || notes.length < 3) {
      showToast('Prohibited term, replacement, and guidance note (>=3 chars) are required.');
      return;
    }
    const payload = {
      preferred_term: replacement,
      prohibited_term: prohibited,
      replacement_term: replacement,
      case_sensitive: document.getElementById('termCaseSensitive').checked,
      notes,
      rule_id: 'RULE-TERM-01',
    };
    try {
      if (editId) {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/terminology/${encodeURIComponent(editId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Updated terminology rule ${editId}.`);
      } else {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/terminology`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Added terminology rule ${res.term_id}.`);
      }
      AppState.vaultFormOpen.term = false;
      renderBrandVaultTab();
    } catch (err) {
      showToast(`Could not save terminology rule: ${err.message}`);
    }
  });

  container.querySelectorAll('.edit-term-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const t = (AppState.vaultData.terminology || []).find((x) => x.id === btn.getAttribute('data-id'));
      if (!t) return;
      AppState.vaultFormOpen.term = true;
      renderBrandVaultTab();
      document.getElementById('termFormHeading').textContent = `Edit terminology rule ${t.id}`;
      document.getElementById('editTermIdInput').value = t.id;
      document.getElementById('termProhibited').value = t.prohibited_term;
      document.getElementById('termReplacement').value = t.replacement_term;
      document.getElementById('termNotes').value = t.notes;
      document.getElementById('termCaseSensitive').checked = Boolean(t.case_sensitive);
    });
  });

  container.querySelectorAll('.delete-term-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      openModalDialog({
        title: `Delete terminology rule ${id}?`,
        bodyHtml: `Deleting <strong>${escapeHtml(id)}</strong> removes it from future audits. Saved audits keep their historical findings.`,
        confirmLabel: 'Delete rule',
        onConfirm: async () => {
          try {
            await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/terminology/${encodeURIComponent(id)}`, {
              method: 'DELETE',
            });
            await refreshBrandVault();
            showToast(`Deleted ${id}.`);
          } catch (err) {
            showToast(`Delete failed: ${err.message}`);
          }
        },
      });
    });
  });
}

function renderVaultFactsTab(container) {
  const q = AppState.vaultSearchQuery;
  const facts = (AppState.vaultData.verified_facts || []).filter((f) =>
    !q ||
    f.id.toLowerCase().includes(q) ||
    f.statement.toLowerCase().includes(q) ||
    f.source_reference.toLowerCase().includes(q) ||
    f.verification_status.toLowerCase().includes(q)
  );
  const formOpen = AppState.vaultFormOpen.fact;
  const isAdmin = AppState.activeRole === 'Brand Administrator';

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div>
          <h2 class="card-title">Verified facts (${facts.length})</h2>
          <p style="font-size: 12.5px; color: var(--text-secondary); margin-top: 2px;">
            A source citation or similarity match does not make a fact verified. Only an authorised Brand Administrator can mark a fact <strong>Verified</strong>.
          </p>
        </div>
        <button type="button" class="btn btn-sm ${formOpen ? '' : 'btn-accent'}" id="toggleFactFormBtn">
          ${formOpen ? 'Close form' : '+ Add fact'}
        </button>
      </div>

      <div id="factFormDrawer" style="display: ${formOpen ? 'block' : 'none'}; background: var(--bg-main); padding: 16px; border-radius: var(--radius-sm); margin-bottom: 16px; border: 1px solid var(--border-color);">
        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;" id="factFormHeading">Add fact record</h3>
        <input type="hidden" id="editFactIdInput" value="" />
        <div class="input-form-grid">
          <div class="form-group">
            <label for="factStatement">Fact statement</label>
            <input type="text" id="factStatement" class="form-control" placeholder="e.g., Processing is up to 64% faster under benchmark conditions." />
          </div>
          <div class="form-group">
            <label for="factNumValue">Numeric value</label>
            <input type="text" id="factNumValue" class="form-control" placeholder="e.g., 64" />
          </div>
          <div class="form-group">
            <label for="factNumUnits">Units</label>
            <input type="text" id="factNumUnits" class="form-control" placeholder="e.g., % faster" />
          </div>
        </div>
        <div class="input-form-grid">
          <div class="form-group">
            <label for="factContext">Product / feature context</label>
            <input type="text" id="factContext" class="form-control" placeholder="e.g., Cross-border settlement speed" />
          </div>
          <div class="form-group">
            <label for="factSource">Source reference</label>
            <input type="text" id="factSource" class="form-control" placeholder="e.g., Q3 2026 Benchmark Report" />
          </div>
          <div class="form-group">
            <label for="factConditions">Applicable conditions</label>
            <input type="text" id="factConditions" class="form-control" placeholder="e.g., Measured across 42 supported corridors" />
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <label for="factVerStatus" style="font-size: 13px; font-weight: 600;">Verification status:</label>
            <select id="factVerStatus" class="form-control" style="width: auto;">
              <option value="Verified" ${!isAdmin ? 'disabled' : ''}>Verified ${!isAdmin ? '(Admin only)' : ''}</option>
              <option value="Pending Verification" ${!isAdmin ? 'selected' : ''}>Pending Verification</option>
              <option value="Archived">Archived</option>
            </select>
            ${!isAdmin ? '<span class="form-helper">Non-admin additions default to Pending Verification until reviewed by a Brand Administrator.</span>' : ''}
          </div>
          <div style="display: flex; gap: 8px;">
            <button type="button" class="btn btn-sm" id="cancelFactEditBtn">Cancel</button>
            <button type="button" class="btn btn-accent btn-sm" id="saveFactBtn">Save fact</button>
          </div>
        </div>
      </div>

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Fact ID</th>
              <th>Statement &amp; provenance</th>
              <th>Metric</th>
              <th>Date / version</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${facts.map((f) => `
              <tr>
                <td class="nowrap-col">
                  <span class="mono-id">${escapeHtml(f.id)}</span>
                  ${f.is_demo ? '<div style="margin-top: 4px;"><span class="status-badge badge-warning" style="font-size: 10.5px; padding: 1px 6px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>Demo data</span></span></div>' : ''}
                </td>
                <td>
                  <strong>${escapeHtml(f.statement)}</strong>
                  <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 4px;">
                    <strong>Source:</strong> ${escapeHtml(f.source_reference)} &bull;
                    <strong>Conditions:</strong> ${escapeHtml(f.applicable_conditions)}
                  </div>
                </td>
                <td class="nowrap-col"><span class="mono-id">${escapeHtml(f.numeric_value)} ${escapeHtml(f.numeric_units)}</span></td>
                <td class="nowrap-col"><span class="mono-id">${escapeHtml(f.date_version)}</span></td>
                <td class="nowrap-col">${renderStateBadge(f.verification_status)}</td>
                <td class="nowrap-col">
                  <div style="display: flex; gap: 6px;">
                    <button type="button" class="btn btn-sm edit-fact-btn" data-id="${escapeHtml(f.id)}">Edit</button>
                    <button type="button" class="btn btn-sm btn-danger-outline delete-fact-btn" data-id="${escapeHtml(f.id)}">Delete</button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  document.getElementById('toggleFactFormBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.fact = !AppState.vaultFormOpen.fact;
    renderBrandVaultTab();
  });

  document.getElementById('cancelFactEditBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.fact = false;
    renderBrandVaultTab();
  });

  document.getElementById('saveFactBtn').addEventListener('click', async () => {
    const editId = document.getElementById('editFactIdInput').value.trim();
    const statement = document.getElementById('factStatement').value.trim();
    const context = document.getElementById('factContext').value.trim();
    const source = document.getElementById('factSource').value.trim();
    const conditions = document.getElementById('factConditions').value.trim();

    if (statement.length < 5 || context.length < 2 || source.length < 3 || conditions.length < 3) {
      showToast('Complete statement, product context, source reference, and applicable conditions.');
      return;
    }

    const payload = {
      statement,
      numeric_value: document.getElementById('factNumValue').value.trim(),
      numeric_units: document.getElementById('factNumUnits').value.trim(),
      product_context: context,
      source_reference: source,
      applicable_conditions: conditions,
      date_version: '2026-10 (v1.0)',
      verification_status: document.getElementById('factVerStatus').value,
    };

    try {
      if (editId) {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/facts/${encodeURIComponent(editId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Updated fact ${editId}.`);
      } else {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/facts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Added fact ${res.fact_id}.`);
      }
      AppState.vaultFormOpen.fact = false;
      renderBrandVaultTab();
    } catch (err) {
      showToast(`Could not save fact: ${err.message}`);
    }
  });

  container.querySelectorAll('.edit-fact-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const f = (AppState.vaultData.verified_facts || []).find((x) => x.id === btn.getAttribute('data-id'));
      if (!f) return;
      AppState.vaultFormOpen.fact = true;
      renderBrandVaultTab();
      document.getElementById('factFormHeading').textContent = `Edit fact ${f.id}`;
      document.getElementById('editFactIdInput').value = f.id;
      document.getElementById('factStatement').value = f.statement;
      document.getElementById('factNumValue').value = f.numeric_value;
      document.getElementById('factNumUnits').value = f.numeric_units;
      document.getElementById('factContext').value = f.product_context;
      document.getElementById('factSource').value = f.source_reference;
      document.getElementById('factConditions').value = f.applicable_conditions;
      document.getElementById('factVerStatus').value = f.verification_status;
    });
  });

  container.querySelectorAll('.delete-fact-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      openModalDialog({
        title: `Delete fact ${id}?`,
        bodyHtml: `Deleting <strong>${escapeHtml(id)}</strong> removes it from future claim verification. Existing saved audits retain their recorded evidence citations.`,
        confirmLabel: 'Delete fact',
        onConfirm: async () => {
          try {
            await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/facts/${encodeURIComponent(id)}`, {
              method: 'DELETE',
            });
            await refreshBrandVault();
            showToast(`Deleted ${id}.`);
          } catch (err) {
            showToast(`Delete failed: ${err.message}`);
          }
        },
      });
    });
  });
}

function renderVaultVisualTab(container) {
  const b = AppState.vaultData.brand;
  const q = AppState.vaultSearchQuery;
  const colors = (AppState.vaultData.colors || []).filter((c) =>
    !q ||
    c.name.toLowerCase().includes(q) ||
    c.hex_code.toLowerCase().includes(q) ||
    c.usage_role.toLowerCase().includes(q)
  );
  const formOpen = AppState.vaultFormOpen.color;

  container.innerHTML = `
    <div class="card" style="margin-bottom: 20px;">
      <div class="card-header">
        <h2 class="card-title">Approved colour tokens (${colors.length})</h2>
        <button type="button" class="btn btn-sm ${formOpen ? '' : 'btn-accent'}" id="toggleColorFormBtn">
          ${formOpen ? 'Close form' : '+ Add colour token'}
        </button>
      </div>

      <div id="colorFormDrawer" style="display: ${formOpen ? 'block' : 'none'}; background: var(--bg-main); padding: 16px; border-radius: var(--radius-sm); margin-bottom: 16px; border: 1px solid var(--border-color);">
        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;" id="colorFormHeading">Add colour token</h3>
        <input type="hidden" id="editColorIdInput" value="" />
        <div class="input-form-grid">
          <div class="form-group">
            <label for="colName">Colour name</label>
            <input type="text" id="colName" class="form-control" placeholder="e.g., Primary Charcoal" />
          </div>
          <div class="form-group">
            <label for="colHex">Hex code (#RRGGBB)</label>
            <input type="text" id="colHex" class="form-control" placeholder="#17191C" />
          </div>
          <div class="form-group">
            <label for="colRole">Usage role</label>
            <input type="text" id="colRole" class="form-control" placeholder="e.g., Headings &amp; navigation" />
          </div>
        </div>
        <details class="collapsible-details" style="margin-bottom: 12px;">
          <summary>Advanced visual settings (Delta-E tolerance)</summary>
          <div class="collapsible-details-body">
            <div class="form-group" style="max-width: 240px;">
              <label for="colDeltaE">Maximum colour distance tolerance (CIE Delta-E)</label>
              <input type="number" id="colDeltaE" class="form-control" value="14.0" step="1" min="1" max="50" />
            </div>
          </div>
        </details>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button type="button" class="btn btn-sm" id="cancelColorEditBtn">Cancel</button>
          <button type="button" class="btn btn-accent btn-sm" id="saveColorBtn">Save colour token</button>
        </div>
      </div>

      <div class="color-swatch-grid">
        ${colors.map((c) => `
          <div class="color-swatch-card">
            <div class="color-swatch-preview" style="background-color: ${escapeHtml(c.hex_code)};"></div>
            <div class="color-swatch-body">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; gap: 6px;">
                <strong>${escapeHtml(c.name)}</strong>
                <span class="mono-id">${escapeHtml(c.hex_code)}</span>
              </div>
              <div style="font-size: 12.5px; color: var(--text-secondary); margin-bottom: 8px;">
                ${escapeHtml(c.usage_role)}
              </div>
              <div style="display: flex; gap: 6px;">
                <button type="button" class="btn btn-sm edit-col-btn" data-id="${escapeHtml(c.id)}">Edit</button>
                <button type="button" class="btn btn-sm btn-danger-outline delete-col-btn" data-id="${escapeHtml(c.id)}">Delete</button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Approved brand logo &amp; clear space</h2>
      </div>
      <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 16px;">
        <div style="flex: 1; min-width: 240px;">
          <label style="font-size: 13px; font-weight: 600; display: block; margin-bottom: 6px;">Approved logo asset (PNG or SVG, max 300 KB)</label>
          ${b.approved_logo_b64 ? `
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
              <img src="${b.approved_logo_b64}" alt="Approved brand logo" style="max-height: 48px; max-width: 140px; object-fit: contain; border: 1px solid var(--border-color); padding: 4px; border-radius: 4px; background: #FFFFFF;" />
              <div>
                <div class="mono-id" style="font-size: 12px; font-weight: 600;">${escapeHtml(b.approved_logo_filename || 'approved_logo')}</div>
                <div style="font-size: 11px; color: var(--slate-600);">${escapeHtml(b.approved_logo_format || '')}</div>
              </div>
              <button type="button" class="btn btn-sm btn-danger-outline" id="vaultDeleteLogoBtn" style="margin-left: auto;">Remove</button>
            </div>
          ` : `
            <div style="font-size: 12.5px; color: var(--slate-600); margin-bottom: 8px;">No approved logo asset configured. Upload an approved logo for template matching.</div>
          `}
          <input type="file" id="vaultApprovedLogoInput" accept=".png,.svg,image/png,image/svg+xml" class="form-control" style="font-size: 12px; padding: 4px 8px;" />
        </div>
        <div style="flex: 1; min-width: 240px;">
          <div class="input-form-grid" style="grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
              <label for="visClearSpaceRatio" style="font-size: 12.5px;">Clear space ratio (&times; logo height)</label>
              <input type="number" id="visClearSpaceRatio" class="form-control vault-watch" step="0.05" min="0.1" max="2.0" value="${b.min_clear_space_ratio || 0.25}" />
            </div>
            <div class="form-group">
              <label for="visClearSpacePx" style="font-size: 12.5px;">Fallback clearance (px, optional)</label>
              <input type="number" id="visClearSpacePx" class="form-control vault-watch" step="1" min="0" max="200" value="${b.min_clear_space_px || 16}" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Typography, spacing &amp; logo usage guidelines</h2>
        <button type="button" class="btn btn-accent btn-sm" id="saveVisualSpecsBtn">Save visual guidelines</button>
      </div>
      <div class="input-form-grid">
        <div class="form-group">
          <label for="visTypography">Typography guidelines</label>
          <textarea id="visTypography" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.typography_specs)}</textarea>
        </div>
        <div class="form-group">
          <label for="visSpacing">Spacing &amp; clear-space rules</label>
          <textarea id="visSpacing" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.spacing_rules)}</textarea>
        </div>
        <div class="form-group">
          <label for="visLogo">Logo placement rules</label>
          <textarea id="visLogo" class="form-control vault-watch" style="min-height: 84px;">${escapeHtml(b.logo_placement_constraints)}</textarea>
        </div>
      </div>
    </div>
  `;

  container.querySelectorAll('.vault-watch').forEach((el) => {
    el.addEventListener('input', () => setUnsavedVaultChanges(true));
  });

  document.getElementById('toggleColorFormBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.color = !AppState.vaultFormOpen.color;
    renderBrandVaultTab();
  });

  document.getElementById('cancelColorEditBtn').addEventListener('click', () => {
    AppState.vaultFormOpen.color = false;
    renderBrandVaultTab();
  });

  document.getElementById('saveColorBtn').addEventListener('click', async () => {
    const editId = document.getElementById('editColorIdInput').value.trim();
    const name = document.getElementById('colName').value.trim();
    const hex = document.getElementById('colHex').value.trim();
    const role = document.getElementById('colRole').value.trim();
    const deltaE = parseFloat(document.getElementById('colDeltaE').value) || 14.0;

    if (!/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(hex)) {
      showToast('Hex code must be in #RGB or #RRGGBB format (e.g., #17191C).');
      return;
    }
    if (name.length < 2 || role.length < 2) {
      showToast('Colour name and usage role are required.');
      return;
    }

    const payload = { name, hex_code: hex, usage_role: role, max_delta_e: deltaE };
    try {
      if (editId) {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/colors/${encodeURIComponent(editId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Updated colour ${editId}.`);
      } else {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/colors`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        AppState.vaultData = res.vault;
        showToast(`Added colour ${res.color_id}.`);
      }
      AppState.vaultFormOpen.color = false;
      renderBrandVaultTab();
    } catch (err) {
      showToast(`Colour save error: ${err.message}`);
    }
  });

  container.querySelectorAll('.edit-col-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const c = (AppState.vaultData.colors || []).find((x) => x.id === btn.getAttribute('data-id'));
      if (!c) return;
      AppState.vaultFormOpen.color = true;
      renderBrandVaultTab();
      document.getElementById('colorFormHeading').textContent = `Edit colour token ${c.id}`;
      document.getElementById('editColorIdInput').value = c.id;
      document.getElementById('colName').value = c.name;
      document.getElementById('colHex').value = c.hex_code;
      document.getElementById('colRole').value = c.usage_role;
      document.getElementById('colDeltaE').value = c.max_delta_e;
    });
  });

  container.querySelectorAll('.delete-col-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      openModalDialog({
        title: `Delete colour token ${id}?`,
        bodyHtml: `Deleting <strong>${escapeHtml(id)}</strong> removes it from future visual palette checks. Existing audits retain their recorded results.`,
        confirmLabel: 'Delete colour token',
        onConfirm: async () => {
          await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/colors/${encodeURIComponent(id)}`, {
            method: 'DELETE',
          });
          await refreshBrandVault();
          showToast(`Deleted colour ${id}.`);
        },
      });
    });
  });


  const logoInput = document.getElementById('vaultApprovedLogoInput');
  if (logoInput) {
    logoInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      if (file.size > 300 * 1024) {
        showToast('Logo file exceeds 300 KB limit.');
        return;
      }
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/logo`, {
          method: 'POST',
          body: fd,
        });
        AppState.vaultData = res.vault || AppState.vaultData;
        renderBrandVaultTab();
        showToast('Approved brand logo uploaded and saved.');
      } catch (err) {
        showToast(`Logo upload failed: ${err.message}`);
      }
    });
  }

  const delLogoBtn = document.getElementById('vaultDeleteLogoBtn');
  if (delLogoBtn) {
    delLogoBtn.addEventListener('click', async () => {
      try {
        const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/logo`, {
          method: 'DELETE',
        });
        AppState.vaultData = res.vault || AppState.vaultData;
        renderBrandVaultTab();
        showToast('Approved brand logo removed.');
      } catch (err) {
        showToast(`Failed to remove logo: ${err.message}`);
      }
    });
  }

  document.getElementById('saveVisualSpecsBtn').addEventListener('click', async () => {
    try {
      const res = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/visual-specs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          typography_specs: document.getElementById('visTypography').value,
          spacing_rules: document.getElementById('visSpacing').value,
          logo_placement_constraints: document.getElementById('visLogo').value,
          min_clear_space_ratio: parseFloat(document.getElementById('visClearSpaceRatio').value) || 0.25,
          min_clear_space_px: parseInt(document.getElementById('visClearSpacePx').value, 10) || 16,
        }),
      });
      AppState.vaultData = res.vault || res;
      setUnsavedVaultChanges(false);
      showToast('Visual identity guidelines saved.');
    } catch (err) {
      showToast(`Save failed: ${err.message}`);
    }
  });
}

function renderVaultAccessibilityTab(container) {
  const b = AppState.vaultData.brand;
  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Accessibility requirements</h2>
        <button type="button" class="btn btn-accent btn-sm" id="saveA11yRulesBtn">Save accessibility settings</button>
      </div>
      <div class="input-form-grid" style="grid-template-columns: 1fr 1fr;">
        <div class="form-group">
          <label for="a11yNormalContrast">Minimum contrast for normal text (WCAG AA default: 4.5:1)</label>
          <input type="number" id="a11yNormalContrast" class="form-control vault-watch" step="0.1" min="1" max="21" value="${b.min_contrast_normal}" />
        </div>
        <div class="form-group">
          <label for="a11yLargeContrast">Minimum contrast for large text (WCAG AA default: 3.0:1)</label>
          <input type="number" id="a11yLargeContrast" class="form-control vault-watch" step="0.1" min="1" max="21" value="${b.min_contrast_large}" />
        </div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 10px; margin: 12px 0;">
        <div class="checkbox-row">
          <input type="checkbox" id="a11yRequireAlt" class="vault-watch" ${b.require_alt_text ? 'checked' : ''} />
          <label for="a11yRequireAlt" style="font-size: 13.5px; cursor: pointer;">Require descriptive alternative text on all attached visual assets and HTML/Markdown images</label>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="a11yHeadingOrder" class="vault-watch" ${b.enforce_heading_order ? 'checked' : ''} />
          <label for="a11yHeadingOrder" style="font-size: 13.5px; cursor: pointer;">Enforce sequential heading hierarchy (flag skipped levels such as H2 to H4)</label>
        </div>
      </div>

      <details class="collapsible-details">
        <summary>Advanced readability settings</summary>
        <div class="collapsible-details-body">
          <div class="form-group" style="max-width: 320px;">
            <label for="a11yReadingEase">Target Flesch reading ease score (0–100)</label>
            <input type="number" id="a11yReadingEase" class="form-control vault-watch" step="1" min="0" max="100" value="${b.target_reading_ease}" />
            <span class="form-helper">Higher scores indicate easier reading (50–60 is standard business prose).</span>
          </div>
        </div>
      </details>
    </div>
  `;

  container.querySelectorAll('.vault-watch').forEach((el) => {
    el.addEventListener('input', () => setUnsavedVaultChanges(true));
    el.addEventListener('change', () => setUnsavedVaultChanges(true));
  });

  document.getElementById('saveA11yRulesBtn').addEventListener('click', async () => {
    try {
      AppState.vaultData = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/accessibility-rules`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          min_contrast_normal: parseFloat(document.getElementById('a11yNormalContrast').value) || 4.5,
          min_contrast_large: parseFloat(document.getElementById('a11yLargeContrast').value) || 3.0,
          require_alt_text: document.getElementById('a11yRequireAlt').checked,
          enforce_heading_order: document.getElementById('a11yHeadingOrder').checked,
          target_reading_ease: parseFloat(document.getElementById('a11yReadingEase').value) || 50.0,
        }),
      });
      setUnsavedVaultChanges(false);
      showToast('Accessibility requirements saved.');
    } catch (err) {
      showToast(`Error saving accessibility settings: ${err.message}`);
    }
  });
}

// ============================================================================
// VIEW 4: REVIEW QUEUE (SECTION 07 — FILTERS & APPROVAL SAFEGUARD)
// ============================================================================

async function renderReviewQueueView() {
  const container = document.getElementById('reviewQueueContainer');
  if (container && !AppState.lastRefreshed.reviewQueue) {
    container.innerHTML = '<div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">Loading review queue...</div>';
  }
  try {
    const offset = AppState.reviewQueueOffset || 0;
    const res = await apiFetch(`/api/audits?brand_id=${encodeURIComponent(AppState.activeBrandId)}&limit=50&offset=${offset}`);
    AppState.lastRefreshed.reviewQueue = new Date().toISOString();
    const allAudits = res.audits || [];
    const totalCount = res.total ?? allAudits.length;
    const statuses = ['ALL', 'Draft', 'In Review', 'Changes Requested', 'Revised', 'Approved'];

    const q = AppState.reviewQueueSearch.toLowerCase();
    const filtered = allAudits.filter((a) => {
      if (AppState.reviewQueueFilter !== 'ALL' && a.overall_status !== AppState.reviewQueueFilter) return false;
      if (q && !`${a.id} ${a.document_name} ${a.assigned_reviewer}`.toLowerCase().includes(q)) return false;
      return true;
    });

    container.innerHTML = `
      <div class="card-header">
        <div class="filter-pills-row">
          ${statuses.map((st) => `
            <button type="button" class="filter-pill ${AppState.reviewQueueFilter === st ? 'active' : ''}" data-rq-filter="${escapeHtml(st)}">
              ${escapeHtml(st === 'ALL' ? 'All' : normalizeStatusDisplay(st))}
            </button>
          `).join('')}
        </div>
        <input type="search" id="rqSearchInput" class="form-control" style="width: 240px; font-size: 13px;" placeholder="Search documents..." value="${escapeHtml(AppState.reviewQueueSearch)}" aria-label="Search review queue" />
      </div>

      ${filtered.length === 0 ? `
        <div class="empty-state-box">
          <h3>No documents in this queue state</h3>
          <p>Run an audit or switch the status filter above to inspect documents.</p>
        </div>
      ` : `
        <div class="rq-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th class="rq-doc-col">Document</th>
                <th>Submitted by</th>
                <th>Assigned reviewer</th>
                <th>Status</th>
                <th>Unresolved findings</th>
                <th>Last updated</th>
                <th class="rq-actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.map((a) => {
                const hasUnresolved = a.open_findings > 0;
                return `
                  <tr>
                    <td class="rq-doc-col" data-label="Document">
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <strong style="font-size: 14.5px; line-height: 20px;">${escapeHtml(a.document_name)}</strong>
                        ${(a.id.startsWith('AUD-100') || (a.document_name && (a.document_name.includes('sample data') || a.document_name.includes('(Demo)')))) ? '<span class="status-badge badge-neutral" style="font-size: 11px;"><span>Sample data</span></span>' : ''}
                      </div>
                      <div style="margin-top: 4px;"><span class="mono-id">${escapeHtml(a.id)}</span></div>
                    </td>
                    <td data-label="Submitted by">${escapeHtml(a.submitted_by_name || '—')}</td>
                    <td data-label="Assigned reviewer">${escapeHtml(a.assigned_reviewer)}</td>
                    <td class="nowrap-col">${renderStateBadge(a.overall_status)}</td>
                    <td class="nowrap-col">
                      ${hasUnresolved
                        ? `<span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>${a.open_findings} unresolved</span></span>`
                        : `<span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>0 unresolved</span></span>`}
                    </td>
                    <td class="nowrap-col" style="font-size: 12.5px; color: var(--text-secondary);" title="${escapeHtml(a.updated_at)}">${escapeHtml(formatTimestamp(a.updated_at))}</td>
                    <td class="rq-actions-col">
                      <div style="display: flex; gap: 6px; align-items: center; justify-content: flex-end;">
                        <button type="button" class="btn btn-accent btn-sm rq-open-btn" data-id="${escapeHtml(a.id)}">Open review</button>
                        ${a.overall_status !== 'Approved' ? `
                          <button type="button" class="btn btn-sm rq-wf-btn" data-id="${escapeHtml(a.id)}" data-state="Changes Requested">Request changes</button>
                        ` : ''}
                      </div>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>

        ${totalCount > 50 ? `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-top: 1px solid var(--border-color); font-size: 13px; color: var(--text-secondary);">
            <div>Showing ${offset + 1}–${Math.min(offset + allAudits.length, totalCount)} of ${totalCount} documents</div>
            <div style="display: flex; gap: 8px;">
              <button type="button" class="btn btn-sm" id="rqPrevPageBtn" ${offset <= 0 ? 'disabled' : ''}>&larr; Previous</button>
              <button type="button" class="btn btn-sm" id="rqNextPageBtn" ${offset + 50 >= totalCount ? 'disabled' : ''}>Next &rarr;</button>
            </div>
          </div>
        ` : ''}

        <div class="rq-cards-view">
          ${filtered.map((a) => {
            const hasUnresolved = a.open_findings > 0;
            return `
              <div class="rq-card">
                <div class="rq-card-header">
                  <div>
                    <div class="rq-card-title">${escapeHtml(a.document_name)}</div>
                    <div style="margin-top: 4px;"><span class="mono-id">${escapeHtml(a.id)}</span></div>
                  </div>
                  <div>${renderStateBadge(a.overall_status)}</div>
                </div>
                <div class="rq-card-meta">
                  <span>Submitted by: <strong>${escapeHtml(a.submitted_by_name || '—')}</strong></span>
                  <span>&bull;</span>
                  <span>Reviewer: <strong>${escapeHtml(a.assigned_reviewer)}</strong></span>
                  <span>&bull;</span>
                  ${hasUnresolved
                    ? `<span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>${a.open_findings} unresolved</span></span>`
                    : `<span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>0 unresolved</span></span>`}
                  <span>&bull;</span>
                  <span>Updated: ${escapeHtml(formatTimestamp(a.updated_at))}</span>
                </div>
                <div class="rq-card-actions">
                  <button type="button" class="btn btn-accent btn-sm rq-open-btn" data-id="${escapeHtml(a.id)}">Open review</button>
                  ${a.overall_status !== 'Approved' ? `
                    <button type="button" class="btn btn-sm rq-wf-btn" data-id="${escapeHtml(a.id)}" data-state="Changes Requested">Request changes</button>
                  ` : ''}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `}
    `;

    const prevBtn = document.getElementById('rqPrevPageBtn');
    if (prevBtn) {
      prevBtn.addEventListener('click', async () => {
        AppState.reviewQueueOffset = Math.max(0, offset - 50);
        await renderReviewQueueView();
      });
    }
    const nextBtn = document.getElementById('rqNextPageBtn');
    if (nextBtn) {
      nextBtn.addEventListener('click', async () => {
        AppState.reviewQueueOffset = offset + 50;
        await renderReviewQueueView();
      });
    }

    container.querySelectorAll('.filter-pill[data-rq-filter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        AppState.reviewQueueFilter = btn.getAttribute('data-rq-filter');
        renderReviewQueueView();
      });
    });

    const searchEl = document.getElementById('rqSearchInput');
    if (searchEl) {
      searchEl.addEventListener('input', (e) => {
        AppState.reviewQueueSearch = e.target.value;
        renderReviewQueueView();
      });
    }

    container.querySelectorAll('.rq-open-btn').forEach((btn) => {
      btn.addEventListener('click', () => openAuditById(btn.getAttribute('data-id')));
    });

    container.querySelectorAll('.rq-wf-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const state = btn.getAttribute('data-state');
        try {
          await apiFetch(`/api/audits/${encodeURIComponent(id)}/workflow`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              new_state: state,
              comment: `Status updated to ${state} by ${AppState.activeRole}.`,
              override_acknowledged: false,
            }),
          });
          await renderReviewQueueView();
          await refreshOverview();
          showToast(`Audit ${id} marked as "${state}".`);
        } catch (err) {
          showToast(`Cannot update ${id}: ${err.message}`);
        }
      });
    });

    container.querySelectorAll('.rq-approve-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        try {
          await apiFetch(`/api/audits/${encodeURIComponent(id)}/workflow`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              new_state: 'Approved',
              comment: `Approved for publication by ${AppState.activeRole}.`,
              override_acknowledged: false,
            }),
          });
          await renderReviewQueueView();
          await refreshOverview();
          showToast(`Audit ${id} approved and logged.`);
        } catch (err) {
          showToast(`Approval blocked: ${err.message}`);
        }
      });
    });
  } catch (err) {
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.reviewQueue ? formatTimestamp(AppState.lastRefreshed.reviewQueue) : 'Never';
    container.innerHTML = `
      <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
        <h3 style="color: #B42318;">Could not retrieve review queue</h3>
        <p style="color: #475467;">${escapeHtml(err.message)}</p>
        ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
        ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
        <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
        <button type="button" class="btn btn-sm btn-accent" id="retryReviewQueueBtn" style="margin-top: 12px;">Retry</button>
      </div>
    `;
    const retryBtn = document.getElementById('retryReviewQueueBtn');
    if (retryBtn) retryBtn.addEventListener('click', () => renderReviewQueueView());
  }
}

// ============================================================================
// VIEW 5: GUIDELINE INSIGHTS / AMBIGUITY (SECTION 07 — COMPACT + EXPANDABLE)
// ============================================================================

function hasFrontendPermission(perm) {
  if (AppState.permissions && typeof AppState.permissions[perm] === 'boolean') {
    return AppState.permissions[perm];
  }
  if (perm === 'edit_brand_vault') {
    return AppState.activeRole === 'Brand Administrator';
  }
  if (perm === 'approve_audit' || perm === 'dismiss_finding') {
    return AppState.activeRole === 'Reviewer' || AppState.activeRole === 'Brand Administrator';
  }
  return true;
}

function renderRuleTextWithVagueSpans(rawText, matchedSpans) {
  const text = String(rawText || '');
  if (!Array.isArray(matchedSpans) || matchedSpans.length === 0) {
    return escapeHtml(text);
  }
  const sorted = [...matchedSpans]
    .filter((s) => s && typeof s.start === 'number' && typeof s.end === 'number' && s.end > s.start)
    .sort((a, b) => a.start - b.start);

  let out = '';
  let cursor = 0;
  for (const sp of sorted) {
    const start = Math.max(cursor, Math.min(text.length, sp.start));
    const end = Math.max(start, Math.min(text.length, sp.end));
    if (start > cursor) {
      out += escapeHtml(text.slice(cursor, start));
    }
    if (end > start) {
      const qual = escapeHtml(sp.qualifier || sp.phrase || 'vague qualifier');
      out += `<mark class="vague-span-highlight" title="Vague qualifier: ${qual}">${escapeHtml(text.slice(start, end))}</mark>`;
      cursor = end;
    }
  }
  if (cursor < text.length) {
    out += escapeHtml(text.slice(cursor));
  }
  return out;
}

function drawHeatmapCanvasOverlay(canvas, hm, activeLayers, focusedCellId, baseImage) {
  if (!canvas || !hm) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Draw base image or neutral checkerboard background
  ctx.fillStyle = '#F8FAFC';
  ctx.fillRect(0, 0, w, h);
  if (baseImage && baseImage.complete && baseImage.naturalWidth > 0) {
    try {
      ctx.drawImage(baseImage, 0, 0, w, h);
    } catch (_e) {
      // Fallback if SVG/image taint or decode issue
    }
  } else {
    const cells = hm.cells || [];
    const n = hm.grid_size || 4;
    const cw = w / n;
    const ch = h / n;
    cells.forEach((c) => {
      ctx.fillStyle = c.dominant_hex || '#E2E8F0';
      ctx.fillRect(c.col * cw, c.row * ch, cw, ch);
    });
  }

  const n = hm.grid_size || 4;
  const cellW = w / n;
  const cellH = h / n;
  const scaleX = w / Math.max(1, hm.analyzed_width || hm.original_width || w);
  const scaleY = h / Math.max(1, hm.analyzed_height || hm.original_height || h);

  // Layer 1: Delta-E Palette Grid
  if (activeLayers.delta_e) {
    (hm.cells || []).forEach((c) => {
      const x = c.col * cellW;
      const y = c.row * cellH;
      const isFocused = focusedCellId === c.cell_id;

      if (c.flagged) {
        ctx.fillStyle = 'rgba(180, 35, 24, 0.22)';
        ctx.fillRect(x, y, cellW, cellH);

        // Diagonal hatch pattern so cell status is communicated with pattern, not colour alone
        ctx.save();
        ctx.beginPath();
        ctx.rect(x, y, cellW, cellH);
        ctx.clip();
        ctx.strokeStyle = 'rgba(180, 35, 24, 0.65)';
        ctx.lineWidth = 1.5;
        const step = 12;
        for (let d = -cellH; d < cellW + cellH; d += step) {
          ctx.beginPath();
          ctx.moveTo(x + d, y);
          ctx.lineTo(x + d + cellH, y + cellH);
          ctx.stroke();
        }
        ctx.restore();
      }

      ctx.strokeStyle = isFocused ? '#C84624' : (c.flagged ? '#B42318' : 'rgba(15, 23, 42, 0.32)');
      ctx.lineWidth = isFocused ? 3 : (c.flagged ? 2 : 1);
      ctx.strokeRect(x + 0.5, y + 0.5, cellW - 1, cellH - 1);
    });
  }

  // Layer 2: Known-Text Contrast Regions
  if (activeLayers.contrast && hm.text_contrast && Array.isArray(hm.text_contrast.elements)) {
    const svgScaleX = w / Math.max(1, hm.original_width || hm.analyzed_width || w);
    const svgScaleY = h / Math.max(1, hm.original_height || hm.analyzed_height || h);
    hm.text_contrast.elements.forEach((el) => {
      const sx = el.source === 'svg_text' ? svgScaleX : scaleX;
      const sy = el.source === 'svg_text' ? svgScaleY : scaleY;
      const rx = (el.x || 0) * sx;
      const ry = (el.y || 0) * sy;
      const rw = Math.max(24, (el.width || 40) * sx);
      const rh = Math.max(16, (el.height || 18) * sy);

      const notMeasured = el.status === 'Not measured' || el.contrast_ratio === null || el.contrast_ratio === undefined;
      ctx.save();
      ctx.strokeStyle = notMeasured ? '#475467' : (el.passed ? '#067647' : '#B42318');
      ctx.lineWidth = 2;
      ctx.setLineDash(notMeasured ? [2, 2] : (el.passed ? [] : [4, 3]));
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.fillStyle = notMeasured ? 'rgba(71, 84, 103, 0.92)' : (el.passed ? 'rgba(6, 118, 71, 0.88)' : 'rgba(180, 35, 24, 0.92)');
      ctx.fillRect(rx, Math.max(0, ry - 16), Math.min(w - rx, 98), 16);
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '600 10px Inter, sans-serif';
      ctx.fillText(notMeasured ? 'NOT MEASURED' : `${el.passed ? 'PASS' : 'FAIL'} ${el.contrast_ratio}:1`, rx + 4, Math.max(11, ry - 4));
      ctx.restore();
    });
  }

  // Layer 3: Logo Clear Space
  if (activeLayers.clear_space && hm.clear_space && hm.clear_space.checked && hm.clear_space.logo_box) {
    const lb = hm.clear_space.logo_box;
    const isSvgBox = lb.source && lb.source !== 'user_drawn_rect' && lb.source !== 'png_alpha_bbox';
    const sx = isSvgBox ? (w / Math.max(1, hm.original_width || w)) : scaleX;
    const sy = isSvgBox ? (h / Math.max(1, hm.original_height || h)) : scaleY;
    const lx = lb.x * sx;
    const ly = lb.y * sy;
    const lw = lb.width * sx;
    const lh = lb.height * sy;
    const reqPx = (hm.clear_space.required_px || 16) * sx;

    ctx.save();
    ctx.strokeStyle = hm.clear_space.passed ? '#067647' : '#B42318';
    ctx.lineWidth = 2;
    ctx.strokeRect(lx, ly, lw, lh);
    ctx.setLineDash([5, 4]);
    ctx.strokeRect(
      Math.max(1, lx - reqPx),
      Math.max(1, ly - reqPx),
      Math.min(w - 2, lw + reqPx * 2),
      Math.min(h - 2, lh + reqPx * 2)
    );
    ctx.fillStyle = hm.clear_space.passed ? 'rgba(6, 118, 71, 0.9)' : 'rgba(180, 35, 24, 0.92)';
    ctx.fillRect(lx, Math.max(0, ly - 18), Math.min(w - lx, 145), 18);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '600 10px Inter, sans-serif';
    ctx.fillText(
      `LOGO ${hm.clear_space.passed ? 'CLEAR' : 'CROWDED'}: ${hm.clear_space.min_distance_px}px (${hm.clear_space.measured_ratio}x)`,
      lx + 4,
      Math.max(12, ly - 5)
    );
    ctx.restore();
  }
}

function renderVisualHeatmapInspector(viewer, audit, docHtml) {
  const hm = audit.visual_metadata || {};
  const cells = hm.cells || [];
  const n = hm.grid_size || 4;
  const tc = hm.text_contrast || {};
  const cs = hm.clear_space || {};

  if (!AppState.heatmapLayers) {
    AppState.heatmapLayers = { delta_e: true, contrast: true, clear_space: true };
  }
  const layers = AppState.heatmapLayers;
  const focusedCellId = AppState.focusedHeatmapCellId || (cells[0] && cells[0].cell_id) || 'R1C1';

  viewer.innerHTML = `
    <div class="heatmap-inspector-panel" id="heatmapInspectorPanel" role="region" aria-label="Visual Asset Heatmap Inspector">
      <div class="heatmap-toolbar">
        <div class="heatmap-layers-group" role="group" aria-label="Heatmap overlay layers">
          <span style="font-size: 12px; font-weight: 600; color: var(--slate-700);">Layers:</span>
          <button type="button" class="btn btn-sm heatmap-layer-toggle ${layers.delta_e ? 'active' : ''}" data-hm-layer="delta_e" aria-pressed="${layers.delta_e ? 'true' : 'false'}">
            Delta-E Palette (${hm.flagged_cells_count || 0} flagged)
          </button>
          <button type="button" class="btn btn-sm heatmap-layer-toggle ${layers.contrast ? 'active' : ''}" data-hm-layer="contrast" aria-pressed="${layers.contrast ? 'true' : 'false'}">
            Text Contrast (${tc.measured_count > 0 ? (tc.state === 'Findings' ? 'Findings' : 'Passed') : 'Not measured'})
          </button>
          <button type="button" class="btn btn-sm heatmap-layer-toggle ${layers.clear_space ? 'active' : ''}" data-hm-layer="clear_space" aria-pressed="${layers.clear_space ? 'true' : 'false'}">
            Clear Space (${escapeHtml(cs.state || 'Not Checked')})
          </button>
        </div>

        <div class="heatmap-controls-group">
          <label for="heatmapGridSizeSelect" style="font-size: 12px; font-weight: 600; color: var(--slate-700);">Grid:</label>
          <select id="heatmapGridSizeSelect" class="form-control" style="width: 82px; height: 30px; padding: 2px 6px; font-size: 12px;">
            ${[2, 3, 4, 6, 8].map((g) => `<option value="${g}" ${Number(n) === g ? 'selected' : ''}>${g}x${g}</option>`).join('')}
          </select>
          <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 4px; color: var(--slate-700); cursor: pointer;">
            <input type="checkbox" id="heatmapLogoOnlyCheckbox" ${cs.logo_box && cs.logo_box.source === 'png_alpha_bbox' ? 'checked' : ''} />
            <span>Logo-only PNG</span>
          </label>
          <button type="button" class="btn btn-sm" id="heatmapDrawLogoBtn" aria-pressed="${AppState.drawingLogoRect ? 'true' : 'false'}">
            ${AppState.drawingLogoRect ? 'Click-drag on canvas...' : 'Mark logo box'}
          </button>
        </div>
      </div>

      <div class="heatmap-stage-wrap" id="heatmapStageWrap">
        <canvas id="heatmapOverlayCanvas" width="440" height="280" aria-label="Visual asset compliance heatmap canvas"></canvas>
        <div class="heatmap-focus-grid" id="heatmapFocusableGrid" style="grid-template-columns: repeat(${n}, 1fr); grid-template-rows: repeat(${n}, 1fr);" role="group" aria-label="Interactive ${n} by ${n} heatmap cells">
          ${cells.map((c) => {
            const notChecked = c.status === 'not_checked';
            const deVal = notChecked ? '—' : (c.min_delta_e ?? c.delta_e ?? 0);
            const statusText = notChecked ? 'NOT CHECKED' : (c.flagged ? 'FAIL [Hatch]' : 'PASS [Solid]');
            return `
              <button
                type="button"
                class="heatmap-cell-btn ${c.flagged ? 'is-flagged' : 'is-passed'} ${focusedCellId === c.cell_id ? 'is-focused' : ''}"
                data-cell-id="${escapeHtml(c.cell_id)}"
                aria-label="Cell ${escapeHtml(c.cell_id)}: ${notChecked ? 'Not checked' : (c.flagged ? 'FAIL' : 'PASS')}, dominant ${escapeHtml(c.dominant_hex || 'transparent')}, Delta-E ${deVal} to ${escapeHtml(c.closest_brand_color || 'palette')}"
              >
                <span class="heatmap-cell-coord">${escapeHtml(c.cell_id)}</span>
                <span class="heatmap-cell-status-tag">${escapeHtml(statusText)}</span>
                <span class="heatmap-cell-de">&Delta;E ${deVal}</span>
              </button>
            `;
          }).join('')}
        </div>
      </div>

      <div class="heatmap-legend-bar" aria-label="Heatmap status legend">
        <span><strong>Legend:</strong></span>
        <span class="heatmap-legend-item"><span class="legend-swatch-pass" aria-hidden="true"></span> PASS: Solid border (&Delta;E within tolerance)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-fail" aria-hidden="true">///</span> FAIL: Diagonal hatch + FAIL label (&Delta;E above threshold)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-logo" aria-hidden="true">[ ]</span> Clear space: Dashed clearance boundary</span>
      </div>
      ${cs.located_method && cs.located_method !== 'None' ? `
        <div class="heatmap-logo-source-indicator" style="padding: 4px 12px; font-size: 11.5px; color: var(--slate-700); background: #F8FAFC; border-top: 1px solid var(--border-color);">
          Logo located by: <strong>${escapeHtml(cs.located_method)}</strong>
        </div>
      ` : ''}

      <div class="heatmap-disclosures-box">
        <div style="font-size: 12.5px; color: var(--slate-800);">
          <strong>Text contrast (${tc.measured_count > 0 ? (tc.state === 'Findings' ? 'Findings' : 'Passed') : 'Not measured'}):</strong> ${escapeHtml(tc.disclosure || 'Contrast measured for 0 text elements; text inside raster images is not detected.')}
        </div>
        <div style="font-size: 12.5px; color: var(--slate-800); margin-top: 4px;" id="heatmapPaletteScope">
          <strong>Palette (${escapeHtml(hm.palette_state || 'Not Checked')}):</strong> ${hm.palette_state === 'Not Checked'
            ? 'No brand palette colours are configured, so palette compliance was not checked.'
            : `A cell is flagged when its dominant colour, or any colour cluster covering at least ${escapeHtml(String(hm.off_palette_min_cell_coverage_pct ?? 2))}% of the cell, is outside the palette tolerance. Smaller details are not reported.`}
        </div>
        <div style="font-size: 12.5px; color: var(--slate-800); margin-top: 4px;">
          <strong>Logo clear space (${escapeHtml(cs.state || 'Not Checked')}):</strong> ${escapeHtml(cs.reason || 'No logo location specified.')}
        </div>
      </div>

      <div class="heatmap-table-wrap" style="margin-top: 10px;">
        <table class="data-table" id="heatmapCellsTable" aria-label="Heatmap grid cell colour and Delta-E measurements">
          <thead>
            <tr>
              <th scope="col">Cell</th>
              <th scope="col">Dominant Colour</th>
              <th scope="col">Nearest Vault Colour</th>
              <th scope="col">Min CIE &Delta;E</th>
              <th scope="col">Max Allowed &Delta;E</th>
              <th scope="col">Status &amp; Pattern</th>
            </tr>
          </thead>
          <tbody>
            ${cells.map((c) => {
              const notChecked = c.status === 'not_checked';
              const deVal = notChecked ? '—' : (c.min_delta_e ?? c.delta_e ?? 0);
              const maxDe = notChecked ? '—' : (c.threshold_delta_e ?? c.max_delta_e ?? 14);
              return `
                <tr data-table-cell-id="${escapeHtml(c.cell_id)}" class="${c.flagged ? 'heatmap-row-flagged' : ''}">
                  <td class="mono-id"><strong>${escapeHtml(c.cell_id)}</strong></td>
                  <td>
                    <span class="color-dot-inline" style="background:${escapeHtml(c.dominant_hex || '#FFFFFF')};" aria-hidden="true"></span>
                    <span class="mono-id">${escapeHtml(c.dominant_hex || 'Transparent')}</span>
                  </td>
                  <td>
                    <span class="color-dot-inline" style="background:${escapeHtml(c.closest_brand_hex || '#FFFFFF')};" aria-hidden="true"></span>
                    <span>${escapeHtml(c.closest_brand_color || 'None')}</span>
                    <span class="mono-id" style="font-size: 11px;">(${escapeHtml(c.closest_brand_hex || '—')})</span>
                  </td>
                  <td class="mono-id">${deVal}</td>
                  <td class="mono-id">${maxDe}</td>
                  <td>
                    ${notChecked
                      ? '<span class="status-badge badge-neutral"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/></svg><span>Not checked</span></span>'
                      : c.flagged
                      ? '<span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>FAIL · Diagonal Hatch</span></span>'
                      : '<span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>PASS · Solid</span></span>'}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-color);">
      ${docHtml}
    </div>
  `;

  const canvas = document.getElementById('heatmapOverlayCanvas');
  let baseImg = null;
  if (audit.visual_asset_b64) {
    baseImg = new Image();
    baseImg.onload = () => {
      drawHeatmapCanvasOverlay(canvas, hm, layers, AppState.focusedHeatmapCellId || focusedCellId, baseImg);
    };
    baseImg.src = audit.visual_asset_b64;
  }
  drawHeatmapCanvasOverlay(canvas, hm, layers, focusedCellId, baseImg);

  viewer.querySelectorAll('.heatmap-layer-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const k = btn.getAttribute('data-hm-layer');
      layers[k] = !layers[k];
      btn.classList.toggle('active', layers[k]);
      btn.setAttribute('aria-pressed', layers[k] ? 'true' : 'false');
      drawHeatmapCanvasOverlay(canvas, hm, layers, AppState.focusedHeatmapCellId || focusedCellId, baseImg);
    });
  });

  viewer.querySelectorAll('.heatmap-cell-btn').forEach((btn) => {
    const onFocusOrClick = () => {
      const cid = btn.getAttribute('data-cell-id');
      AppState.focusedHeatmapCellId = cid;
      viewer.querySelectorAll('.heatmap-cell-btn').forEach((b) => b.classList.toggle('is-focused', b.getAttribute('data-cell-id') === cid));
      drawHeatmapCanvasOverlay(canvas, hm, layers, cid, baseImg);
      // Also select matching finding in the center rail if one cites this cell
      const matchingFinding = (audit.findings || []).find((f) => String(f.paragraph_ref || '').includes(cid) || String(f.flagged_text || '').includes(cid));
      if (matchingFinding) {
        AppState.selectedFindingId = matchingFinding.id;
        renderFindingsCenterPanel();
        renderCorrectionRightPanel();
      }
    };
    btn.addEventListener('click', onFocusOrClick);
    btn.addEventListener('focus', onFocusOrClick);
  });

  const gridSel = document.getElementById('heatmapGridSizeSelect');
  const logoChk = document.getElementById('heatmapLogoOnlyCheckbox');
  const triggerHeatmapReinspect = async (customRect) => {
    try {
      const res = await apiFetch(`/api/audits/${encodeURIComponent(audit.id)}/heatmap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grid_size: Number(gridSel?.value || n),
          logo_only: Boolean(logoChk?.checked),
          logo_rect: customRect !== undefined ? customRect : (cs.logo_box || null),
        }),
      });
      if (res && res.audit) {
        AppState.currentAudit = res.audit;
        renderAuditWorkspace();
      }
    } catch (err) {
      showToast(`Heatmap update failed: ${err.message}`);
    }
  };

  if (gridSel) {
    gridSel.addEventListener('change', () => triggerHeatmapReinspect());
  }
  if (logoChk) {
    logoChk.addEventListener('change', () => triggerHeatmapReinspect(null));
  }

  const drawBtn = document.getElementById('heatmapDrawLogoBtn');
  if (drawBtn && canvas) {
    drawBtn.addEventListener('click', () => {
      AppState.drawingLogoRect = !AppState.drawingLogoRect;
      drawBtn.setAttribute('aria-pressed', AppState.drawingLogoRect ? 'true' : 'false');
      drawBtn.textContent = AppState.drawingLogoRect ? 'Drag on image above...' : 'Mark logo box';
      const gridOverlay = document.getElementById('heatmapFocusableGrid');
      if (gridOverlay) {
        gridOverlay.style.pointerEvents = AppState.drawingLogoRect ? 'none' : 'auto';
      }
    });

    let dragStart = null;
    canvas.addEventListener('mousedown', (e) => {
      if (!AppState.drawingLogoRect) return;
      const rect = canvas.getBoundingClientRect();
      dragStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    });
    canvas.addEventListener('mouseup', async (e) => {
      if (!AppState.drawingLogoRect || !dragStart) return;
      const rect = canvas.getBoundingClientRect();
      const endX = e.clientX - rect.left;
      const endY = e.clientY - rect.top;
      AppState.drawingLogoRect = false;
      const aw = hm.analyzed_width || hm.original_width || canvas.width;
      const ah = hm.analyzed_height || hm.original_height || canvas.height;
      const scaleX = aw / Math.max(1, rect.width);
      const scaleY = ah / Math.max(1, rect.height);
      const x = Math.max(0, Math.min(dragStart.x, endX) * scaleX);
      const y = Math.max(0, Math.min(dragStart.y, endY) * scaleY);
      const width = Math.max(8, Math.abs(endX - dragStart.x) * scaleX);
      const height = Math.max(8, Math.abs(endY - dragStart.y) * scaleY);
      dragStart = null;
      await triggerHeatmapReinspect({ x, y, width, height });
    });
  }
}

async function renderAmbiguityRadarView() {
  const container = document.getElementById('ambiguityRadarContainer');
  if (container && !AppState.lastRefreshed.radar) {
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">
        Loading guideline insights...
      </div>
    `;
  }
  try {
    const data = await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}`);
    AppState.lastRefreshed.radar = new Date().toISOString();
    const rows = data.rules_analysis || [];
    const conciseNote = data.concise_info_note || 'Frequent overrides are a signal to review a rule, not proof it is incorrect.';
    const canEditVault = hasFrontendPermission('edit_brand_vault');
    const minSampleReq = data.min_sample_required || 5;
    const sampleAuditsCnt = data.sample_audits_count ?? 0;
    const hasSufficientSample = Boolean(data.sufficient_sample);

    if (rows.length === 0) {
      container.innerHTML = `
        <div class="empty-state-box">
          <h3>No guideline rules configured for this brand</h3>
          <p>Add rules in the Brand Vault to evaluate ambiguity scores, reviewer override correlation, and candidate rewrites.</p>
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last checked: ${escapeHtml(formatTimestamp(AppState.lastRefreshed.radar))}</div>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="card" style="margin-bottom: 16px; padding: 14px 18px; background-color: var(--bg-main);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div>
            <div style="font-size: 13.5px; color: var(--text-primary); font-weight: 600;">
              ${escapeHtml(conciseNote)}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Every candidate rewrite is a <strong>suggestion for human sign-off</strong> — nothing is applied automatically.
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span class="status-badge ${hasSufficientSample ? 'badge-passed' : 'badge-neutral'}" title="Minimum sample threshold for override rate correlation">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
              <span>Sample: ${sampleAuditsCnt} / ${minSampleReq} audits (${hasSufficientSample ? 'Sufficient sample' : 'Not enough data'})</span>
            </span>
            ${data.sample_audits_note ? `
              <span class="status-badge badge-neutral" style="font-size: 11px;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                <span>${escapeHtml(data.sample_audits_note)}</span>
              </span>
            ` : ''}
            <span style="font-size: 11px; color: var(--text-secondary);">
              Brand Vault v${data.brand_version || 1} &bull; Updated ${escapeHtml(formatTimestamp(AppState.lastRefreshed.radar))}
            </span>
          </div>
        </div>
      </div>

      <div class="insights-stack">
        ${rows.map((r, idx) => {
          const hasFeedback = (r.recorded_feedback || []).length > 0;
          const ambScore = r.ambiguity_score ?? 0;
          const formulaStr = r.ambiguity_formula || 'score = min(100, sum(qualifier_weights) + 20*no_numeric + 15*no_examples + 15*subjective_only)';
          const reasonsList = r.ambiguity_reasons || [];
          const cand = r.candidate_rewrite || {};
          const doExamples = cand.do_examples || [];
          const dontExamples = cand.dont_examples || [];
          const loopClosure = r.loop_closure || null;
          const latestProposed = (r.revisions || []).find((rv) => rv.status === 'proposed');
          const priorityBadgeClass = r.priority === 'High' ? 'badge-error' : (r.priority === 'Medium' ? 'badge-warning' : 'badge-neutral');

          return `
            <details class="insight-card" data-rule-card="${escapeHtml(r.rule_id)}" ${idx === 0 || r.priority === 'High' || r.overrides_recorded > 0 ? 'open' : ''}>
              <summary class="insight-card-summary">
                <div class="insight-card-main">
                  <span class="mono-id">${escapeHtml(r.rule_id)} · v${r.version}</span>
                  <div class="insight-card-title">${escapeHtml(r.title)}</div>
                  <span class="status-badge badge-neutral" style="font-size: 11px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${escapeHtml(r.pillar)}</span></span>
                </div>
                <div class="insight-card-meta">
                  <span class="status-badge ${priorityBadgeClass}" title="Priority derived from ambiguity score and override rate">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                    <span>Priority: ${escapeHtml(r.priority || 'Low')}</span>
                  </span>
                  <span class="status-badge ${ambScore >= 35 ? 'badge-warning' : 'badge-neutral'} ambiguity-score-badge" title="${escapeHtml(formulaStr)}" tabindex="0" aria-label="Ambiguity score ${ambScore} out of 100. Formula: ${escapeHtml(formulaStr)}">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                    <span>Ambiguity: ${ambScore}/100</span>
                  </span>
                  <span class="status-badge badge-neutral">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                    <span>Override rate: ${escapeHtml(r.override_rate_display || 'Not enough data')}</span>
                  </span>
                  <span class="status-badge badge-neutral">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                    <span>${escapeHtml(r.classification_label || 'Not enough data')}</span>
                  </span>
                  <span class="insight-card-chevron" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                  </span>
                </div>
              </summary>
              <div class="insight-card-body">
                ${loopClosure ? `
                  <div class="loop-closure-banner" style="padding: 10px 12px; background: var(--status-success-bg); border: 1px solid var(--status-success-border); border-radius: var(--radius-control); font-size: 13px; color: var(--slate-800);">
                    <div><strong>Loop closure:</strong> ${escapeHtml(loopClosure.display)}</div>
                    <div class="loop-closure-caveat" style="margin-top: 4px; font-size: 12px; color: var(--slate-700);">
                      <strong>Sample status:</strong> ${escapeHtml(loopClosure.minimum_sample_caveat || '')}
                    </div>
                    <div class="loop-closure-side-by-side" style="margin-top: 8px; overflow-x: auto;">
                      <table class="data-table" style="width: 100%; font-size: 12px; background: #FFFFFF; border-radius: 4px;">
                        <thead>
                          <tr>
                            <th scope="col" style="padding: 4px 8px;">Metric</th>
                            <th scope="col" style="padding: 4px 8px;">Before Approval (&le; ${escapeHtml(loopClosure.revised_date || '')})</th>
                            <th scope="col" style="padding: 4px 8px;">After Approval (&gt; ${escapeHtml(loopClosure.revised_date || '')})</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td style="padding: 4px 8px;">Audits counted</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.before ? loopClosure.before.audits_counted : 0}</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.after ? loopClosure.after.audits_counted : 0}</td>
                          </tr>
                          <tr>
                            <td style="padding: 4px 8px;">Violations</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.before ? loopClosure.before.violations : 0}</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.after ? loopClosure.after.violations : 0}</td>
                          </tr>
                          <tr>
                            <td style="padding: 4px 8px;">Reviewer overrides</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.before ? loopClosure.before.overrides : 0}</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.after ? loopClosure.after.overrides : 0}</td>
                          </tr>
                          <tr>
                            <td style="padding: 4px 8px;">Dismissals</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.before ? loopClosure.before.dismissals : 0}</td>
                            <td class="mono-id" style="padding: 4px 8px;">${loopClosure.after ? loopClosure.after.dismissals : 0}</td>
                          </tr>
                          <tr>
                            <td style="padding: 4px 8px;">Override rate</td>
                            <td class="mono-id" style="padding: 4px 8px;"><strong>${loopClosure.before ? escapeHtml(loopClosure.before.override_rate_display) : '—'}</strong></td>
                            <td class="mono-id" style="padding: 4px 8px;"><strong>${loopClosure.after ? escapeHtml(loopClosure.after.override_rate_display) : '—'}</strong></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div class="scoring-disclosure" style="margin-top: 6px; font-size: 11px; color: var(--slate-600); font-style: italic;">
                      ${escapeHtml(loopClosure.scoring_factors_disclosure || 'Score evaluates vagueness indicators, missing measurable criteria, override and dismissal rates, and accepted corrections.')}
                    </div>
                  </div>
                ` : ''}

                <div class="insight-detail-row">
                  <span class="insight-detail-label">Current guideline wording (vague spans highlighted)</span>
                  <div class="insight-detail-value rule-highlighted-text">${renderRuleTextWithVagueSpans(r.description, r.matched_spans)}</div>
                </div>

                <div class="insight-detail-row">
                  <span class="insight-detail-label">Deterministic ambiguity score &amp; formula</span>
                  <div class="insight-detail-value" style="font-size: 13px;">
                    <div><strong>Score:</strong> <span class="mono-id">${ambScore} / 100</span> &bull; <strong>Formula:</strong> <code class="mono-id" style="font-size: 11.5px;">${escapeHtml(formulaStr)}</code></div>
                    ${reasonsList.length > 0 ? `
                      <ul style="margin: 6px 0 0 18px; color: var(--slate-700);">
                        ${reasonsList.map((rsn) => `<li>${escapeHtml(rsn)}</li>`).join('')}
                      </ul>
                    ` : `<div style="color: var(--slate-600); margin-top: 4px;">No vague qualifiers or structural ambiguity triggers detected.</div>`}
                  </div>
                </div>

                <div class="insight-detail-row">
                  <span class="insight-detail-label">Override correlation &amp; telemetry</span>
                  <div class="insight-detail-value" style="font-size: 13px;">
                    <strong>Status:</strong> ${escapeHtml(r.classification_label || 'Not enough data')} &bull;
                    <strong>Override rate:</strong> ${escapeHtml(r.override_rate_display || 'Not enough data')}
                    (${r.overrides_recorded} override(s) / ${r.violations_recorded} finding(s) across ${r.sample_audits_count ?? sampleAuditsCnt} brand audit(s); min sample = ${r.min_sample_required ?? minSampleReq})
                  </div>
                </div>

                ${hasFeedback ? `
                  <div class="insight-detail-row">
                    <span class="insight-detail-label">Logged reviewer dismissals &amp; override justifications</span>
                    <ul style="padding-left: 18px; margin-top: 4px; font-size: 13px; color: var(--text-primary);">
                      ${r.recorded_feedback.map((fb) => `
                        <li style="margin-bottom: 4px;">"${escapeHtml(fb.override_reason)}" &bull; <span class="mono-id">${escapeHtml(fb.audit_id)}</span></li>
                      `).join('')}
                    </ul>
                  </div>
                ` : ''}

                <!-- B3 & B6: Side-by-Side Diff & Suggestion for Human Sign-Off -->
                <div class="clarity-rewriter-box" style="background: var(--slate-50); border: 1px solid var(--border-color); border-radius: var(--radius-card); padding: 14px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
                    <div>
                      <span class="insight-detail-label" style="color: var(--primary-action);">Guideline Clarity Rewriter — Suggestion for human sign-off</span>
                      <div style="font-size: 12px; color: var(--slate-600);">Quantified thresholds come strictly from the rule text or Verified Facts; otherwise an explicit placeholder is inserted.</div>
                    </div>
                    ${cand.improved ? `
                      <span class="status-badge badge-passed">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                        <span>Ambiguity ${cand.ambiguity_before}/100 &rarr; ${cand.ambiguity_after}/100</span>
                      </span>
                    ` : `
                      <span class="status-badge badge-neutral">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>
                        <span>${escapeHtml(cand.message || 'no improvement found')}</span>
                      </span>
                    `}
                  </div>

                  <div class="clarity-diff-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px;">
                    <div class="clarity-diff-col" style="background: var(--surface-solid); border: 1px solid var(--border-color); border-radius: var(--radius-control); padding: 10px 12px;">
                      <div style="font-size: 11.5px; font-weight: 700; color: var(--slate-600); text-transform: uppercase; margin-bottom: 4px;">
                        Before (Ambiguity ${cand.ambiguity_before ?? ambScore}/100)
                      </div>
                      <div style="font-size: 13px; color: var(--text-primary);">${renderRuleTextWithVagueSpans(cand.old_text || r.description, r.matched_spans)}</div>
                    </div>
                    <div class="clarity-diff-col" style="background: var(--surface-solid); border: 1px solid ${cand.improved ? 'var(--status-success-border)' : 'var(--border-color)'}; border-radius: var(--radius-control); padding: 10px 12px;">
                      <div style="font-size: 11.5px; font-weight: 700; color: var(--slate-700); text-transform: uppercase; margin-bottom: 4px;">
                        After — Suggestion for human sign-off (Ambiguity ${cand.ambiguity_after ?? ambScore}/100)
                      </div>
                      ${cand.improved ? `
                        <div style="font-size: 13px; color: var(--text-primary); font-weight: 500;">${escapeHtml(cand.new_text)}</div>
                        <div style="margin-top: 6px; font-size: 11.5px; color: var(--slate-600);">
                          <strong>Threshold source:</strong>
                          ${cand.cited_fact_id
                            ? `Verified Fact <span class="mono-id">${escapeHtml(cand.cited_fact_id)}</span>`
                            : (cand.threshold_source === 'rule_text' ? 'Existing numeric token in rule text' : 'Explicit placeholder <span class="mono-id">[SET THRESHOLD: unit]</span>')}
                        </div>
                      ` : `
                        <div style="font-size: 13px; color: var(--slate-600); font-style: italic;">no improvement found — current wording is already concise or requires manual authoring.</div>
                      `}
                    </div>
                  </div>

                  <!-- Do / Don't Examples with Provenance -->
                  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 12px;">
                    <div style="background: var(--surface-solid); border: 1px solid var(--border-color); border-radius: var(--radius-control); padding: 10px 12px;">
                      <div style="font-size: 11.5px; font-weight: 700; color: #067647; text-transform: uppercase; margin-bottom: 6px;">Do Example(s) &amp; Provenance</div>
                      ${doExamples.map((ex) => `
                        <div style="font-size: 12.5px; margin-bottom: 6px;">
                          <div>"${escapeHtml(ex.text)}"</div>
                          <div style="margin-top: 2px;"><span class="mono-id" style="font-size: 11px;">Provenance: ${escapeHtml(ex.provenance)}</span></div>
                        </div>
                      `).join('')}
                    </div>
                    <div style="background: var(--surface-solid); border: 1px solid var(--border-color); border-radius: var(--radius-control); padding: 10px 12px;">
                      <div style="font-size: 11.5px; font-weight: 700; color: #B42318; text-transform: uppercase; margin-bottom: 6px;">Don't Example(s) &amp; Provenance</div>
                      ${dontExamples.map((ex) => `
                        <div style="font-size: 12.5px; margin-bottom: 6px;">
                          <div>"${escapeHtml(ex.text)}"</div>
                          <div style="margin-top: 2px;"><span class="mono-id" style="font-size: 11px;">Provenance: ${escapeHtml(ex.provenance)}</span></div>
                        </div>
                      `).join('')}
                    </div>
                  </div>

                  <!-- Role-gated Approve / Reject Controls -->
                  <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div style="font-size: 12px; color: var(--slate-600);">
                      ${canEditVault
                        ? 'Brand Administrator sign-off: approving updates the rule, increments Brand Vault version, and logs an audit event.'
                        : `Role "${escapeHtml(AppState.activeRole)}" is read-only here. Sign in as Brand Administrator to approve or reject guideline revisions.`}
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                      <button
                        type="button"
                        class="btn btn-sm btn-accent clarity-approve-btn"
                        data-rule-id="${escapeHtml(r.rule_id)}"
                        data-proposed-id="${escapeHtml(latestProposed ? latestProposed.id : '')}"
                        ${(!canEditVault || !cand.improved) ? 'disabled' : ''}
                      >
                        Approve rewrite
                      </button>
                      <button
                        type="button"
                        class="btn btn-sm btn-danger-outline clarity-reject-btn"
                        data-rule-id="${escapeHtml(r.rule_id)}"
                        data-proposed-id="${escapeHtml(latestProposed ? latestProposed.id : '')}"
                        ${(!canEditVault || !cand.improved) ? 'disabled' : ''}
                      >
                        Reject
                      </button>
                      <button type="button" class="btn btn-sm inspect-rule-vault-btn" data-rule-id="${escapeHtml(r.rule_id)}">
                        Open in Brand Vault &rarr;
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </details>
          `;
        }).join('')}
      </div>
    `;

    container.querySelectorAll('.inspect-rule-vault-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        AppState.activeVaultTab = 'voice';
        switchView('brand-vault');
      });
    });

    container.querySelectorAll('.clarity-approve-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const ruleId = btn.getAttribute('data-rule-id');
        const propId = btn.getAttribute('data-proposed-id');
        btn.disabled = true;
        try {
          let res;
          if (propId) {
            res = await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}/revisions/${encodeURIComponent(propId)}/approve`, {
              method: 'POST',
            });
          } else {
            res = await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}/rules/${encodeURIComponent(ruleId)}/approve`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({}),
            });
          }
          showToast(`Approved revision for ${ruleId} (Brand Vault bumped to v${res.brand_version_after}).`);
          await renderAmbiguityRadarView();
        } catch (err) {
          btn.disabled = false;
          showToast(`Cannot approve revision: ${err.message}`);
        }
      });
    });

    container.querySelectorAll('.clarity-reject-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const ruleId = btn.getAttribute('data-rule-id');
        let propId = btn.getAttribute('data-proposed-id');
        btn.disabled = true;
        try {
          if (!propId) {
            const prop = await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}/rules/${encodeURIComponent(ruleId)}/propose`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({}),
            });
            propId = prop.id;
          }
          await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}/revisions/${encodeURIComponent(propId)}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Rejected by Brand Administrator in Guideline Insights.' }),
          });
          showToast(`Rejected candidate rewrite for ${ruleId}. Brand Vault unchanged.`);
          await renderAmbiguityRadarView();
        } catch (err) {
          btn.disabled = false;
          showToast(`Cannot reject revision: ${err.message}`);
        }
      });
    });
  } catch (err) {
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.radar ? formatTimestamp(AppState.lastRefreshed.radar) : 'Never';
    if (container) {
      container.innerHTML = `
        <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
          <h3 style="color: #B42318;">Could not retrieve guideline insights</h3>
          <p style="color: #475467;">${escapeHtml(err.message)}</p>
          ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
          ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
          ${action.canRetry ? `<button type="button" class="btn btn-sm btn-accent" id="retryRadarBtn" style="margin-top: 12px;">${escapeHtml(action.retryLabel || 'Retry')}</button>` : ''}
        </div>
      `;
      const retryBtn = document.getElementById('retryRadarBtn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderAmbiguityRadarView());
    }
  }
}

async function _legacyRenderAmbiguityRadarViewUnused() {
  const container = document.getElementById('ambiguityRadarContainer');
  if (container && !AppState.lastRefreshed.radar) {
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">
        Loading guideline insights...
      </div>
    `;
  }
  try {
    const data = await apiFetch(`/api/ambiguity-radar/${encodeURIComponent(AppState.activeBrandId)}`);
    AppState.lastRefreshed.radar = new Date().toISOString();
    const rows = data.rules_analysis || [];
    const conciseNote = data.concise_info_note || 'Frequent overrides are a signal to review a rule, not proof it is incorrect.';

    if (rows.length === 0) {
      container.innerHTML = `
        <div class="empty-state-box">
          <h3>No rule ambiguities or frequent overrides detected</h3>
          <p>As reviewers evaluate audits and record finding dismissals or override justifications, patterns and wording recommendations will appear here.</p>
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last checked: ${escapeHtml(formatTimestamp(AppState.lastRefreshed.radar))}</div>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="card" style="margin-bottom: 16px; padding: 14px 18px; background-color: var(--bg-main);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="font-size: 13.5px; color: var(--text-primary); font-weight: 500;">
            ${escapeHtml(conciseNote)}
          </div>
          <div style="font-size: 11px; color: var(--text-secondary);">
            Last updated: ${escapeHtml(formatTimestamp(AppState.lastRefreshed.radar))}
          </div>
        </div>
      </div>

      <div class="insights-stack">
        ${rows.map((r, idx) => {
          const hasFeedback = (r.recorded_feedback || []).length > 0;
          const isHighAttention = r.overrides_recorded > 0 || r.recommendation_status === 'Review wording';
          return `
            <details class="insight-card" ${idx === 0 || isHighAttention ? 'open' : ''}>
              <summary class="insight-card-summary">
                <div class="insight-card-main">
                  <span class="mono-id">${escapeHtml(r.rule_id)} · v${r.version}</span>
                  <div class="insight-card-title">${escapeHtml(r.title)}</div>
                  <span class="status-badge badge-neutral" style="font-size: 11px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${escapeHtml(r.pillar)}</span></span>
                </div>
                <div class="insight-card-meta">
                  <span class="status-badge badge-neutral"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${r.violations_recorded} violation(s)</span></span>
                  <span class="status-badge ${r.overrides_recorded > 0 ? 'badge-warning' : 'badge-neutral'}">${r.overrides_recorded > 0 ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>'}<span>${r.overrides_recorded} override(s)</span></span>
                  ${renderStateBadge(r.recommendation_status)}
                  <span class="insight-card-chevron" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                  </span>
                </div>
              </summary>
              <div class="insight-card-body">
                <div class="insight-detail-row">
                  <span class="insight-detail-label">Current guideline wording</span>
                  <div class="insight-detail-value">${escapeHtml(r.description)}</div>
                </div>

                <div class="insight-detail-row">
                  <span class="insight-detail-label">Enforcement signal</span>
                  <div class="insight-detail-value">${escapeHtml(r.likely_signal || (r.potential_causes && r.potential_causes[0]) || 'Consistent enforcement')}</div>
                </div>

                ${(r.potential_causes || []).length > 0 ? `
                  <div class="insight-detail-row">
                    <span class="insight-detail-label">Potential causes</span>
                    <div class="insight-detail-value">${escapeHtml(r.potential_causes.join('; '))}</div>
                  </div>
                ` : ''}

                ${hasFeedback ? `
                  <div class="insight-detail-row">
                    <span class="insight-detail-label">Logged reviewer dismissals &amp; override justifications</span>
                    <ul style="padding-left: 18px; margin-top: 4px; font-size: 13.5px; color: var(--text-primary);">
                      ${r.recorded_feedback.map((fb) => `
                        <li style="margin-bottom: 4px;">"${escapeHtml(fb.override_reason)}" &bull; <span class="mono-id">${escapeHtml(fb.audit_id)}</span></li>
                      `).join('')}
                    </ul>
                  </div>
                ` : ''}

                ${r.suggested_clarification ? `
                  <div class="insight-recommendation-box">
                    <div class="insight-detail-label" style="color: var(--primary-action); margin-bottom: 4px;">Suggested clarification for administrator review</div>
                    <div style="font-size: 13.5px; color: var(--text-primary);">${escapeHtml(r.suggested_clarification)}</div>
                  </div>
                ` : ''}

                <div style="display: flex; justify-content: flex-end; padding-top: 8px;">
                  <button type="button" class="btn btn-sm btn-accent inspect-rule-vault-btn" data-rule-id="${escapeHtml(r.rule_id)}">
                    Review in Brand Vault &rarr;
                  </button>
                </div>
              </div>
            </details>
          `;
        }).join('')}
      </div>
    `;

    container.querySelectorAll('.inspect-rule-vault-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        AppState.activeVaultTab = 'voice';
        switchView('brand-vault');
      });
    });
  } catch (err) {
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.radar ? formatTimestamp(AppState.lastRefreshed.radar) : 'Never';
    if (container) {
      container.innerHTML = `
        <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
          <h3 style="color: #B42318;">Could not retrieve guideline insights</h3>
          <p style="color: #475467;">${escapeHtml(err.message)}</p>
          ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
          ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
          ${action.canRetry ? `<button type="button" class="btn btn-sm btn-accent" id="retryRadarBtn" style="margin-top: 12px;">${escapeHtml(action.retryLabel || 'Retry')}</button>` : ''}
        </div>
      `;
      const retryBtn = document.getElementById('retryRadarBtn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderAmbiguityRadarView());
    }
  }
}

// ============================================================================
// VIEW 6: AUDIT HISTORY (SECTION 07 — REAL DIFF, NO RAW TAGS, TIMELINE)
// ============================================================================

async function renderAuditHistoryView() {
  const container = document.getElementById('auditHistoryContainer');
  if (container && !AppState.lastRefreshed.history) {
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">
        Loading audit history...
      </div>
    `;
  }
  try {
    const res = await apiFetch(`/api/audits?brand_id=${encodeURIComponent(AppState.activeBrandId)}&limit=100`);
    AppState.lastRefreshed.history = new Date().toISOString();
    const audits = res.audits || [];

    if (audits.length === 0) {
      container.innerHTML = `
        <div class="empty-state-box">
          <h3>No audit history for this brand yet</h3>
          <p>Completed audits, content revisions, and approval events will appear here.</p>
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last checked: ${escapeHtml(formatTimestamp(AppState.lastRefreshed.history))}</div>
        </div>
      `;
      return;
    }

    if (!AppState.selectedHistoryAuditId || !audits.some((a) => a.id === AppState.selectedHistoryAuditId)) {
      AppState.selectedHistoryAuditId = audits[0].id;
    }
    const detail = await apiFetch(`/api/audits/${encodeURIComponent(AppState.selectedHistoryAuditId)}`);
    const revCount = (detail.revisions || []).length || 1;
    const isIdentical = detail.original_content === detail.current_content;
    const rightPaneLabel = isIdentical
      ? 'No changes yet (identical to v1)'
      : `Revised content (v${revCount})`;

    const origRendered = AppState.historyFormatView === 'source'
      ? `<div class="source-content-viewer raw-source-mode">${escapeHtml(detail.original_content)}</div>`
      : `<div class="source-content-viewer">${renderSafeDocumentHtml(detail.original_content, [], null, 'rendered')}</div>`;

    const diffRendered = isIdentical
      ? `<div class="source-content-viewer ${AppState.historyFormatView === 'source' ? 'raw-source-mode' : ''}">
           <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 8px;"><em>No revisions have been applied to this document yet. Content matches v1.</em></div>
           ${AppState.historyFormatView === 'source' ? escapeHtml(detail.current_content) : renderSafeDocumentHtml(detail.current_content, [], null, 'rendered')}
         </div>`
      : `<div class="source-content-viewer ${AppState.historyFormatView === 'source' ? 'raw-source-mode' : ''}">
           ${computeWordDiffHtml(detail.original_content, detail.current_content, AppState.historyFormatView)}
         </div>`;

    const selectedIdx = audits.findIndex((a) => a.id === detail.id);
    const displayIdx = selectedIdx >= 0 ? selectedIdx + 1 : 1;

    container.innerHTML = `
      <div class="card" style="margin-bottom: 16px;">
        <div class="card-header">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <label for="historyAuditSelect" style="font-size: 13px; font-weight: 600;">Audit record:</label>
            <select id="historyAuditSelect" class="form-control" style="width: auto;">
              ${audits.map((a) => `
                <option value="${escapeHtml(a.id)}" ${a.id === detail.id ? 'selected' : ''}>
                  ${escapeHtml(a.id)} — ${escapeHtml(a.document_name)} ${(a.id.startsWith('AUD-100') || (a.document_name && (a.document_name.includes('sample data') || a.document_name.includes('(Demo)')))) ? '(Sample data) ' : ''}(${escapeHtml(normalizeStatusDisplay(a.overall_status))})
                </option>
              `).join('')}
            </select>
            ${renderStateBadge(detail.overall_status)}
            <span style="font-size: 12px; color: var(--text-secondary); margin-left: 4px;">Submitted by: <strong>${escapeHtml(detail.submitted_by_name || '—')}</strong></span>
            <span style="font-size: 11.5px; color: var(--text-secondary); margin-left: 4px;">(Record ${displayIdx} of ${audits.length})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <div class="segmented-toggle" role="group" aria-label="History content format">
              <button type="button" class="segmented-btn ${AppState.historyFormatView === 'rendered' ? 'active' : ''}" id="histViewRenderedBtn">Rendered</button>
              <button type="button" class="segmented-btn ${AppState.historyFormatView === 'source' ? 'active' : ''}" id="histViewSourceBtn">Source</button>
            </div>
            ${detail.overall_status === 'Approved' ? `
              <button type="button" class="btn btn-sm btn-success" id="histCertificateBtn">Certificate</button>
            ` : ''}
            <button type="button" class="btn btn-sm" id="histOpenWorkspaceBtn">Open review</button>
          </div>
        </div>

        <div class="diff-comparison-grid two-col">
          <div>
            <span class="diff-pane-label" style="margin-bottom: 6px;">Original submitted snapshot (v1)</span>
            ${origRendered}
          </div>
          <div>
            <span class="diff-pane-label" style="margin-bottom: 6px;">${escapeHtml(rightPaneLabel)}</span>
            ${diffRendered}
          </div>
        </div>
      </div>

      <div class="card" style="margin-top: 16px;">
        <div class="card-header" style="margin-bottom: 14px;">
          <div>
            <h2 class="card-title">Approval &amp; content-integrity events</h2>
            <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 2px;">
              Cryptographic SHA-256 verification and reviewer sign-offs recorded for this document.
            </div>
          </div>
          ${(detail.approvals || []).length > 0 ? `<span class="status-badge badge-neutral"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${(detail.approvals || []).length} event(s)</span></span>` : ''}
        </div>
        ${(detail.approvals || []).length === 0 ? `
          <div class="empty-state-box" style="padding: 24px 16px; margin: 0;">
            <p style="margin: 0; font-size: 13.5px; color: var(--text-secondary);">No approval events recorded yet.</p>
          </div>
        ` : `
          <div class="version-timeline">
            ${(detail.approvals || []).map((ap) => `
              <div class="timeline-item">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  ${renderStateBadge(ap.previous_state)}
                  <span>&rarr;</span>
                  ${renderStateBadge(ap.new_state)}
                  <span class="mono-id">v${ap.version_reviewed}</span>
                  <span style="font-size: 12px; color: var(--text-secondary);" title="${escapeHtml(ap.created_at)}">
                    ${escapeHtml(formatTimestamp(ap.created_at))}
                  </span>
                </div>
                <div style="font-size: 13.5px; margin-top: 6px; color: var(--text-primary);">
                  <strong>${escapeHtml(ap.approver_name ? `${ap.approver_name} (${ap.approver_role})` : ap.approver_role)}:</strong> ${escapeHtml(ap.comment)}
                </div>
                <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 4px;">
                  SHA-256: <span class="mono-id" style="font-size: 11px;">${escapeHtml(ap.content_sha256.slice(0, 24))}...</span>
                </div>
              </div>
            `).join('')}
          </div>
        `}
      </div>
    `;

    document.getElementById('historyAuditSelect').addEventListener('change', async (e) => {
      AppState.selectedHistoryAuditId = e.target.value;
      await renderAuditHistoryView();
    });

    document.getElementById('histViewRenderedBtn').addEventListener('click', () => {
      AppState.historyFormatView = 'rendered';
      renderAuditHistoryView();
    });

    document.getElementById('histViewSourceBtn').addEventListener('click', () => {
      AppState.historyFormatView = 'source';
      renderAuditHistoryView();
    });

    document.getElementById('histOpenWorkspaceBtn').addEventListener('click', () => {
      openAuditById(detail.id);
    });

    const histCertBtn = document.getElementById('histCertificateBtn');
    if (histCertBtn) {
      histCertBtn.addEventListener('click', () => {
        openCertificateModal(detail.id);
      });
    }
  } catch (err) {
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.history ? formatTimestamp(AppState.lastRefreshed.history) : 'Never';
    if (container) {
      container.innerHTML = `
        <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
          <h3 style="color: #B42318;">Could not retrieve audit history</h3>
          <p style="color: #475467;">${escapeHtml(err.message)}</p>
          ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
          ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
          ${action.canRetry ? `<button type="button" class="btn btn-sm btn-accent" id="retryHistoryBtn" style="margin-top: 12px;">${escapeHtml(action.retryLabel || 'Retry')}</button>` : ''}
        </div>
      `;
      const retryBtn = document.getElementById('retryHistoryBtn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderAuditHistoryView());
    }
  }
}

// ============================================================================
// VIEW 7 & 8: SETTINGS & PRIVACY / PROCESSING STATUS (SECTION 08)
// ============================================================================

function renderSettingsView() {
  const container = document.getElementById('settingsContainer');
  container.innerHTML = `
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-header">
        <div>
          <h2 class="card-title">Workspace preferences</h2>
          <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">
            Configure evaluation demo mode and default audit behaviour.
          </p>
        </div>
      </div>

      <div class="audit-options-grid">
        <div class="option-control-card">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;">
            <div>
              <div style="font-size: 13.5px; font-weight: 600;">Workspace deployment mode</div>
              <div class="form-helper">Server deployment environment configured via <code>LOOMSHIELD_WORKSPACE_MODE</code>.</div>
            </div>
            <span class="status-badge ${AppState.demoMode ? 'badge-warning' : 'badge-passed'}">
              ${AppState.demoMode ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>Demo Workspace</span>' : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Production Workspace</span>'}
            </span>
          </div>
        </div>

        <div class="option-control-card">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
            <div>
              <div style="font-size: 13.5px; font-weight: 600;">Privacy &amp; system diagnostics</div>
              <div class="form-helper">${AppState.processingMode === 'local' ? 'Inspect local processing engines, supported file formats, and run an on-device self-test.' : 'Inspect verification engines, supported file formats, and run an engine self-test.'}</div>
            </div>
            <button type="button" class="btn btn-sm" id="openPrivacyStatusFromSettingsBtn">Open system status</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h2 class="card-title">Team &amp; permissions</h2>
          <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">
            In production deployments, user roles come from organisation authentication. ${AppState.demoMode ? 'Because Demo mode is enabled, you can preview how each role interacts with approval and Brand Vault controls below.' : 'Role preview is available when the workspace is started with LOOMSHIELD_WORKSPACE_MODE=demo.'}
          </p>
        </div>
      </div>

      ${AppState.demoMode ? `
        <div style="background: var(--bg-main); padding: 14px 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="status-badge badge-warning"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>Demo role preview</span></span>
            <span style="font-size: 13px; margin-left: 8px;">Select role to preview permission boundaries:</span>
          </div>
          <select id="settingsRolePreviewSelect" class="form-control" style="width: auto;">
            <option value="Content Creator" ${AppState.activeRole === 'Content Creator' ? 'selected' : ''}>Content Creator</option>
            <option value="Reviewer" ${AppState.activeRole === 'Reviewer' ? 'selected' : ''}>Reviewer</option>
            <option value="Brand Administrator" ${AppState.activeRole === 'Brand Administrator' ? 'selected' : ''}>Brand Administrator</option>
          </select>
        </div>
      ` : ''}

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Role</th>
              <th>Audit &amp; correction access</th>
              <th>Approval authority</th>
              <th>Brand Vault &amp; fact verification</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Content Creator</strong></td>
              <td>Run audits, accept/edit suggestions, dismiss with reason</td>
              <td>Submit for review (cannot approve for publication)</td>
              <td>Read-only access; new facts default to Pending Verification</td>
            </tr>
            <tr>
              <td><strong>Reviewer</strong></td>
              <td>Inspect findings, evidence citations, and revision diffs</td>
              <td>Approve resolved audits or record justified overrides</td>
              <td>Read-only access to rules and verified facts</td>
            </tr>
            <tr>
              <td><strong>Brand Administrator</strong></td>
              <td>Full audit and review access</td>
              <td>Approve audits and review override telemetry</td>
              <td>Create/edit rules, mark facts Verified, and update thresholds</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Demo mode is server-configured and read-only

  document.getElementById('openPrivacyStatusFromSettingsBtn').addEventListener('click', () => {
    switchView('engine-status');
  });

  const roleSel = document.getElementById('settingsRolePreviewSelect');
  if (roleSel) {
    roleSel.addEventListener('change', (e) => {
      AppState.activeRole = e.target.value;
      updateTopbarContext();
      showToast(`Role preview set to ${AppState.activeRole}.`);
    });
  }
}

async function triggerEngineSelftest() {
  const btn = document.getElementById('runEngineSelftestHeaderBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Running self-test...';
  }
  try {
    const res = await apiFetch('/api/engine-selftest', { method: 'POST' });
    AppState.engineStatus = res.engine_status;
    await renderEngineStatusView();
    showToast(`Engine self-test completed (${res.selftest.status} in ${res.selftest.duration_ms} ms).`);
  } catch (err) {
    showToast(`Self-test failed: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Run engine self-test';
    }
  }
}

async function renderEngineStatusView() {
  const container = document.getElementById('engineStatusContainer');
  if (container && !AppState.lastRefreshed.engineStatus) {
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--text-secondary); font-size: 13px;">
        Loading engine status and verification telemetry...
      </div>
    `;
  }
  try {
    const status = await apiFetch('/api/engine-status');
    AppState.engineStatus = status;
    AppState.lastRefreshed.engineStatus = new Date().toISOString();

    const selftest = status.last_selftest || status.selftest;
    const lastCheckedHtml = selftest && (selftest.last_checked_at || status.last_selftest_time)
      ? `Last checked: <strong>${escapeHtml(formatTimestamp(selftest.last_checked_at || status.last_selftest_time))}</strong> (${selftest.duration_ms} ms)`
      : 'Self-test has not been run in this session yet. Click "Run engine self-test" above to verify.';

    const isLocal = status.processing_mode === 'local';
    const localOnlyBadge = status.local_only_mode || (isLocal ? 'On' : 'Off');
    const localOnlyNote = isLocal
      ? 'Audits and persistence run on this device'
      : `Audits execute on LoomShield backend (${escapeHtml(status.storage_type || 'ephemeral')} storage)`;

    container.innerHTML = `
      <!-- Concise Factual Summary Cards (Section 08) -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label"><span>Operating mode</span></div>
          <div style="margin: 10px 0 6px;">${renderStateBadge(localOnlyBadge)}</div>
          <div class="metric-note">${escapeHtml(localOnlyNote)}</div>
        </div>

        <div class="metric-card">
          <div class="metric-label"><span>Deterministic checks</span></div>
          <div style="margin: 10px 0 6px;">${renderStateBadge(selftest ? selftest.status : (status.deterministic_checks_status || 'Available'))}</div>
          <div class="metric-note">Terminology, patterns, contrast &amp; colour math</div>
        </div>

        <div class="metric-card">
          <div class="metric-label"><span>Embedded NLP</span></div>
          <div style="margin: 10px 0 6px;">${renderStateBadge(selftest ? selftest.status : (status.local_nlp_status || 'Available'))}</div>
          <div class="metric-note">Fact retrieval &amp; claim comparison</div>
        </div>

        <div class="metric-card">
          <div class="metric-label"><span>Storage &amp; records</span></div>
          <div style="margin: 10px 0 6px;">
            <span class="status-badge ${status.storage_type === 'persistent' ? 'badge-passed' : 'badge-neutral'}">
              ${status.storage_type === 'persistent' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Persistent disk</span>' : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>Ephemeral instance</span>'}
            </span>
          </div>
          <div class="metric-note">${status.record_counts && status.record_counts.audits !== undefined ? `${status.record_counts.audits} audits · ${status.record_counts.rules || 0} rules · ${status.record_counts.findings || 0} findings` : 'Zero external API keys'}</div>
        </div>
      </div>

      <div class="card" style="margin-bottom: 16px;">
        <div class="card-header">
          <div>
            <h2 class="card-title">Live engine verification</h2>
            <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 2px;">${lastCheckedHtml}</div>
          </div>
          ${selftest ? renderStateBadge(selftest.status) : renderStateBadge('Not Checked')}
        </div>

        ${selftest && selftest.checks ? `
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Verification check</th>
                  <th>Subsystem</th>
                  <th>Status</th>
                  <th>Measured result</th>
                </tr>
              </thead>
              <tbody>
                ${selftest.checks.map((c) => `
                  <tr>
                    <td><strong>${escapeHtml(c.name)}</strong></td>
                    <td>${escapeHtml(c.engine)}</td>
                    <td class="nowrap-col">${renderStateBadge(c.status)}</td>
                    <td style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(c.detail)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : `
          <p style="font-size: 13.5px; color: var(--text-secondary);">
            Run the engine self-test to execute live validation of the contrast calculator, colour distance engine, embedded fact retrieval model, and HTML/SVG markup sanitiser.
          </p>
        `}
      </div>

      <div class="card" style="margin-bottom: 16px;">
        <h2 class="card-title" style="margin-bottom: 10px;">Privacy scope &amp; supported file formats</h2>
        <p style="font-size: 13.5px; color: var(--text-secondary); margin-bottom: 10px;">
          <strong>Supported upload formats (max ${status.max_upload_size_mb} MB):</strong>
          ${(status.supported_formats || []).map((f) => `<span class="mono-id" style="margin-right: 4px;">.${escapeHtml(f)}</span>`).join('')}
        </p>
        <ul style="padding-left: 18px; font-size: 13.5px; line-height: 1.65; color: var(--text-primary);">
          <li><strong>Processing location:</strong> All six audit pillars, rule matching, fact retrieval, file parsing, and SQLite storage execute on the host running the LoomShield backend.</li>
          <li><strong>Persistence:</strong> Brand Vault rules, submitted content snapshots, revision history, and approval logs are stored in the SQLite database (${escapeHtml(status.storage_type || 'ephemeral')} storage).</li>
          <li><strong>External network policy:</strong> No external AI API key is required or configured. Fonts and styles are served locally from the application bundle.</li>
          ${(status.honest_limitations || []).map((lim) => `<li>${escapeHtml(lim)}</li>`).join('')}
        </ul>

        <details class="collapsible-details" style="margin-top: 16px;">
          <summary>Technical details &amp; architecture matrix</summary>
          <div class="collapsible-details-body">
            <div class="input-form-grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 14px;">
              <div>
                <strong>${escapeHtml(status.tier1_engine.name)}</strong>
                <ul style="padding-left: 18px; margin-top: 6px;">
                  ${(status.tier1_engine.capabilities || []).map((c) => `<li>${escapeHtml(c)}</li>`).join('')}
                </ul>
              </div>
              <div>
                <strong>${escapeHtml(status.tier2_engine.name)}</strong>
                <ul style="padding-left: 18px; margin-top: 6px;">
                  ${(status.tier2_engine.capabilities || []).map((c) => `<li>${escapeHtml(c)}</li>`).join('')}
                </ul>
              </div>
            </div>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Operating mode</th>
                    <th>API key required?</th>
                    <th>NLP capability</th>
                    <th>Runtime status</th>
                  </tr>
                </thead>
                <tbody>
                  ${(status.architecture_matrix || []).map((row) => `
                    <tr>
                      <td><strong>${escapeHtml(row.requirement)}</strong></td>
                      <td class="nowrap-col"><span class="mono-id">${escapeHtml(row.api_key)}</span></td>
                      <td>${escapeHtml(row.nlp)}</td>
                      <td class="nowrap-col">${renderStateBadge(row.status || (row.active_in_loomshield ? 'Available' : 'Disabled / Not configured'))}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      </div>
    `;
  } catch (err) {
    const action = getApiErrorAction(err);
    const lastTime = AppState.lastRefreshed.engineStatus ? formatTimestamp(AppState.lastRefreshed.engineStatus) : 'Never';
    if (container) {
      container.innerHTML = `
        <div class="empty-state-box" style="border: 1px solid #FECDCA; background: #FEF3F2;">
          <h3 style="color: #B42318;">Could not retrieve engine status</h3>
          <p style="color: #475467;">${escapeHtml(err.message)}</p>
          ${action.helperText ? `<div style="font-size: 12.5px; color: #B42318; margin-top: 4px;">${escapeHtml(action.helperText)}</div>` : ''}
          ${err.requestId ? `<div style="font-size: 11px; color: #98A2B3; margin-top: 4px; font-family: var(--font-mono);">Request ID: ${escapeHtml(err.requestId)}</div>` : ''}
          <div style="font-size: 11px; color: #98A2B3; margin-top: 6px;">Last successful update: ${escapeHtml(lastTime)}</div>
          ${action.canRetry ? `<button type="button" class="btn btn-sm btn-accent" id="retryEngineStatusBtn" style="margin-top: 12px;">${escapeHtml(action.retryLabel || 'Retry')}</button>` : ''}
        </div>
      `;
      const retryBtn = document.getElementById('retryEngineStatusBtn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderEngineStatusView());
    }
  }
}


function initCommandPalette() {
  const modal = document.getElementById('commandPaletteModal');
  const input = document.getElementById('commandPaletteInput');
  const resultsContainer = document.getElementById('commandPaletteResults');
  if (!modal || !input || !resultsContainer) return;

  let activeIndex = 0;
  let currentItems = [];

  function getCommands() {
    const list = [
      { type: 'Action', label: 'New audit', detail: 'Start auditing new document copy or files', run: () => { AppState.auditStage = 'input'; AppState.wizardMode = true; AppState.wizardStep = 1; switchView('new-audit'); } },
      { type: 'Navigation', label: 'Go to Overview', detail: 'Workspace dashboard and recent audits', run: () => switchView('overview') },
      { type: 'Navigation', label: 'Go to Brand guidelines', detail: 'Tone, preferred words, facts, colours, accessibility', run: () => switchView('brand-vault') },
      { type: 'Navigation', label: 'Go to Review queue', detail: 'Track audits awaiting sign-off and approval', run: () => switchView('review-queue') },
      { type: 'Navigation', label: 'Go to Guideline insights', detail: 'Ambiguity radar and recurring override patterns', run: () => switchView('ambiguity-radar') },
      { type: 'Navigation', label: 'Go to Audit history', detail: 'Audited versions, word diffs, and approval audit logs', run: () => switchView('audit-history') },
      { type: 'Navigation', label: 'Go to Settings', detail: 'Role selector and workspace preferences', run: () => switchView('settings') },
      { type: 'Navigation', label: 'Go to Privacy and processing', detail: 'Engine self-tests and honest processing status', run: () => switchView('engine-status') },
      { type: 'Navigation', label: 'Go to Verify certificate', detail: 'Verify Ed25519 compliance certificates (#verify)', run: () => switchView('verify-certificate') },
      { type: 'Navigation', label: 'Go to About & roadmap', detail: 'Architecture and verified system capabilities', run: () => switchView('about-roadmap') },
      { type: 'Action', label: 'Run engine self-test', detail: 'Execute deterministic engine verification diagnostics', run: () => triggerEngineSelftest() },
    ];

    if (AppState.demoMode) {
      list.push({
        type: 'Action',
        label: 'Reset demo workspace',
        detail: 'Restore seeded demo guidelines and sample documents',
        run: () => document.getElementById('resetDemoBtn')?.click(),
      });
    }

    // Brands
    (AppState.brands || []).forEach((b) => {
      list.push({
        type: 'Brand',
        label: `Switch brand: ${b.name}`,
        detail: `Brand ID: ${b.id} · v${b.version || 1}`,
        run: async () => {
          const sel = document.getElementById('brandSelector');
          if (sel) {
            sel.value = b.id;
            sel.dispatchEvent(new Event('change'));
          }
        },
      });
    });

    // Recent audits
    if (AppState.overviewData && AppState.overviewData.recent_audits) {
      AppState.overviewData.recent_audits.slice(0, 8).forEach((a) => {
        list.push({
          type: 'Audit',
          label: `Open recent audit: ${a.document_name}`,
          detail: `${a.id} · ${a.overall_status} · ${a.open_findings} open`,
          run: () => openAuditById(a.id),
        });
      });
    }

    return list;
  }

  function renderPaletteList(q) {
    const all = getCommands();
    const query = (q || '').trim().toLowerCase();
    currentItems = query
      ? all.filter((item) => `${item.label} ${item.type} ${item.detail}`.toLowerCase().includes(query))
      : all;

    if (currentItems.length === 0) {
      resultsContainer.innerHTML = '<div style="padding: 16px; font-size: 13px; color: var(--slate-700); text-align: center;">No matching commands found</div>';
      return;
    }

    activeIndex = 0;
    resultsContainer.innerHTML = currentItems.map((item, idx) => `
      <div class="command-palette-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}" role="option">
        <div style="flex: 1;">
          <div style="font-weight: 600; color: var(--primary-ink);">${escapeHtml(item.label)}</div>
          <div style="font-size: 11.5px; color: var(--slate-700); margin-top: 2px;">${escapeHtml(item.detail)}</div>
        </div>
        <span class="status-badge badge-neutral" style="font-size: 10px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg><span>${escapeHtml(item.type)}</span></span>
      </div>
    `).join('');

    resultsContainer.querySelectorAll('.command-palette-item').forEach((el) => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.getAttribute('data-idx'), 10);
        executeItem(idx);
      });
    });
  }

  function executeItem(idx) {
    if (currentItems[idx]) {
      closePalette();
      currentItems[idx].run();
    }
  }

  function openPalette() {
    document.getElementById('appSidebar')?.classList.remove('mobile-open');
    const signInMenu = document.getElementById('demoSignInMenu');
    if (signInMenu) signInMenu.style.display = 'none';
    modal.style.display = 'flex';
    input.value = '';
    renderPaletteList('');
    setTimeout(() => input.focus(), 50);
  }

  function closePalette() {
    modal.style.display = 'none';
  }

  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (modal.style.display === 'none' || !modal.style.display) {
        openPalette();
      } else {
        closePalette();
      }
    } else if (e.key === 'Escape' && modal.style.display !== 'none') {
      closePalette();
    }
  });

  input.addEventListener('input', (e) => {
    renderPaletteList(e.target.value);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (currentItems.length > 0) {
        activeIndex = (activeIndex + 1) % currentItems.length;
        updateActiveItem();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentItems.length > 0) {
        activeIndex = (activeIndex - 1 + currentItems.length) % currentItems.length;
        updateActiveItem();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeItem(activeIndex);
    }
  });

  function updateActiveItem() {
    resultsContainer.querySelectorAll('.command-palette-item').forEach((el, idx) => {
      el.classList.toggle('active', idx === activeIndex);
      if (idx === activeIndex) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closePalette();
    }
  });
}


// ============================================================================
// ROUND 3 DAY 2: DEMO IDENTITIES SIGN-IN & SIGNED COMPLIANCE CERTIFICATES
// ============================================================================

const DEFAULT_DEMO_USERS = [
  { user_id: 'usr_priya', id: 'usr_priya', name: 'Priya Nair', role: 'Content Creator', initials: 'PN' },
  { user_id: 'usr_marcus', id: 'usr_marcus', name: 'Marcus Lee', role: 'Reviewer', initials: 'ML' },
  { user_id: 'usr_ava', id: 'usr_ava', name: 'Ava Chen', role: 'Brand Administrator', initials: 'AC' },
];

function renderDemoSignInMenu() {
  const listEl = document.getElementById('demoSignInUsersList');
  if (!listEl) return;
  const users = (AppState.demoUsers && AppState.demoUsers.length > 0)
    ? AppState.demoUsers
    : DEFAULT_DEMO_USERS;

  listEl.innerHTML = users.map((u) => {
    const uid = u.user_id || u.id || '';
    const uname = u.name || u.user_name || 'Demo User';
    const isCurrent = (AppState.userId && AppState.userId === uid) || (!AppState.userId && AppState.userName === uname);
    return `
      <button type="button" class="signin-user-option ${isCurrent ? 'active-user' : ''}" data-demo-user-id="${escapeHtml(uid)}" role="menuitem">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span class="user-avatar-initials">${escapeHtml(u.initials || uname.slice(0, 2).toUpperCase())}</span>
          <div>
            <div style="font-weight: 600; color: var(--glass-text-primary);">${escapeHtml(uname)}</div>
            <div style="font-size: 11.5px; color: var(--glass-text-secondary);">${escapeHtml(u.role)}</div>
          </div>
        </div>
        ${isCurrent ? '<span class="status-badge badge-passed" style="font-size: 10.5px;"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Active</span></span>' : '<span style="font-size: 11.5px; color: var(--glass-text-secondary);">Sign in &rarr;</span>'}
      </button>
    `;
  }).join('');

  listEl.querySelectorAll('.signin-user-option').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const uid = btn.getAttribute('data-demo-user-id');
      await signInAsDemoUser(uid);
      const menu = document.getElementById('demoSignInMenu');
      if (menu) menu.style.display = 'none';
      document.getElementById('accountRoleBtn')?.setAttribute('aria-expanded', 'false');
    });
  });
}

async function signInAsDemoUser(userId) {
  try {
    const res = await apiFetch('/api/demo/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });
    AppState.demoToken = res.token || '';
    const u = res.user || res;
    AppState.userId = u.user_id || u.id || userId;
    AppState.userName = u.user_name || u.name || 'Demo User';
    AppState.userInitials = u.initials || '';
    AppState.activeRole = u.role || 'Content Creator';
    const sessionData = await apiFetch('/api/session');
    if (sessionData) {
      AppState.session = sessionData;
      AppState.permissions = sessionData.permissions || {};
    }
    updateTopbarContext();
    if (AppState.activeView === 'new-audit' && AppState.auditStage === 'results') {
      updateWorkspaceApprovalGuard();
    } else if (AppState.activeView === 'settings') {
      renderSettingsView();
    } else if (AppState.activeView === 'review-queue') {
      await renderReviewQueueView();
    }
    try {
      sessionStorage.setItem('loomshield_demo_session', JSON.stringify({
        token: AppState.demoToken,
        userId: AppState.userId,
        userName: AppState.userName,
        userInitials: AppState.userInitials,
        activeRole: AppState.activeRole,
      }));
    } catch (_e) {}
    showToast(`Signed in as ${AppState.userName} (${AppState.activeRole}).`);
  } catch (err) {
    showToast(`Demo sign-in failed: ${err.message}`);
  }
}

async function openCertificateModal(auditId) {
  document.getElementById('appSidebar')?.classList.remove('mobile-open');
  const signInMenu = document.getElementById('demoSignInMenu');
  if (signInMenu) signInMenu.style.display = 'none';

  try {
    let certRes;
    try {
      certRes = await apiFetch(`/api/audits/${encodeURIComponent(auditId)}/certificate`);
    } catch (getErr) {
      if (getErr && getErr.status === 404) {
        certRes = await apiFetch(`/api/audits/${encodeURIComponent(auditId)}/certificate`, {
          method: 'POST',
        });
      } else {
        throw getErr;
      }
    }
    const envelope = certRes.certificate || certRes;
    const payload = envelope.payload || {};
    const isEphemeral = Boolean(envelope.ephemeral_key ?? payload.ephemeral_key);
    const ephemeralWarning = isEphemeral
      ? (envelope.key_notice || payload.key_notice || 'ephemeral demo key: valid only until the server restarts')
      : '';
    const fs = payload.findings_summary || { total: 0, accepted: 0, modified: 0, dismissed: 0, open: 0 };
    const ap = payload.approval || {};
    const dismissals = payload.dismissals || [];

    const root = document.getElementById('modalRoot');
    root.style.display = 'block';
    root.innerHTML = `
      <div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="certModalTitle">
        <div class="modal-card certificate-modal-card">
          ${ephemeralWarning ? `
            <div class="alert alert-warning" style="margin-bottom: 12px; font-size: 12.5px;">
              <strong>Ephemeral key notice:</strong> <span>${escapeHtml(ephemeralWarning)}</span>
            </div>
          ` : ''}

          <div class="certificate-sheet" id="printableCertificateSheet">
            <div class="certificate-sheet-header">
              <div>
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--slate-600);">LoomShield Brand Governance</div>
                <h2 id="certModalTitle" style="font-size: 20px; font-weight: 700; color: var(--slate-900); margin-top: 2px;">Signed Compliance Certificate</h2>
                <div style="font-size: 12px; color: var(--slate-600); margin-top: 2px;">Certificate ID: <span class="mono-id">${escapeHtml(payload.certificate_id)}</span> &bull; Issued (UTC): <span class="mono-id">${escapeHtml(payload.issued_at)}</span></div>
              </div>
              <div style="text-align: right;">
                <span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Ed25519 Signed (v${escapeHtml(payload.certificate_version)})</span></span>
              </div>
            </div>

            <div class="certificate-grid">
              <div class="certificate-field-box">
                <div class="certificate-field-label">Document &amp; Audit ID</div>
                <div class="certificate-field-value">${escapeHtml(payload.document_name)} (<span class="mono-id">${escapeHtml(payload.audit_id)}</span>)</div>
              </div>
              <div class="certificate-field-box">
                <div class="certificate-field-label">Submitted By</div>
                <div class="certificate-field-value">${escapeHtml((payload.submitted_by && payload.submitted_by.name) || 'Content Creator')} (<span class="mono-id">${escapeHtml((payload.submitted_by && payload.submitted_by.user_id) || '—')}</span> &bull; ${escapeHtml((payload.submitted_by && payload.submitted_by.role) || 'Content Creator')})</div>
              </div>
              <div class="certificate-field-box">
                <div class="certificate-field-label">Brand Guideline Version</div>
                <div class="certificate-field-value">${escapeHtml(payload.brand_name)} (<span class="mono-id">${escapeHtml(payload.brand_id)}</span> &bull; v${escapeHtml(payload.brand_version)})</div>
              </div>
              <div class="certificate-field-box">
                <div class="certificate-field-label">Approval Sign-Off</div>
                <div class="certificate-field-value">${escapeHtml(ap.approver_name || ap.approver_role)} (${escapeHtml(ap.approver_role)}) at ${escapeHtml(ap.approved_at)}</div>
                <div style="font-size: 11.5px; color: var(--slate-600); margin-top: 2px;">Override: ${ap.override_acknowledged ? 'Yes' : 'No'} &bull; Note: "${escapeHtml(ap.comment || '—')}"</div>
              </div>
              <div class="certificate-field-box">
                <div class="certificate-field-label">Findings Summary &amp; Mode</div>
                <div class="certificate-field-value">Total: ${fs.total} &bull; Accepted: ${fs.accepted} &bull; Modified: ${fs.modified} &bull; Dismissed: ${fs.dismissed} &bull; Open: ${fs.open}</div>
                <div style="font-size: 11.5px; color: var(--slate-600); margin-top: 2px;">Engine: ${escapeHtml(payload.engine_version)} (${escapeHtml(payload.processing_mode)})</div>
              </div>
            </div>

            ${dismissals.length > 0 ? `
              <div style="margin-bottom: 12px; font-size: 12px;">
                <strong>Recorded Dismissals (${dismissals.length}):</strong>
                <ul style="padding-left: 18px; margin-top: 4px;">
                  ${dismissals.map((d) => `<li><span class="mono-id">${escapeHtml(d.finding_id)}</span>: ${escapeHtml(d.reason)}</li>`).join('')}
                </ul>
              </div>
            ` : ''}

            <div class="certificate-hash-block">
              <div><strong>Approved Content SHA-256:</strong> ${escapeHtml(payload.content_sha256)}</div>
              <div style="margin-top: 4px;"><strong>Original Content SHA-256:</strong> ${escapeHtml(payload.original_content_sha256)}</div>
              <div style="margin-top: 4px;"><strong>Signing Key ID (kid):</strong> ${escapeHtml(envelope.kid)} &bull; <strong>Algorithm:</strong> ${escapeHtml(envelope.alg)}</div>
              <div style="margin-top: 4px;"><strong>Ed25519 Signature (Base64):</strong> ${escapeHtml(envelope.signature_b64)}</div>
            </div>

            <div class="certificate-limitations-box">
              <div><strong>Scope &amp; Limitations:</strong> ${escapeHtml(payload.limitations)}</div>
              ${ephemeralWarning ? `<div style="margin-top: 4px;"><strong>Signing Key Mode:</strong> ${escapeHtml(ephemeralWarning)}</div>` : ''}
            </div>
          </div>

          <div class="modal-actions-row no-print" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 16px;">
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <button type="button" class="btn btn-sm btn-accent" id="certDownloadJsonBtn">Download JSON</button>
              <button type="button" class="btn btn-sm" id="certPrintBtn">Print (A4)</button>
              <button type="button" class="btn btn-sm" id="certOpenVerifierBtn">Verify on #verify page</button>
            </div>
            <button type="button" class="btn btn-sm btn-ghost" id="certModalCloseBtn">Close</button>
          </div>
        </div>
      </div>
    `;

    const closeModal = () => {
      document.body.classList.remove('printing-certificate');
      root.style.display = 'none';
      root.innerHTML = '';
    };

    document.getElementById('certModalCloseBtn')?.addEventListener('click', closeModal);

    document.getElementById('certDownloadJsonBtn')?.addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(envelope, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `loomshield-certificate-${auditId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(`Downloaded certificate JSON for ${auditId}.`);
    });

    document.getElementById('certPrintBtn')?.addEventListener('click', () => {
      document.body.classList.add('printing-certificate');
      window.print();
      setTimeout(() => {
        document.body.classList.remove('printing-certificate');
      }, 500);
    });

    document.getElementById('certOpenVerifierBtn')?.addEventListener('click', async () => {
      closeModal();
      const ta = document.getElementById('verifyCertTextarea');
      if (ta) {
        ta.value = JSON.stringify(envelope, null, 2);
      }
      window.location.hash = '#verify';
      await switchView('verify-certificate');
      await runCertificateVerification();
    });
  } catch (err) {
    showToast(`Could not issue or load certificate: ${err.message}`);
  }
}

async function renderVerifyCertificateView() {
  const infoBar = document.getElementById('verifyPublicKeyInfoBar');
  if (infoBar) {
    try {
      const pk = await apiFetch('/api/certificates/public-key');
      const isEph = Boolean(pk.ephemeral_key ?? pk.is_ephemeral);
      const keyNotice = pk.key_notice || pk.ephemeral_warning || 'ephemeral demo key: valid only until the server restarts';
      infoBar.innerHTML = `
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
          <div>
            <div style="font-size: 13.5px; font-weight: 600; color: var(--primary-ink);">Active Server Ed25519 Verification Key</div>
            <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 4px;">
              Key ID (<code>kid</code>): <span class="mono-id">${escapeHtml(pk.kid)}</span> &bull;
              Public Key (Base64): <span class="mono-id">${escapeHtml(pk.public_key_b64)}</span>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
              Offline CLI verifier: <code>python scripts/verify_certificate.py cert.json --public-key ${escapeHtml(pk.public_key_b64)}</code>
            </div>
          </div>
          ${isEph ? `
            <span class="status-badge badge-warning"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>${escapeHtml(keyNotice)}</span></span>
          ` : `
            <span class="status-badge badge-passed"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Configured Signing Key</span></span>
          `}
        </div>
      `;
    } catch (err) {
      infoBar.innerHTML = `<div style="font-size: 13px; color: var(--status-error);">Could not load public key: ${escapeHtml(err.message)}</div>`;
    }
  }

  const runBtn = document.getElementById('runVerifyCertBtn');
  if (runBtn && !runBtn._bound) {
    runBtn._bound = true;
    runBtn.addEventListener('click', () => runCertificateVerification());
  }

  const clearBtn = document.getElementById('clearVerifyCertBtn');
  if (clearBtn && !clearBtn._bound) {
    clearBtn._bound = true;
    clearBtn.addEventListener('click', () => {
      const ta = document.getElementById('verifyCertTextarea');
      const box = document.getElementById('verifyCertResultBox');
      if (ta) ta.value = '';
      if (box) {
        box.style.display = 'none';
        box.innerHTML = '';
      }
    });
  }

  const fileInput = document.getElementById('verifyCertFileInput');
  if (fileInput && !fileInput._bound) {
    fileInput._bound = true;
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const textContent = await file.text();
      const ta = document.getElementById('verifyCertTextarea');
      if (ta) ta.value = textContent;
      await runCertificateVerification();
      fileInput.value = '';
    });
  }

  const sampleBtn = document.getElementById('verifyLoadSampleBtn');
  if (sampleBtn && !sampleBtn._bound) {
    sampleBtn._bound = true;
    sampleBtn.addEventListener('click', async () => {
      try {
        const listRes = await apiFetch(`/api/audits?brand_id=${encodeURIComponent(AppState.activeBrandId)}&limit=50`);
        const approved = (listRes.audits || []).find((a) => a.overall_status === 'Approved');
        if (!approved) {
          showToast('No Approved audit found in current brand. Approve an audit first to issue a certificate.');
          return;
        }
        let certRes;
        try {
          certRes = await apiFetch(`/api/audits/${encodeURIComponent(approved.id)}/certificate`);
        } catch (getErr) {
          if (getErr && getErr.status === 404) {
            certRes = await apiFetch(`/api/audits/${encodeURIComponent(approved.id)}/certificate`, { method: 'POST' });
          } else {
            throw getErr;
          }
        }
        const env = certRes.certificate || certRes;
        const ta = document.getElementById('verifyCertTextarea');
        if (ta) ta.value = JSON.stringify(env, null, 2);
        await runCertificateVerification();
      } catch (err) {
        showToast(`Could not load sample certificate: ${err.message}`);
      }
    });
  }
}

async function runCertificateVerification() {
  const ta = document.getElementById('verifyCertTextarea');
  const box = document.getElementById('verifyCertResultBox');
  if (!ta || !box) return;

  const rawText = ta.value.trim();
  if (!rawText) {
    showToast('Paste a certificate JSON envelope or upload a .json file first.');
    return;
  }

  let parsedEnvelope = null;
  try {
    parsedEnvelope = JSON.parse(rawText);
  } catch (_e) {
    box.style.display = 'block';
    box.innerHTML = `
      <div class="card" style="border-left: 4px solid var(--status-error);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
          <h3 class="card-title">Verification Result: Not valid</h3>
          <span class="status-badge badge-error"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span>Not valid (malformed)</span></span>
        </div>
        <p style="font-size: 13.5px; color: var(--text-primary);">Certificate input is malformed JSON and could not be parsed.</p>
      </div>
    `;
    return;
  }

  try {
    const res = await apiFetch('/api/certificates/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ certificate: parsedEnvelope }),
    });

    const isRevoked = Boolean(res.is_revoked || res.status === 'revoked');
    const isValid = Boolean(res.valid && !isRevoked);
    const reasonText = Array.isArray(res.reasons) && res.reasons.length > 0
      ? res.reasons.join(' ')
      : (res.reason || (isValid ? 'Ed25519 signature and canonical JSON payload verified.' : (isRevoked ? 'Certificate was revoked by administrator.' : 'Certificate verification failed.')));
    const isEph = Boolean(res.ephemeral_key ?? res.is_ephemeral_key);
    const keyNotice = isEph ? (res.key_notice || res.ephemeral_warning || 'ephemeral demo key: valid only until the server restarts') : '';

    const payload = (parsedEnvelope && typeof parsedEnvelope.payload === 'object' && parsedEnvelope.payload) || {};
    let serverHashText = 'Audit record is not stored on this server instance.';
    if (res.audit_exists_on_server) {
      serverHashText = res.content_hash_matches_server
        ? 'Matches stored audit content SHA-256 on this server.'
        : 'MISMATCH: Stored audit content hash on this server does not match the certificate.';
    }

    const badgeLabel = isRevoked ? 'Revoked (Signature Valid)' : (isValid ? 'Valid' : `Not valid (${escapeHtml(res.status || 'invalid')})`);
    const badgeClass = isRevoked ? 'badge-error' : (isValid ? 'badge-passed' : 'badge-error');
    const badgeSvg = isValid
      ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>'
      : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';

    box.style.display = 'block';
    box.innerHTML = `
      <div class="card" style="border-left: 4px solid ${isRevoked ? '#B42318' : (isValid ? 'var(--status-success)' : 'var(--status-error)')};">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px;">
          <h3 class="card-title" id="verifyResultHeading">Verification Result: ${isRevoked ? 'Revoked' : (isValid ? 'Valid' : 'Not valid')}</h3>
          <span class="status-badge ${badgeClass}" id="verifyResultBadge">
            ${badgeSvg}
            <span>${badgeLabel}</span>
          </span>
        </div>
        ${isRevoked ? `
          <div class="alert alert-error" style="margin-bottom: 10px; background: #FEF3F2; border: 1px solid #FECDCA; color: #B42318; padding: 8px 12px; border-radius: 4px; font-size: 13px;">
            <strong>REVOCATION NOTICE:</strong> This certificate was revoked on ${escapeHtml(res.revoked_at || '—')} by ${escapeHtml(res.revoked_by || 'Brand Administrator')}: "${escapeHtml(res.revocation_reason || 'Administrative revocation')}". The cryptographic signature remains mathematically valid.
          </div>
        ` : ''}
        <p style="font-size: 14px; font-weight: 600; color: var(--primary-ink); margin-bottom: 8px;" id="verifyResultReason">${escapeHtml(reasonText)}</p>
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
          <div><strong>Server Content Hash Check:</strong> ${escapeHtml(serverHashText)}</div>
          ${payload.certificate_id ? `<div><strong>Certificate ID:</strong> <span class="mono-id">${escapeHtml(payload.certificate_id)}</span> &bull; <strong>Audit ID:</strong> <span class="mono-id">${escapeHtml(payload.audit_id || '—')}</span></div>` : ''}
          ${payload.content_sha256 ? `<div><strong>Certified Content SHA-256:</strong> <span class="mono-id">${escapeHtml(payload.content_sha256)}</span></div>` : ''}
          ${keyNotice ? `<div style="margin-top: 6px; color: var(--status-warning);"><strong>Signing Key Notice:</strong> ${escapeHtml(keyNotice)}</div>` : ''}
        </div>
      </div>
    `;
  } catch (err) {
    box.style.display = 'block';
    box.innerHTML = `
      <div class="card" style="border-left: 4px solid var(--status-error);">
        <h3 class="card-title">Verification request failed</h3>
        <p style="font-size: 13.5px; color: var(--text-secondary); margin-top: 4px;">${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}
