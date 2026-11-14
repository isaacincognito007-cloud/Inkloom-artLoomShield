with open("frontend/app.js", "r", encoding="utf-8") as f:
    js = f.read()

target = '''      <div class="heatmap-legend-bar" aria-label="Heatmap status legend">
        <span><strong>Legend:</strong></span>
        <span class="heatmap-legend-item"><span class="legend-swatch-pass" aria-hidden="true"></span> PASS: Solid border (&Delta;E within tolerance)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-fail" aria-hidden="true">///</span> FAIL: Diagonal hatch + FAIL label (&Delta;E above threshold)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-logo" aria-hidden="true">[ ]</span> Clear space: Dashed clearance boundary</span>
      </div>'''

replacement = '''      <div class="heatmap-legend-bar" aria-label="Heatmap status legend">
        <span><strong>Legend:</strong></span>
        <span class="heatmap-legend-item"><span class="legend-swatch-pass" aria-hidden="true"></span> PASS: Solid border (&Delta;E within tolerance)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-fail" aria-hidden="true">///</span> FAIL: Diagonal hatch + FAIL label (&Delta;E above threshold)</span>
        <span class="heatmap-legend-item"><span class="legend-swatch-logo" aria-hidden="true">[ ]</span> Clear space: Dashed clearance boundary</span>
      </div>
      ${cs.located_method && cs.located_method !== 'None' ? `
        <div class="heatmap-logo-source-indicator" style="padding: 4px 12px; font-size: 11.5px; color: var(--slate-700); background: #F8FAFC; border-top: 1px solid var(--border-color);">
          Logo located by: <strong>${escapeHtml(cs.located_method)}</strong>
        </div>
      ` : ''}'''

assert target in js, "target not found in app.js"
js = js.replace(target, replacement)

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(js)

print("Added logo location method indicator to heatmap viewer")
