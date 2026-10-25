function updateProcessingModeUI() {
  const title = document.getElementById('processingModeTitle');
  const helper = document.getElementById('localModeHelper');
  const badge = document.getElementById('processingModeBadge');
  const isLocal = AppState.processingMode === 'local';

  if (title && helper && badge) {
    if (isLocal) {
      title.textContent = 'Local on-device processing';
      helper.textContent = 'Processed on this device; nothing leaves your machine.';
      badge.textContent = 'On-device';
      badge.className = 'status-badge badge-passed';
    } else {
      title.textContent = 'Hosted server processing';
      helper.textContent = AppState.demoMode
        ? 'Your content is sent to the LoomShield server for processing and the audit is saved to history. Demo workspace: do not submit confidential material.'
        : 'Your content is sent to the LoomShield server for processing and the audit is saved to history. This workspace has no sign-in: submitted content is stored and visible to anyone using this deployment; do not submit confidential material.';
      badge.textContent = 'Hosted server';
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
  userName: '',
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
  'brand-vault': 'Brand Vault',
  'review-queue': 'Review queue',
  'ambiguity-radar': 'Guideline ambiguity',
  'audit-history': 'Audit history',
  'settings': 'Settings',
  'engine-status': 'Privacy and processing',
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
    'Needs Review': 'Needs review',
    'needs_review': 'Needs review',
    'Check Failed': 'Failed',
    'Findings': 'Needs review',
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
  if (AppState.activeRole && !headers['x-loomshield-role']) {
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
    const initials = (AppState.userName || 'Workspace User')
      .split(' ')
      .filter(Boolean)
      .map((w) => w[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
    roleBtn.innerHTML = `
      <span class="user-avatar-initials">${escapeHtml(initials)}</span>
      <span style="font-weight: 600;">${escapeHtml(AppState.userName || 'Workspace User')}</span>
      <span class="role-pill-badge">${escapeHtml(AppState.activeRole)}</span>
    `;
    roleBtn.setAttribute('title', `Signed in as ${AppState.userName || 'Workspace User'} (${AppState.activeRole}) — Workspace settings`);
  }
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

  document.getElementById('accountRoleBtn').addEventListener('click', () => {
    switchView('settings');
  });

  document.getElementById('overviewNewAuditBtn').addEventListener('click', () => {
    AppState.auditStage = 'input';
    AppState.wizardMode = true;
    AppState.wizardStep = 1;
    switchView('new-audit');
  });

  document.getElementById('overviewTryDemoBtn').addEventListener('click', () => {
    AppState.auditStage = 'input';
    AppState.wizardMode = true;
    AppState.wizardStep = 8;
    switchView('new-audit');
  });

  document.getElementById('demoSampleSelector').addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    if (val) {
      AppState.auditStage = 'input';
      switchView('new-audit');
      loadSamplePreset(val);
      e.target.value = '';
    }
  });

  document.getElementById('resetDemoBtn').addEventListener('click', () => {
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

  const runSelfTestBtn = document.getElementById('runEngineSelftestHeaderBtn');
  if (runSelfTestBtn) {
    runSelfTestBtn.addEventListener('click', async () => {
      await triggerEngineSelftest();
    });
  }
}

async function switchView(viewName) {
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
  if (viewName === 'new-audit') renderAuditWorkspace();
  if (viewName === 'brand-vault') await refreshBrandVault();
  if (viewName === 'review-queue') await renderReviewQueueView();
  if (viewName === 'ambiguity-radar') await renderAmbiguityRadarView();
  if (viewName === 'audit-history') await renderAuditHistoryView();
  if (viewName === 'settings') renderSettingsView();
  if (viewName === 'engine-status') await renderEngineStatusView();
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
        AppState.activeRole = sessionData.user_role || 'Content Creator';
        AppState.userName = sessionData.user_name || 'Workspace User';
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
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map((a) => `
            <tr>
              <td>
                <strong>${escapeHtml(a.document_name)}</strong>
                <div style="margin-top: 3px; display: flex; gap: 6px; align-items: center;">
                  <span class="mono-id">${escapeHtml(a.id)}</span>
                  <span class="mono-id">${escapeHtml(a.input_format)}</span>
                </div>
              </td>
              <td class="nowrap-col" style="font-size: 12.5px; color: var(--text-secondary);" title="${escapeHtml(a.updated_at)}">${escapeHtml(formatTimestamp(a.updated_at))}</td>
              <td class="nowrap-col">${renderStateBadge(a.overall_status)}</td>
              <td class="nowrap-col">
                ${a.open_findings > 0
                  ? `<span class="status-badge badge-error">${a.open_findings} open</span>`
                  : `<span class="status-badge badge-passed">0 open (${a.total_findings} resolved)</span>`}
              </td>
              <td class="nowrap-col">
                <button type="button" class="btn btn-sm open-audit-btn" data-audit-id="${escapeHtml(a.id)}">Open review</button>
              </td>
            </tr>
          `).join('')}
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

async function openAuditById(auditId) {
  try {
    const audit = await apiFetch(`/api/audits/${encodeURIComponent(auditId)}`);
    AppState.currentAudit = audit;
    AppState.auditStage = 'results';
    AppState.selectedPillarFilter = 'ALL';
    AppState.selectedSeverityFilter = 'ALL';
    AppState.selectedStatusFilter = 'ALL';
    AppState.findingSearchQuery = '';
    AppState.selectedFindingId = audit.findings && audit.findings.length > 0 ? audit.findings[0].id : null;
    await switchView('new-audit');
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

  // Ingestion method toggle: Paste content vs Upload file
  const pasteBtn = document.getElementById('inputMethodPasteBtn');
  const uploadBtn = document.getElementById('inputMethodUploadBtn');
  const pasteSec = document.getElementById('ingestionPasteSection');
  const uploadSec = document.getElementById('ingestionUploadSection');

  if (pasteBtn && uploadBtn) {
    pasteBtn.addEventListener('click', () => {
      AppState.inputMethod = 'paste';
      pasteBtn.classList.add('active');
      pasteBtn.setAttribute('aria-selected', 'true');
      uploadBtn.classList.remove('active');
      uploadBtn.setAttribute('aria-selected', 'false');
      if (pasteSec) pasteSec.style.display = 'block';
      if (uploadSec) uploadSec.style.display = 'none';
    });

    uploadBtn.addEventListener('click', () => {
      AppState.inputMethod = 'upload';
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
      if (previewBar) previewBar.style.display = 'none';
      syncVisualCheckControlState();
    });
  }

  fileInput.addEventListener('change', () => {
    if (!fileInput.files || fileInput.files.length === 0) {
      if (previewBar) previewBar.style.display = 'none';
      if (fileCard) fileCard.style.display = 'none';
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
      syncVisualCheckControlState();
      return;
    }
    if (f.size > maxBytes) {
      showToast(`File "${f.name}" exceeds the 5 MB limit (${(f.size / (1024 * 1024)).toFixed(2)} MB).`);
      fileInput.value = '';
      if (previewBar) previewBar.style.display = 'none';
      if (fileCard) fileCard.style.display = 'none';
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
      if (fFormatEl) fFormatEl.textContent = detected;
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
          syncVisualCheckControlState();
        });
      }
    }
    syncVisualCheckControlState();
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
      if (fileInput) fileInput.value = '';
      if (fileCard) fileCard.style.display = 'none';
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
      AppState.selectedFindingId = updated.findings && updated.findings.length > 0 ? updated.findings[0].id : null;
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

  document.getElementById('runAuditBtn').addEventListener('click', async () => {
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
      const targetState = btn.getAttribute('data-wf');
      await transitionCurrentAuditWorkflow(targetState);
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
  const docName = document.getElementById('auditDocName').value.trim();
  const content = document.getElementById('auditContentText').value;
  if (!docName || !content.trim()) {
    showToast('Please enter both a document title and content to audit.');
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
    AppState.selectedFindingId = audit.findings && audit.findings.length > 0 ? audit.findings[0].id : null;
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
    AppState.selectedFindingId = audit.findings && audit.findings.length > 0 ? audit.findings[0].id : null;
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
              <span class="wizard-tile-check">✓</span>
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
              <span class="wizard-tile-check">✓</span>
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
              <span class="wizard-tile-check">✓</span>
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
              <span class="wizard-tile-check">✓</span>
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
              <span class="wizard-tile-check">✓</span>
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
            <span>🛡️</span>
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
                <span class="wizard-bullet-icon">✓</span>
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
            ✨ Try an example with a few mistakes
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
    });
  });
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

  countBadge.textContent = `${filtered.length} of ${allFindings.length} finding(s)`;

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
    const simHtml = f.similarity_score !== null && f.similarity_score !== undefined
      ? `<div><strong>Lexical overlap score:</strong> <span class="mono-id">${Number(f.similarity_score).toFixed(2)}</span> (topical retrieval similarity, not factual truth probability)</div>`
      : '';

    return `
      <div class="finding-card ${isSelected ? 'selected' : ''}" data-finding-id="${escapeHtml(f.id)}">
        <div class="finding-card-top">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span class="mono-id">${escapeHtml(f.pillar)}</span>
            ${renderStateBadge(f.severity)}
          </div>
          ${renderStateBadge(f.review_state)}
        </div>

        <div class="finding-issue-title">${escapeHtml(f.issue_type)}</div>
        <div class="finding-excerpt">"${escapeHtml(f.flagged_text)}"</div>
        <div class="finding-explanation">${escapeHtml(f.explanation)}</div>

        <div class="evidence-box">
          <div><strong>Cited rule or fact:</strong> <span class="mono-id">${escapeHtml(f.rule_or_fact_id)}</span></div>
          <div style="margin-top: 4px;"><strong>Evidence:</strong> ${escapeHtml(f.source_evidence)}</div>
        </div>

        <!-- Section 01 & 04: Technical method moved into collapsible "How this was detected" detail -->
        <details class="collapsible-details">
          <summary>How this was detected</summary>
          <div class="collapsible-details-body">
            <div><strong>Finding ID:</strong> <span class="mono-id">${escapeHtml(f.id)}</span></div>
            <div style="margin-top: 4px;"><strong>Source location:</strong> ${spanText}</div>
            <div style="margin-top: 4px;"><strong>Detection method:</strong> ${escapeHtml(f.detection_method)}</div>
            <div style="margin-top: 4px;"><strong>Engine tier:</strong> ${escapeHtml(f.engine_source)}</div>
            ${simHtml}
          </div>
        </details>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.finding-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('details')) return;
      AppState.selectedFindingId = card.getAttribute('data-finding-id');
      renderSourceContentPanel();
      renderFindingsCenterPanel();
      renderCorrectionRightPanel();
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

  if (openCount === 0) {
    overrideRow.style.display = 'none';
    noticeEl.innerHTML = `<span style="color: var(--status-success); font-weight: 600;">All findings are resolved. Document is ready for Reviewer approval.</span>`;
    approveBtn.disabled = false;
    approveBtn.title = 'Approve document for publication';
  } else {
    overrideRow.style.display = 'flex';
    const canOverride = overrideCheck.checked && commentInput.value.trim().length > 0;
    noticeEl.innerHTML = `<span style="color: var(--status-error); font-weight: 600;">${openCount} unresolved finding(s) remain.</span> Resolve all findings first, or record an authorised override with a mandatory written justification.`;
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
        <span class="status-badge badge-neutral">${rules.length + terms.length + facts.length + colors.length} match(es)</span>
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
          ${b.is_demo ? '<span class="status-badge badge-warning" style="margin-top: 4px;">Demo profile</span>' : ''}
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
                <td class="nowrap-col"><span class="status-badge badge-error">${escapeHtml(t.prohibited_term)}</span></td>
                <td class="nowrap-col"><span class="status-badge badge-passed">${escapeHtml(t.replacement_term)}</span></td>
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
                  ${f.is_demo ? '<div style="margin-top: 4px;"><span class="status-badge badge-warning" style="font-size: 10.5px; padding: 1px 6px;">Demo data</span></div>' : ''}
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

  document.getElementById('saveVisualSpecsBtn').addEventListener('click', async () => {
    try {
      AppState.vaultData = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/visual-specs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          typography_specs: document.getElementById('visTypography').value,
          spacing_rules: document.getElementById('visSpacing').value,
          logo_placement_constraints: document.getElementById('visLogo').value,
        }),
      });
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
                    <td class="rq-doc-col">
                      <strong style="font-size: 14.5px; line-height: 20px; display: block;">${escapeHtml(a.document_name)}</strong>
                      <div style="margin-top: 4px;"><span class="mono-id">${escapeHtml(a.id)}</span></div>
                    </td>
                    <td>${escapeHtml(a.assigned_reviewer)}</td>
                    <td class="nowrap-col">${renderStateBadge(a.overall_status)}</td>
                    <td class="nowrap-col">
                      ${hasUnresolved
                        ? `<span class="status-badge badge-error">${a.open_findings} unresolved</span>`
                        : `<span class="status-badge badge-passed">0 unresolved</span>`}
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
                  <span>Reviewer: <strong>${escapeHtml(a.assigned_reviewer)}</strong></span>
                  <span>&bull;</span>
                  ${hasUnresolved
                    ? `<span class="status-badge badge-error">${a.open_findings} unresolved</span>`
                    : `<span class="status-badge badge-passed">0 unresolved</span>`}
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
                  <span class="status-badge badge-neutral" style="font-size: 11px;">${escapeHtml(r.pillar)}</span>
                </div>
                <div class="insight-card-meta">
                  <span class="status-badge badge-neutral">${r.violations_recorded} violation(s)</span>
                  <span class="status-badge ${r.overrides_recorded > 0 ? 'badge-warning' : 'badge-neutral'}">${r.overrides_recorded} override(s)</span>
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
                  ${escapeHtml(a.id)} — ${escapeHtml(a.document_name)} (${escapeHtml(normalizeStatusDisplay(a.overall_status))})
                </option>
              `).join('')}
            </select>
            ${renderStateBadge(detail.overall_status)}
            <span style="font-size: 11.5px; color: var(--text-secondary); margin-left: 4px;">(Record ${displayIdx} of ${audits.length})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="segmented-toggle" role="group" aria-label="History content format">
              <button type="button" class="segmented-btn ${AppState.historyFormatView === 'rendered' ? 'active' : ''}" id="histViewRenderedBtn">Rendered</button>
              <button type="button" class="segmented-btn ${AppState.historyFormatView === 'source' ? 'active' : ''}" id="histViewSourceBtn">Source</button>
            </div>
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
          ${(detail.approvals || []).length > 0 ? `<span class="status-badge badge-neutral">${(detail.approvals || []).length} event(s)</span>` : ''}
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
                  <strong>${escapeHtml(ap.approver_role)}:</strong> ${escapeHtml(ap.comment)}
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
              ${AppState.demoMode ? 'Demo Workspace' : 'Production Workspace'}
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
            <span class="status-badge badge-warning">Demo role preview</span>
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
              ${escapeHtml(status.storage_type === 'persistent' ? 'Persistent disk' : 'Ephemeral instance')}
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
