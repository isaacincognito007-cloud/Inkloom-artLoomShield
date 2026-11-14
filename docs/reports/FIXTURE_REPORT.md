# Visual Heatmap Inspector — Fixture Evaluation Report

**Generated Date:** `2026-10-30`  
**Total Fixtures Evaluated:** `12`  
**Total Assertion Checks:** `28`  
**Hits:** `25` • **Misses:** `3`  
**Fixture Pass Rate:** `89.3%`

---

## Executive Summary

This report documents the empirical evaluation of the LoomShield Visual Heatmap Inspector against a committed benchmark suite of 12 labelled banner fixtures (`tests/fixtures/banners/`).

The suite verifies:
1. **Delta-E 2000 Palette Compliance:** Grid-based dominant color extraction and flagging of off-palette cells.
2. **Text Contrast (WCAG AA):** Vector text contrast extraction, inherited group fills, and unresolvable gradient detection.
3. **Logo Clear Space & Multi-Scale Template Matching:** Precedence resolution across user-drawn boxes, SVG markers, multi-scale NCC template matching (0.5x - 2.0x), and PNG alpha bounds.

---

## Fixture Results Table

| Fixture File | Category & Description | Assertions | Status |
| :--- | :--- | :---: | :---: |
| `01_on_palette_pass.svg` | On-palette pass banner with compliant brand colors and marked logo | 4 checks | **MISS (1 failed)** |
| `02_one_off_palette_cell.svg` | One off-palette neon magenta block flagging exactly one cell | 2 checks | **HIT (100%)** |
| `03_small_off_palette_element.svg` | Small lime green badge icon flagging the top-right cell | 2 checks | **MISS (2 failed)** |
| `04_low_contrast_svg_text.svg` | SVG text with insufficient contrast #94A3B8 on #FFFFFF | 2 checks | **HIT (100%)** |
| `05_inherited_fill_text.svg` | SVG text inheriting fill #0B2545 from enclosing <g> group | 2 checks | **HIT (100%)** |
| `06_unresolvable_fill.svg` | SVG text using gradient fill url(#grad1) unresolvable to static color | 1 checks | **HIT (100%)** |
| `07_crowded_logo.svg` | Logo crowded too close to edge and sibling element | 3 checks | **HIT (100%)** |
| `08_ample_clear_space.svg` | Logo placed in canvas center with generous clearance on all sides | 3 checks | **HIT (100%)** |
| `09_transformed_logo_group.svg` | Logo inside <g> element with translate() transform matrix | 3 checks | **HIT (100%)** |
| `10_template_match_positive.png` | Raster PNG containing approved logo template at 1.0x scale | 2 checks | **HIT (100%)** |
| `11_template_match_negative.png` | Raster PNG with no logo mark, template match should fail | 2 checks | **HIT (100%)** |
| `12_no_logo.svg` | SVG banner with no logo element or marker at all | 2 checks | **HIT (100%)** |

---

## Detailed Evaluation Breakdown

### `01_on_palette_pass.svg`

*On-palette pass banner with compliant brand colors and marked logo*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Palette Status | `pass` | `pass` | **HIT** |
| Flagged Cells Count | `0` | `0` | **HIT** |
| Text Contrast State | `Passed` | `Passed` | **HIT** |
| Clear Space State | `Passed` | `Findings` | **MISS** |

### `02_one_off_palette_cell.svg`

*One off-palette neon magenta block flagging exactly one cell*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Palette Status | `fail` | `fail` | **HIT** |
| Flagged Cells Count | `1` | `1` | **HIT** |

### `03_small_off_palette_element.svg`

*Small lime green badge icon flagging the top-right cell*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Palette Status | `fail` | `pass` | **MISS** |
| Flagged Cells Count | `1` | `0` | **MISS** |

### `04_low_contrast_svg_text.svg`

*SVG text with insufficient contrast #94A3B8 on #FFFFFF*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Text Contrast State | `Findings` | `Findings` | **HIT** |
| Contrast Measured Count | `1` | `1` | **HIT** |

### `05_inherited_fill_text.svg`

*SVG text inheriting fill #0B2545 from enclosing <g> group*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Text Contrast State | `Passed` | `Passed` | **HIT** |
| Contrast Measured Count | `1` | `1` | **HIT** |

### `06_unresolvable_fill.svg`

*SVG text using gradient fill url(#grad1) unresolvable to static color*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Contrast Measured Count | `0` | `0` | **HIT** |

### `07_crowded_logo.svg`

*Logo crowded too close to edge and sibling element*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Findings` | `Findings` | **HIT** |
| Clear Space Passed | `False` | `False` | **HIT** |
| Located Method | `SVG marker` | `SVG marker` | **HIT** |

### `08_ample_clear_space.svg`

*Logo placed in canvas center with generous clearance on all sides*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Passed` | `Passed` | **HIT** |
| Clear Space Passed | `True` | `True` | **HIT** |
| Located Method | `SVG marker` | `SVG marker` | **HIT** |

### `09_transformed_logo_group.svg`

*Logo inside <g> element with translate() transform matrix*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Passed` | `Passed` | **HIT** |
| Clear Space Passed | `True` | `True` | **HIT** |
| Located Method | `SVG marker` | `SVG marker` | **HIT** |

### `10_template_match_positive.png`

*Raster PNG containing approved logo template at 1.0x scale*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Passed` | `Passed` | **HIT** |
| Located Method Prefix | `Template match` | `Template match (NCC score: 1.00)` | **HIT** |

### `11_template_match_negative.png`

*Raster PNG with no logo mark, template match should fail*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Not Checked` | `Not Checked` | **HIT** |
| Reason Text | `Not Checked: approved logo not found` | `Not Checked: approved logo not found...` | **HIT** |

### `12_no_logo.svg`

*SVG banner with no logo element or marker at all*

| Assertion Metric | Expected | Actual | Result |
| :--- | :--- | :--- | :---: |
| Clear Space State | `Not Checked` | `Not Checked` | **HIT** |
| Located Method | `None` | `None` | **HIT** |

---

## Extended Scale and Decoy Fixtures Evaluation (0.7x, 1.5x, Near-Miss Decoy)

To evaluate multi-scale invariance and discrimination against false positive decoys beyond the 12 core fixtures, three additional fixtures were tested:

### `13_template_match_0_7x.png`
*Raster PNG with approved brand logo scaled down to 0.7x ($42\times21\text{ px}$)*
- **Expected:** Template match positive, detected at nearest scale ($0.75\times$), NCC score $\ge 0.80$.
- **Actual:** Located method `Template match (NCC score: 0.91)`, detected scale `0.75`, bounding box `{'x': 159.0, 'y': 89.0, 'width': 45.0, 'height': 22.0}`.
- **Clear Space:** Passed (minimum clearance 89.0 px / $4.05\times$ logo height).
- **Result:** **HIT** (verified by `test_h2_template_match_scale_and_decoy_fixtures`).

### `14_template_match_1_5x.png`
*Raster PNG with approved brand logo scaled up to 1.5x ($90\times45\text{ px}$)*
- **Expected:** Template match positive, detected at scale $1.5\times$, NCC score $\ge 0.80$.
- **Actual:** Located method `Template match (NCC score: 1.00)`, detected scale `1.5`, bounding box `{'x': 160.0, 'y': 90.0, 'width': 90.0, 'height': 45.0}`.
- **Clear Space:** Passed (minimum clearance 90.0 px / $2.0\times$ logo height).
- **Result:** **HIT** (verified by `test_h2_template_match_scale_and_decoy_fixtures`).

### `15_template_match_decoy.png`
*Raster PNG with a near-miss decoy emblem (chevron/arrow shape in brand slate with dot accent)*
- **Expected:** Template match negative; NCC score must remain below the 0.80 threshold to prevent false-positive logo claims.
- **Actual:** Max NCC score below 0.80 across all scales ($0.5\times$ to $2.0\times$). Clear space state reports `Not Checked: approved logo not found`.
- **Result:** **HIT** (verified by `test_h2_template_match_scale_and_decoy_fixtures`).

---

## Methodology & Verification Notes

- **No Synthetic Tuning:** Fixtures were created from realistic design specifications and are evaluated strictly against their declared physical properties.
- **Traceability Test:** Automated test `test_h2_heatmap_fixture_suite_against_expected_json` in `tests/test_heatmap_inspector.py` executes every fixture against `expected.json`.
