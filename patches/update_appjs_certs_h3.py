with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update openCertificateModal to display submitted_by
old_grid = '''            <div class="certificate-grid">
              <div class="certificate-field-box">
                <div class="certificate-field-label">Document &amp; Audit ID</div>
                <div class="certificate-field-value">${escapeHtml(payload.document_name)} (<span class="mono-id">${escapeHtml(payload.audit_id)}</span>)</div>
              </div>'''

new_grid = '''            <div class="certificate-grid">
              <div class="certificate-field-box">
                <div class="certificate-field-label">Document &amp; Audit ID</div>
                <div class="certificate-field-value">${escapeHtml(payload.document_name)} (<span class="mono-id">${escapeHtml(payload.audit_id)}</span>)</div>
              </div>
              <div class="certificate-field-box">
                <div class="certificate-field-label">Submitted By</div>
                <div class="certificate-field-value">${escapeHtml((payload.submitted_by && payload.submitted_by.name) || 'Content Creator')} (<span class="mono-id">${escapeHtml((payload.submitted_by && payload.submitted_by.user_id) || '—')}</span> &bull; ${escapeHtml((payload.submitted_by && payload.submitted_by.role) || 'Content Creator')})</div>
              </div>'''

assert old_grid in js, "old_grid not found in app.js"
js = js.replace(old_grid, new_grid)

# 2. Update runCertificateVerification to display REVOKED state prominently
old_verify_card = '''    const isValid = Boolean(res.valid);
    const reasonText = Array.isArray(res.reasons) && res.reasons.length > 0
      ? res.reasons.join(' ')
      : (res.reason || (isValid ? 'Ed25519 signature and canonical JSON payload verified.' : 'Certificate verification failed.'));
    const isEph = Boolean(res.ephemeral_key ?? res.is_ephemeral_key);
    const keyNotice = isEph ? (res.key_notice || res.ephemeral_warning || 'ephemeral demo key: valid only until the server restarts') : '';

    const payload = (parsedEnvelope && typeof parsedEnvelope.payload === 'object' && parsedEnvelope.payload) || {};
    let serverHashText = 'Audit record is not stored on this server instance.';
    if (res.audit_exists_on_server) {
      serverHashText = res.content_hash_matches_server
        ? 'Matches stored audit content SHA-256 on this server.'
        : 'MISMATCH: Stored audit content hash on this server does not match the certificate.';
    }

    const badgeSvg = isValid
      ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>'
      : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';

    box.style.display = 'block';
    box.innerHTML = `
      <div class="card" style="border-left: 4px solid ${isValid ? 'var(--status-success)' : 'var(--status-error)'};">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px;">
          <h3 class="card-title" id="verifyResultHeading">Verification Result: ${isValid ? 'Valid' : 'Not valid'}</h3>
          <span class="status-badge ${isValid ? 'badge-passed' : 'badge-error'}" id="verifyResultBadge">
            ${badgeSvg}
            <span>${isValid ? 'Valid' : `Not valid (${escapeHtml(res.status || 'invalid')})`}</span>
          </span>
        </div>'''

new_verify_card = '''    const isRevoked = Boolean(res.is_revoked || res.status === 'revoked');
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
        ` : ''}'''

assert old_verify_card in js, "old_verify_card not found in app.js"
js = js.replace(old_verify_card, new_verify_card)

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(js)

print("Updated frontend/app.js with certificate v2 submitted_by and revocation display")
