with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

target = """                ${loopClosure ? `
                  <div class="loop-closure-banner" style="padding: 10px 12px; background: var(--status-success-bg); border: 1px solid var(--status-success-border); border-radius: var(--radius-control); font-size: 13px; color: var(--slate-800);">
                    <strong>Loop closure:</strong> ${escapeHtml(loopClosure.display)}
                  </div>
                ` : ''}"""

replacement = """                ${loopClosure ? `
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
                ` : ''}"""

assert target in js, "target not found in app.js"
js = js.replace(target, replacement)

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(js)

print("Updated frontend/app.js loop closure UI successfully")
