with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update the HTML in renderVaultColorsTab
target_html = '''    <div class="card">
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
    </div>'''

replacement_html = '''    <div class="card">
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
    </div>'''

assert target_html in js, "target_html not found in app.js"
js = js.replace(target_html, replacement_html)

# 2. Update saveVisualSpecsBtn and add logo event listeners
target_save_vis = '''    try {
      AppState.vaultData = await apiFetch(`/api/vault/${encodeURIComponent(AppState.activeBrandId)}/visual-specs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          typography_specs: document.getElementById('visTypography').value,
          spacing_rules: document.getElementById('visSpacing').value,
          logo_placement_constraints: document.getElementById('visLogo').value,
        }),
      });'''

replacement_save_vis = '''    try {
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
      AppState.vaultData = res.vault || res;'''

assert target_save_vis in js, "target_save_vis not found in app.js"
js = js.replace(target_save_vis, replacement_save_vis)

# Add event listeners for logo input and delete button
logo_events = '''
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
'''

target_end_tab = "  document.getElementById('saveVisualSpecsBtn').addEventListener('click', async () => {"
assert target_end_tab in js, "target_end_tab not found in app.js"
js = js.replace(target_end_tab, logo_events + "\n" + target_end_tab)

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(js)

print("Updated frontend/app.js with approved logo and clear space inputs successfully")
