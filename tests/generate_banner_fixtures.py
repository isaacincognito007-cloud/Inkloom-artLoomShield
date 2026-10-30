"""
Script to generate the suite of at least 12 banner test fixtures and expected.json (H2 d).
Creates:
- tests/fixtures/banners/approved_logo_template.png (the approved template logo mark)
- 12 labelled fixture files (SVG and PNG)
- tests/fixtures/banners/expected.json (expected outcomes for each fixture)
"""

import base64
import json
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "banners"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# NovaPay Brand Colors:
# Primary: #17191C (dark slate)
# Secondary: #0B2545 (navy blue)
# Accent: #134074 (medium blue)
# Background: #FFFFFF / #EEF4F8


def create_approved_logo_template() -> Path:
    """Create a distinct 60x30 monochrome approved brand logo template."""
    img = Image.new("RGBA", (60, 30), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Distinct 'N' emblem in dark slate
    draw.rectangle([8, 6, 14, 24], fill=(23, 25, 28, 255))
    draw.polygon([(14, 6), (22, 24), (28, 24), (20, 6)], fill=(23, 25, 28, 255))
    draw.rectangle([28, 6, 34, 24], fill=(23, 25, 28, 255))
    # Small dot accent
    draw.ellipse([42, 10, 48, 16], fill=(19, 64, 116, 255))
    draw.rectangle([42, 20, 52, 24], fill=(23, 25, 28, 255))
    
    path = FIXTURES_DIR / "approved_logo_template.png"
    img.save(path, format="PNG")
    return path


def generate_all_fixtures():
    tpl_path = create_approved_logo_template()
    tpl_img = Image.open(tpl_path)

    expected = {}

    # 1. On-palette pass (SVG)
    svg_01 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect x="20" y="20" width="360" height="200" fill="#EEF4F8" rx="8"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
  <text x="40" y="120" fill="#0B2545" font-size="20" font-family="sans-serif">NovaPay Global Settlement</text>
  <text x="40" y="160" fill="#134074" font-size="14" font-family="sans-serif">Compliant with configured palette tokens.</text>
</svg>"""
    (FIXTURES_DIR / "01_on_palette_pass.svg").write_text(svg_01, encoding="utf-8")
    expected["01_on_palette_pass.svg"] = {
        "description": "On-palette pass banner with compliant brand colors and marked logo",
        "palette_status": "pass",
        "flagged_cells_count": 0,
        "clear_space_state": "Passed",
        "contrast_state": "Passed",
    }

    # 2. One off-palette cell (SVG)
    svg_02 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect x="20" y="20" width="160" height="90" fill="#EEF4F8"/>
  <!-- Bright non-brand magenta cell in R1C2 -->
  <rect x="220" y="20" width="160" height="90" fill="#FF007F"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
</svg>"""
    (FIXTURES_DIR / "02_one_off_palette_cell.svg").write_text(svg_02, encoding="utf-8")
    expected["02_one_off_palette_cell.svg"] = {
        "description": "One off-palette neon magenta block flagging exactly one cell",
        "palette_status": "fail",
        "flagged_cells_count": 1,
    }

    # 3. Small off-palette element (SVG)
    svg_03 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
  <text x="40" y="120" fill="#17191C" font-size="16">Enterprise Payouts</text>
  <!-- Small unapproved lime green badge icon -->
  <circle cx="350" cy="50" r="12" fill="#39FF14"/>
</svg>"""
    (FIXTURES_DIR / "03_small_off_palette_element.svg").write_text(svg_03, encoding="utf-8")
    expected["03_small_off_palette_element.svg"] = {
        "description": "Small lime green badge icon flagging the top-right cell",
        "palette_status": "fail",
        "flagged_cells_count": 1,
    }

    # 4. Low-contrast SVG text (SVG)
    # #94A3B8 on #FFFFFF has contrast 2.56:1, strictly failing WCAG 4.5:1
    svg_04 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
  <text x="40" y="140" fill="#94A3B8" font-size="16" font-family="sans-serif">Faint subtext with low contrast ratio 2.56 to 1</text>
</svg>"""
    (FIXTURES_DIR / "04_low_contrast_svg_text.svg").write_text(svg_04, encoding="utf-8")
    expected["04_low_contrast_svg_text.svg"] = {
        "description": "SVG text with insufficient contrast #94A3B8 on #FFFFFF",
        "contrast_state": "Findings",
        "contrast_measured_count": 1,
    }

    # 5. Inherited-fill text (SVG)
    svg_05 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
  <g fill="#0B2545">
    <text x="40" y="130" font-size="18" font-family="sans-serif">Text inheriting fill from parent group</text>
  </g>
</svg>"""
    (FIXTURES_DIR / "05_inherited_fill_text.svg").write_text(svg_05, encoding="utf-8")
    expected["05_inherited_fill_text.svg"] = {
        "description": "SVG text inheriting fill #0B2545 from enclosing <g> group",
        "contrast_state": "Passed",
        "contrast_measured_count": 1,
    }

    # 6. Unresolvable fill (SVG)
    svg_06 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#17191C"/>
      <stop offset="100%" stop-color="#134074"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="40" y="40" width="80" height="36" fill="#17191C"/>
  <text x="40" y="130" fill="url(#grad1)" font-size="18">Gradient Text Unresolvable As Single Hex</text>
</svg>"""
    (FIXTURES_DIR / "06_unresolvable_fill.svg").write_text(svg_06, encoding="utf-8")
    expected["06_unresolvable_fill.svg"] = {
        "description": "SVG text using gradient fill url(#grad1) unresolvable to static color",
        "contrast_measured_count": 0,
    }

    # 7. Crowded logo (SVG)
    # Logo placed at x=6, y=6 (edge distance 6 px < 16 px required and ratio 6/40 = 0.15 < 0.25)
    svg_07 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="6" y="6" width="80" height="40" fill="#17191C"/>
  <rect x="90" y="10" width="100" height="30" fill="#0B2545"/>
</svg>"""
    (FIXTURES_DIR / "07_crowded_logo.svg").write_text(svg_07, encoding="utf-8")
    expected["07_crowded_logo.svg"] = {
        "description": "Logo crowded too close to edge and sibling element",
        "clear_space_state": "Findings",
        "clear_space_passed": False,
        "located_method": "SVG marker",
    }

    # 8. Ample clear space (SVG)
    # Centered logo at x=150, y=90 on 400x240 canvas (all clearances >= 90 px)
    svg_08 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect id="logo" data-loomshield-logo="true" x="150" y="90" width="100" height="40" fill="#17191C"/>
</svg>"""
    (FIXTURES_DIR / "08_ample_clear_space.svg").write_text(svg_08, encoding="utf-8")
    expected["08_ample_clear_space.svg"] = {
        "description": "Logo placed in canvas center with generous clearance on all sides",
        "clear_space_state": "Passed",
        "clear_space_passed": True,
        "located_method": "SVG marker",
    }

    # 9. Transformed logo group (SVG)
    svg_09 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <g id="logo" data-loomshield-logo="true" transform="translate(120, 70)">
    <rect x="0" y="0" width="80" height="40" fill="#17191C"/>
    <circle cx="20" cy="20" r="10" fill="#134074"/>
  </g>
</svg>"""
    (FIXTURES_DIR / "09_transformed_logo_group.svg").write_text(svg_09, encoding="utf-8")
    expected["09_transformed_logo_group.svg"] = {
        "description": "Logo inside <g> element with translate() transform matrix",
        "clear_space_state": "Passed",
        "clear_space_passed": True,
        "located_method": "SVG marker",
    }

    # 10. Template-match positive (PNG)
    # 400x240 banner with approved logo pasted at (160, 90)
    img_10 = Image.new("RGBA", (400, 240), (255, 255, 255, 255))
    draw_10 = ImageDraw.Draw(img_10)
    draw_10.rectangle([20, 20, 380, 220], fill=(238, 244, 248, 255))
    # Paste template at (160, 90)
    img_10.paste(tpl_img, (160, 90), tpl_img)
    img_10.save(FIXTURES_DIR / "10_template_match_positive.png", format="PNG")
    expected["10_template_match_positive.png"] = {
        "description": "Raster PNG containing approved logo template at 1.0x scale",
        "template_match": True,
        "min_score": 0.80,
        "clear_space_state": "Passed",
        "located_method_prefix": "Template match",
    }

    # 11. Template-match negative (PNG)
    # 400x240 banner with completely different geometry, no approved logo
    img_11 = Image.new("RGBA", (400, 240), (23, 25, 28, 255))
    draw_11 = ImageDraw.Draw(img_11)
    for i in range(10):
        draw_11.line([(i * 40, 0), (400 - i * 40, 240)], fill=(11, 37, 69, 255), width=4)
    img_11.save(FIXTURES_DIR / "11_template_match_negative.png", format="PNG")
    expected["11_template_match_negative.png"] = {
        "description": "Raster PNG with no logo mark, template match should fail",
        "template_match": False,
        "clear_space_state": "Not Checked",
        "reason_contains": "Not Checked: approved logo not found",
    }

    # 12. No logo (SVG)
    svg_12 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" width="400" height="240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <rect x="20" y="20" width="360" height="200" fill="#EEF4F8"/>
  <text x="50" y="120" fill="#17191C" font-size="20">Card With No Logo Marker</text>
</svg>"""
    (FIXTURES_DIR / "12_no_logo.svg").write_text(svg_12, encoding="utf-8")
    expected["12_no_logo.svg"] = {
        "description": "SVG banner with no logo element or marker at all",
        "clear_space_state": "Not Checked",
        "located_method": "None",
    }

    # Save expected.json
    expected_path = FIXTURES_DIR / "expected.json"
    with open(expected_path, "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2)

    print(f"Generated {len(expected)} banner fixtures and expected.json in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all_fixtures()
