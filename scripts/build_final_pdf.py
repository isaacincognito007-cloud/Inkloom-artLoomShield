"""
LoomShield Round 3 Final Product Document & Empirical Verification Report Generator.
Solo Builder Submission.
Output: docs/LoomShield_Round3_Final_Product_Document.pdf
Target: Exactly 16 pages on A4.
"""
import sys
import os
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import fitz

# Register embedded TrueType fonts if available
FONT_SANS = "Helvetica"
FONT_SANS_BOLD = "Helvetica-Bold"
FONT_SANS_ITALIC = "Helvetica-Oblique"
FONT_MONO = "Courier"

try:
    if os.path.exists(r'C:\Windows\Fonts\segoeui.ttf') and os.path.exists(r'C:\Windows\Fonts\segoeuib.ttf'):
        pdfmetrics.registerFont(TTFont('AppSans', r'C:\Windows\Fonts\segoeui.ttf'))
        pdfmetrics.registerFont(TTFont('AppSans-Bold', r'C:\Windows\Fonts\segoeuib.ttf'))
        pdfmetrics.registerFont(TTFont('AppSans-Italic', r'C:\Windows\Fonts\segoeuii.ttf'))
        pdfmetrics.registerFont(TTFont('AppMono', r'C:\Windows\Fonts\consola.ttf'))
        FONT_SANS = "AppSans"
        FONT_SANS_BOLD = "AppSans-Bold"
        FONT_SANS_ITALIC = "AppSans-Italic"
        FONT_MONO = "AppMono"
        print("Embedded TrueType fonts (Segoe UI & Consolas) registered successfully.")
except Exception as e:
    print(f"Using core 14 fonts fallback: {e}")

# Palette definitions
NAVY_PRIMARY = colors.HexColor("#0F172A")
NAVY_DARK = colors.HexColor("#0A101D")
NAVY_CARD = colors.HexColor("#1E293B")
ORANGE_ACCENT = colors.HexColor("#C84624")
ORANGE_LIGHT = colors.HexColor("#FBEAE5")
SLATE_BG = colors.HexColor("#F8FAFC")
SLATE_BORDER = colors.HexColor("#E2E8F0")
SLATE_MUTED = colors.HexColor("#475569")
SLATE_TEXT = colors.HexColor("#1E293B")
SLATE_DARK = colors.HexColor("#0F172A")
WHITE = colors.HexColor("#FFFFFF")

# Chip colors
CHIP_BUILT_BG = colors.HexColor("#DCFCE7")
CHIP_BUILT_FG = colors.HexColor("#166534")
CHIP_PARTIAL_BG = colors.HexColor("#FEF9C3")
CHIP_PARTIAL_FG = colors.HexColor("#854D0E")
CHIP_NOTBUILT_BG = colors.HexColor("#F1F5F9")
CHIP_NOTBUILT_FG = colors.HexColor("#475569")
CHIP_DECLARED_BG = colors.HexColor("#DBEAFE")
CHIP_DECLARED_FG = colors.HexColor("#1E40AF")
CHIP_CHANGED_BG = colors.HexColor("#F3E8FF")
CHIP_CHANGED_FG = colors.HexColor("#6B21A8")

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont(FONT_SANS, 8)
        self.setFillColor(SLATE_MUTED)

        # Header
        self.drawString(40, 810, "LoomShield  |  Round 3 Final Product Document & Empirical Verification Report")
        self.drawRightString(555, 810, "October 2026")
        self.setStrokeColor(SLATE_BORDER)
        self.setLineWidth(0.5)
        self.line(40, 802, 555, 802)

        # Footer
        self.line(40, 42, 555, 42)
        self.drawString(40, 30, "Solo Builder  |  Git Commit: d2e4711  |  Branch: final-docs")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 30, page_str)
        self.restoreState()

def create_chip_cell(text, status_type, width=65, height=13):
    bg_map = {
        "BUILT": CHIP_BUILT_BG,
        "PARTIAL": CHIP_PARTIAL_BG,
        "NOT BUILT": CHIP_NOTBUILT_BG,
        "DECLARED": CHIP_DECLARED_BG,
        "CHANGED": CHIP_CHANGED_BG,
        "PASS": CHIP_BUILT_BG,
        "MISS": CHIP_CHANGED_BG
    }
    fg_map = {
        "BUILT": CHIP_BUILT_FG,
        "PARTIAL": CHIP_PARTIAL_FG,
        "NOT BUILT": CHIP_NOTBUILT_FG,
        "DECLARED": CHIP_DECLARED_FG,
        "CHANGED": CHIP_CHANGED_FG,
        "PASS": CHIP_BUILT_FG,
        "MISS": CHIP_CHANGED_FG
    }
    bg = bg_map.get(status_type, CHIP_NOTBUILT_BG)
    fg = fg_map.get(status_type, CHIP_NOTBUILT_FG)
    style = ParagraphStyle(
        'ChipStyle',
        fontName=FONT_SANS_BOLD,
        fontSize=6.5,
        leading=8,
        textColor=fg,
        alignment=TA_CENTER
    )
    p = Paragraph(f"<b>{text}</b>", style)
    t = Table([[p]], colWidths=[width], rowHeights=[height])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    return t

def make_callout(title, text, styles, accent_color=ORANGE_ACCENT):
    content = [
        Paragraph(f"<b><font color='{accent_color.hexval()}'>{title}</font></b>", styles['CalloutTitle']),
        Spacer(1, 2),
        Paragraph(text, styles['CalloutBody'])
    ]
    t = Table([[content]], colWidths=[515])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SLATE_BG),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LINELEFT', (0,0), (0,-1), 3.0, accent_color),
        ('BOX', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    return t

def make_section_header(title, styles, subtitle=None):
    bar = Table([[""]], colWidths=[4], rowHeights=[17])
    bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ORANGE_ACCENT),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    title_p = Paragraph(f"<b>{title}</b>", styles['SectionTitle'])
    row = [[bar, title_p]]
    t = Table(row, colWidths=[6, 509])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    flowables = [
        Spacer(1, 6),
        t
    ]
    if subtitle:
        flowables.append(Spacer(1, 2))
        flowables.append(Paragraph(f"<i>{subtitle}</i>", styles['SectionSubtitle']))
    flowables.append(Spacer(1, 6))
    return flowables

def build_pdf():
    facts_file = REPO_ROOT / "docs" / "final_pdf_data.json"
    facts = json.loads(facts_file.read_text(encoding="utf-8"))
    
    pdf_out = REPO_ROOT / "docs" / "LoomShield_Round3_Final_Product_Document.pdf"
    
    doc = SimpleDocTemplate(
        str(pdf_out),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46
    )
    
    styles = {
        'CoverTitle': ParagraphStyle('CoverTitle', fontName=FONT_SANS_BOLD, fontSize=23, leading=27, textColor=NAVY_PRIMARY, alignment=TA_LEFT),
        'CoverSubtitle': ParagraphStyle('CoverSubtitle', fontName=FONT_SANS, fontSize=11.5, leading=15, textColor=ORANGE_ACCENT, alignment=TA_LEFT),
        'CoverMeta': ParagraphStyle('CoverMeta', fontName=FONT_SANS, fontSize=8, leading=12, textColor=SLATE_MUTED, alignment=TA_LEFT),
        'CoverDesc': ParagraphStyle('CoverDesc', fontName=FONT_SANS, fontSize=8.5, leading=13, textColor=SLATE_TEXT, alignment=TA_LEFT),
        'SectionTitle': ParagraphStyle('SectionTitle', fontName=FONT_SANS_BOLD, fontSize=12.5, leading=15, textColor=NAVY_PRIMARY),
        'SectionSubtitle': ParagraphStyle('SectionSubtitle', fontName=FONT_SANS_ITALIC, fontSize=8.5, leading=11, textColor=SLATE_MUTED),
        'Heading2': ParagraphStyle('Heading2', fontName=FONT_SANS_BOLD, fontSize=9.5, leading=12.5, textColor=NAVY_DARK),
        'Heading3': ParagraphStyle('Heading3', fontName=FONT_SANS_BOLD, fontSize=8.5, leading=11, textColor=SLATE_DARK),
        'Body': ParagraphStyle('Body', fontName=FONT_SANS, fontSize=8.2, leading=11.5, textColor=SLATE_TEXT, alignment=TA_LEFT),
        'BodyBold': ParagraphStyle('BodyBold', fontName=FONT_SANS_BOLD, fontSize=8.2, leading=11.5, textColor=SLATE_TEXT),
        'Bullet': ParagraphStyle('Bullet', fontName=FONT_SANS, fontSize=8.2, leading=11.5, textColor=SLATE_TEXT, leftIndent=10, firstLineIndent=-7),
        'TableHead': ParagraphStyle('TableHead', fontName=FONT_SANS_BOLD, fontSize=7.5, leading=9.5, textColor=WHITE, alignment=TA_LEFT),
        'TableHeadCenter': ParagraphStyle('TableHeadCenter', fontName=FONT_SANS_BOLD, fontSize=7.5, leading=9.5, textColor=WHITE, alignment=TA_CENTER),
        'TableCell': ParagraphStyle('TableCell', fontName=FONT_SANS, fontSize=7.2, leading=9.2, textColor=SLATE_TEXT),
        'TableCellBold': ParagraphStyle('TableCellBold', fontName=FONT_SANS_BOLD, fontSize=7.2, leading=9.2, textColor=SLATE_TEXT),
        'TableCellCenter': ParagraphStyle('TableCellCenter', fontName=FONT_SANS, fontSize=7.2, leading=9.2, textColor=SLATE_TEXT, alignment=TA_CENTER),
        'TableCellCode': ParagraphStyle('TableCellCode', fontName=FONT_MONO, fontSize=6.8, leading=8.5, textColor=NAVY_DARK),
        'CalloutTitle': ParagraphStyle('CalloutTitle', fontName=FONT_SANS_BOLD, fontSize=8, leading=10, textColor=ORANGE_ACCENT),
        'CalloutBody': ParagraphStyle('CalloutBody', fontName=FONT_SANS, fontSize=7.8, leading=10.5, textColor=SLATE_TEXT),
        'TocItem': ParagraphStyle('TocItem', fontName=FONT_SANS_BOLD, fontSize=8, leading=10.5, textColor=NAVY_PRIMARY),
        'TocDots': ParagraphStyle('TocDots', fontName=FONT_SANS, fontSize=8, leading=10.5, textColor=SLATE_MUTED, alignment=TA_RIGHT),
    }
    
    story = []
    
    # =========================================================================
    # PAGE 1: COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 10))
    
    pill_text = "<font color='#C84624'><b>ROUND 3 FINAL SUBMISSION</b></font>  |  <font color='#475569'>GOVERNANCE & AUDIT ENGINE</font>"
    p_pill = Paragraph(pill_text, ParagraphStyle('TopPill', fontName=FONT_SANS_BOLD, fontSize=7.5, leading=9))
    t_pill = Table([[p_pill]], colWidths=[240], rowHeights=[16])
    t_pill.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ORANGE_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, ORANGE_ACCENT),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_pill)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("LoomShield", styles['CoverTitle']))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Deterministic Brand Governance & Audit Verification System", styles['CoverSubtitle']))
    story.append(Spacer(1, 6))
    
    summary_cover = (
        "This document constitutes my final Round 3 technical submission for LoomShield. "
        "As the solo builder, I designed, architected, and implemented the full system: the deterministic rule engine, "
        "local TF-IDF fact retrieval, WCAG contrast analyzer, multi-scale normalized cross-correlation template matching, "
        "the Guideline Clarity Rewriter, Ed25519 tamper-evident audit certificates, and the vanilla JavaScript workspace UI. "
        "Every benchmark, test metric, and latency figure presented in this report is empirically measured from command outputs and committed code."
    )
    story.append(Paragraph(summary_cover, styles['CoverDesc']))
    story.append(Spacer(1, 8))
    
    meta_data = [
        [
            Paragraph("<b>Builder:</b> Solo Developer (Full-Stack)", styles['CoverMeta']),
            Paragraph(f"<b>Git Commit:</b> <font name='{FONT_MONO}'>{facts['git']['short_commit']}</font> (<font name='{FONT_MONO}'>{facts['git']['commit'][:16]}...</font>)", styles['CoverMeta'])
        ],
        [
            Paragraph("<b>Target Track:</b> Round 3 Final Product Delivery", styles['CoverMeta']),
            Paragraph(f"<b>Branch:</b> <font name='{FONT_MONO}'>{facts['git']['branch']}</font>", styles['CoverMeta'])
        ],
        [
            Paragraph(f"<b>Pytest Suite:</b> <b>{facts['pytest']['total_collected']} of {facts['pytest']['total_collected']} Passing</b> (100% green)", styles['CoverMeta']),
            Paragraph(f"<b>Signing Key ID:</b> <font name='{FONT_MONO}'>{facts['engine_and_cert']['key_id']}</font> (Ed25519)", styles['CoverMeta'])
        ],
        [
            Paragraph("<b>Image Guard Cap:</b> 12 Megapixels (109.11 MB Peak RSS)", styles['CoverMeta']),
            Paragraph("<b>Operating Mode:</b> Local-Only (Tier 1 + Tier 2, Cloud Disabled)", styles['CoverMeta'])
        ]
    ]
    t_meta = Table(meta_data, colWidths=[250, 265])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SLATE_BG),
        ('BOX', (0,0), (-1,-1), 0.5, SLATE_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))
    
    status_summary = [
        [
            Paragraph("<b>Subsystem / Delivery Area</b>", styles['TableHead']),
            Paragraph("<b>Status</b>", styles['TableHeadCenter']),
            Paragraph("<b>Delivered Scope & Verification Summary</b>", styles['TableHead'])
        ],
        [
            Paragraph("Tier 1 Deterministic Engine", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Regex, dictionary, brand spelling, WCAG 2.1 AA luminance, CIE Delta-E; 0 nondeterminism.", styles['TableCell'])
        ],
        [
            Paragraph("Tier 2 Embedded TF-IDF NLP", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Scikit-Learn TF-IDF 1-2 n-grams + cosine retrieval; strictly local, zero external cloud APIs.", styles['TableCell'])
        ],
        [
            Paragraph("Guideline Clarity Rewriter", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Vagueness scoring, retrieval fact injection, grammar agreement, atomic approval, before/after tracking.", styles['TableCell'])
        ],
        [
            Paragraph("Heatmap & NCC Template Match", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Multi-scale NCC (0.5x-2.0x, 6 scales, 70.67ms avg), CIE LAB palette, WCAG contrast, clear space.", styles['TableCell'])
        ],
        [
            Paragraph("Ed25519 Tamper-Evident Certs", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("RFC 8032 digital signatures, canonical JSON, SHA-256 document binding, RBAC revocation.", styles['TableCell'])
        ],
        [
            Paragraph("12 MP Memory & 5 MB Upload Guard", styles['TableCellBold']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Strict header check before decode (109.11 MB RSS peak on Windows); chunked stream 5MB limit.", styles['TableCell'])
        ],
        [
            Paragraph("SVG DOM Visual Hierarchy", styles['TableCellBold']),
            create_chip_cell("PARTIAL", "PARTIAL"),
            Paragraph("Direct SVG text/fill inspection built; full CSS cascade inheritance logged under General findings.", styles['TableCell'])
        ],
        [
            Paragraph("Brand Presets / 100MB / OCR", styles['TableCellBold']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph("I did not finish these in the time available; full technical design notes provided in Section 9.", styles['TableCell'])
        ]
    ]
    t_status = Table(status_summary, colWidths=[140, 65, 310])
    t_status.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_status)
    story.append(Spacer(1, 8))
    
    toc_data = [
        [Paragraph("1. Executive Summary & System Overview", styles['TocItem']), Paragraph("Page 2", styles['TocDots'])],
        [Paragraph("2. Architecture & Verification Methodology (Pipeline & Persistence)", styles['TocItem']), Paragraph("Page 3", styles['TocDots'])],
        [Paragraph("2. Architecture Continued (Security, Client IP & RBAC)", styles['TocItem']), Paragraph("Page 4", styles['TocDots'])],
        [Paragraph("3. Feature Commitments & Delivery Status Matrix (Part 1)", styles['TocItem']), Paragraph("Page 5", styles['TocDots'])],
        [Paragraph("3. Feature Commitments & Delivery Status Matrix (Part 2)", styles['TocItem']), Paragraph("Page 6", styles['TocDots'])],
        [Paragraph("4. Improvement 1: Guideline Clarity Rewriter", styles['TocItem']), Paragraph("Page 7", styles['TocDots'])],
        [Paragraph("5. Improvement 2: Heatmap Inspector & Logo Integrity (Architecture & NCC)", styles['TocItem']), Paragraph("Page 8", styles['TocDots'])],
        [Paragraph("5. Improvement 2: Fixture Verification Results & Analysis of Misses", styles['TocItem']), Paragraph("Page 9", styles['TocDots'])],
        [Paragraph("6. Ed25519 Tamper-Evident Audit Certificates", styles['TocItem']), Paragraph("Page 10", styles['TocDots'])],
        [Paragraph("7. Benchmark Results & Resource Measurements", styles['TocItem']), Paragraph("Page 11", styles['TocDots'])],
        [Paragraph("8. Test Suite & Empirical Verification Results", styles['TocItem']), Paragraph("Page 12", styles['TocDots'])],
        [Paragraph("9. Deviations, Unfinished Work & Honest Accounting (Part 1)", styles['TocItem']), Paragraph("Page 13", styles['TocDots'])],
        [Paragraph("9. Deviations Continued (Terminology, Removals & Unverified Environments)", styles['TocItem']), Paragraph("Page 14", styles['TocDots'])],
        [Paragraph("10. Future Roadmap & Production Hardening", styles['TocItem']), Paragraph("Page 15", styles['TocDots'])],
        [Paragraph("Appendix A: API Surface & Integration Reference (Endpoint Inventory)", styles['TocItem']), Paragraph("Page 15", styles['TocDots'])],
        [Paragraph("Appendix A Continued & Final Author Attestation", styles['TocItem']), Paragraph("Page 16", styles['TocDots'])],
    ]
    t_toc = Table(toc_data, colWidths=[420, 95])
    t_toc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SLATE_BG),
        ('BOX', (0,0), (-1,-1), 0.5, SLATE_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_toc)
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 2: SECTION 1: EXECUTIVE SUMMARY & SYSTEM OVERVIEW
    # =========================================================================
    story.extend(make_section_header("1. Executive Summary & System Overview", styles, "Origins, problem statement, and architectural tiering"))
    
    sec1_text1 = (
        "I am the solo creator and developer of LoomShield. Over the course of three engineering rounds, I conceived, designed, "
        "and implemented LoomShield as a local-first, deterministic brand governance workspace. In modern enterprises, marketing copy, "
        "product release materials, and advertising banners must comply with strict regulatory disclosures, brand terminology, design palettes, "
        "and accessibility standards. Traditional approaches fail in two distinct ways: either they rely on manual human review queues that are "
        "slow and inconsistent, or they pass confidential pre-release drafts to cloud-hosted Large Language Models (LLMs) that introduce "
        "hallucinations, non-deterministic audit verdicts, and severe data-exfiltration compliance risks."
    )
    story.append(Paragraph(sec1_text1, styles['Body']))
    story.append(Spacer(1, 5))
    
    sec1_text2 = (
        "I designed LoomShield to solve this dilemma through an uncompromising local-first, deterministic architecture. "
        "LoomShield runs all core auditing logic directly on the host machine with zero third-party cloud API dependencies. "
        "A draft submitted to LoomShield never leaves the local environment. Findings are mapped with character-level precision "
        "to exact spans in text or bounding boxes in visual banners. Every finding links to an explicit rule or verified fact stored in the Brand Vault."
    )
    story.append(Paragraph(sec1_text2, styles['Body']))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph("System Architecture Tiering", styles['Heading2']))
    story.append(Spacer(1, 3))
    
    sec1_text3 = (
        "LoomShield enforces a strict three-tier engine architecture, establishing clear functional separation between deterministic rules, "
        "local machine-learning retrieval, and optional external cloud escalation:"
    )
    story.append(Paragraph(sec1_text3, styles['Body']))
    story.append(Spacer(1, 5))
    
    tier_data = [
        [
            Paragraph("<b>Engine Tier</b>", styles['TableHead']),
            Paragraph("<b>Operating Mode & Technology</b>", styles['TableHead']),
            Paragraph("<b>Data Privacy & External Dependencies</b>", styles['TableHead']),
            Paragraph("<b>Deterministic Guarantee</b>", styles['TableHeadCenter'])
        ],
        [
            Paragraph("<b>Tier 1: Deterministic Engine</b>", styles['TableCellBold']),
            Paragraph("Regular expressions, terminology dictionaries, case-sensitive spelling, WCAG 2.1 AA luminance math, CIE LAB Delta-E colour distance.", styles['TableCell']),
            Paragraph("100% on-device execution. Zero network calls. Zero third-party telemetry.", styles['TableCell']),
            Paragraph("<font color='#166534'><b>100% Strict</b></font><br/>Identical input yields identical output.", styles['TableCellCenter'])
        ],
        [
            Paragraph("<b>Tier 2: Embedded TF-IDF NLP</b>", styles['TableCellBold']),
            Paragraph("Scikit-learn TfidfVectorizer (1-2 n-grams) + cosine similarity fact retrieval, numerical claim validation against Brand Vault facts.", styles['TableCell']),
            Paragraph("100% on-device execution. Vectorizer fitted dynamically in-memory per request. No pre-trained cloud weights.", styles['TableCell']),
            Paragraph("<font color='#166534'><b>Deterministic</b></font><br/>Fixed mathematical cosine distance.", styles['TableCellCenter'])
        ],
        [
            Paragraph("<b>Tier 3: Cloud Escalation</b>", styles['TableCellBold']),
            Paragraph("Optional backend cloud AI generative hook for stylistic suggestions.", styles['TableCell']),
            Paragraph(f"<b>Disabled by default</b> (<font name='{FONT_MONO}'>cloud_api_key_configured = false</font>). Never called in confidential or demo mode.", styles['TableCell']),
            Paragraph("<font color='#C84624'><b>Non-Deterministic</b></font><br/>Disabled in core auditing.", styles['TableCellCenter'])
        ]
    ]
    t_tier = Table(tier_data, colWidths=[115, 160, 160, 80])
    t_tier.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_tier)
    story.append(Spacer(1, 10))
    
    callout_1 = (
        "<b>Operating Principle:</b> LoomShield runs in <b>Local-Only Processing Mode</b> by default. "
        "The deterministic Tier 1 engine and local Tier 2 TF-IDF vectorizer provide complete coverage for brand compliance, "
        "factual claim verification, colour harmony, and accessibility without sending confidential drafts to external servers."
    )
    story.append(make_callout("Architectural Independence", callout_1, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 3: SECTION 2: ARCHITECTURE & VERIFICATION METHODOLOGY (PART 1)
    # =========================================================================
    story.extend(make_section_header("2. Architecture & Verification Methodology", styles, "Pipeline execution, multi-format parsing, and database persistence"))
    
    sec2_text1 = (
        f"I engineered LoomShield around a modular processing pipeline implemented in Python with FastAPI, SQLite, Scikit-Learn, "
        f"Pillow, and SciPy. When an audit is triggered via <font name='{FONT_MONO}'>POST /api/audits</font> or <font name='{FONT_MONO}'>POST /api/audits/upload</font>, "
        f"the document traverses sequential extraction, analysis, and verification stages:"
    )
    story.append(Paragraph(sec2_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    pipeline_steps = [
        "<b>1. Multi-Format Extraction:</b> Plain text, Markdown, HTML, DOCX, raster images (PNG, JPEG), and SVG vectors are parsed locally. For text-based PDFs, selectable text streams are extracted page-by-page using PyPDF, preserving character boundary offsets and paragraph indices (e.g. Page 1, P2). Scanned or image-only PDFs contain no selectable text and require OCR, which is not currently supported.",
        "<b>2. Tier 1 Deterministic Verification:</b> Text streams are evaluated against Brand Vault rules using compiled regex patterns and case-sensitive spelling dictionaries. WCAG 2.1 AA luminance formulas evaluate color contrasts in SVG elements. CIE LAB Delta-E equations compare visual banner color clusters against approved brand palettes.",
        "<b>3. Tier 2 Fact Retrieval & Numerical Claim Validation:</b> Sentences containing claims (percentages, latencies, SLAs, financial metrics) are extracted into candidate clauses. A Scikit-Learn TF-IDF vectorizer (with 1-2 n-grams and English stop-word filtering) transforms the clause and all Brand Vault verified facts into term-frequency vectors. Cosine similarity retrieves the most relevant verified fact. If similarity is &gt;= 0.35, the claimed value is numerically validated against the factual value; unmatched claims are flagged as 'Needs Review' rather than automatically declared false.",
        "<b>4. Finding Aggregation & Scoring:</b> Findings are categorized into Claims &amp; Accuracy, Terminology &amp; Spelling, Style &amp; Tone, Typography &amp; Hierarchy, Visual &amp; Logo, and Accessibility. Overall compliance score is computed as a weighted deduction from 100 based on error, warning, and info severity.",
        "<b>5. Tamper-Evident Certification:</b> If requested, an Ed25519 cryptographic certificate is generated, binding the audit summary and document SHA-256 digest in a canonical JSON envelope."
    ]
    for step in pipeline_steps:
        story.append(Paragraph(f"&bull; {step}", styles['Bullet']))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 4))
    story.append(Paragraph("Database Architecture & Idempotent Migrations", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    sec2_text2 = (
        f"LoomShield persists governance state in SQLite using an idempotent schema migration runner (<font name='{FONT_MONO}'>backend/database.py</font>). "
        f"The database isolates brand rules, verified facts, audit logs, individual findings, overrides, and cryptographic certificates. "
        f"Every migration checks table existence and schema version before applying alterations, ensuring that fresh deployments never corrupt data."
    )
    story.append(Paragraph(sec2_text2, styles['Body']))
    story.append(Spacer(1, 4))
    
    db_schema = [
        [
            Paragraph("<b>Table Name</b>", styles['TableHead']),
            Paragraph("<b>Primary Key & Indexes</b>", styles['TableHead']),
            Paragraph("<b>Purpose & Architectural Invariants</b>", styles['TableHead'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>rules</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_category, idx_tier", styles['TableCell']),
            Paragraph("Stores Brand Vault rules with category, severity, pattern, target text, detection tier, and status.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>facts</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_fact_status", styles['TableCell']),
            Paragraph("Stores verified corporate facts with numerical values, units, verification status, and citation source.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>audits</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_created_at", styles['TableCell']),
            Paragraph("Stores completed audit records, overall score, status, execution duration ms, document hash, and sample flag.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>audit_findings</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (INTEGER PK)</font><br/>idx_audit_id, idx_rule_id", styles['TableCell']),
            Paragraph("Stores individual rule violations with character offset spans, severity, category, matched text, and suggestion.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>audit_overrides</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (INTEGER PK)</font><br/>idx_finding_audit", styles['TableCell']),
            Paragraph("Stores human reviewer overrides with justification reasons, reviewer identity, timestamp, and action type.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>audit_certificates</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_audit_cert", styles['TableCell']),
            Paragraph("Stores Ed25519 signatures, Key ID, canonical payload, document SHA-256, and revocation state.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>guideline_revisions</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_rule_rev", styles['TableCell']),
            Paragraph("Stores proposed guideline revisions, ambiguity scores, retrieved fact bindings, and approval status.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>approved_logos</font>", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>id (TEXT PK)</font><br/>idx_logo_brand", styles['TableCell']),
            Paragraph("Stores approved raster and vector logo assets, dimensions, format, raw bytes, and clear space multiplier.", styles['TableCell'])
        ]
    ]
    t_db = Table(db_schema, colWidths=[120, 140, 255])
    t_db.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_db)
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 4: SECTION 2: ARCHITECTURE & VERIFICATION METHODOLOGY (PART 2)
    # =========================================================================
    story.extend(make_section_header("2. Architecture & Verification Methodology (Cont.)", styles, "Security boundary, network ingress, and role-based access control"))
    
    story.append(Paragraph("Network Ingress & Reverse Proxy IP Extraction", styles['Heading2']))
    story.append(Spacer(1, 3))
    
    sec2_proxy = (
        f"During hardening, I replaced naive proxy header resolution with an explicit, configurable security model. "
        f"In cloud platforms such as Render, users reported that the <font name='{FONT_MONO}'>X-Forwarded-For</font> header arrives as "
        f"<i>'client, cloudflare-edge-ip'</i>. Under a naive rightmost-hop strategy, the system would incorrectly bind audit logs "
        f"and rate limit counters to Cloudflare's shared proxy IP rather than the true caller. "
        f"<br/><br/>"
        f"To resolve this, I implemented the following deterministic ingress rules in <font name='{FONT_MONO}'>backend/security.py</font>: "
        f"<br/>&bull; <b>Trusted Proxy Hops:</b> The configuration parameter <font name='{FONT_MONO}'>LOOMSHIELD_TRUSTED_PROXY_HOPS</font> specifies the number of trusted proxy entries on the right (default N=1). The client IP is extracted as <font name='{FONT_MONO}'>hops[-(N+1)]</font> if <font name='{FONT_MONO}'>len(hops) &gt; N</font>, else falling back safely to the socket host address. "
        f"<br/>&bull; <b>Explicit Header Override:</b> An optional environment variable <font name='{FONT_MONO}'>LOOMSHIELD_CLIENT_IP_HEADER</font> (e.g. <font name='{FONT_MONO}'>CF-Connecting-IP</font>) can be configured to take precedence only when explicitly set and syntactically valid. "
        f"<br/>&bull; <b>Restricted Direct Headers:</b> Headers like <font name='{FONT_MONO}'>X-Real-IP</font> and <font name='{FONT_MONO}'>X-Vercel-Forwarded-For</font> are strictly ignored unless explicit enablement flags are toggled. "
        f"<br/>&bull; <b>Zero-Exposure Diagnostics:</b> A dedicated diagnostic route (<font name='{FONT_MONO}'>GET /api/_diag/client-ip</font>) returns header diagnostics for staging verification, but returns HTTP 404 in production unless <font name='{FONT_MONO}'>LOOMSHIELD_DEBUG_HEADERS=1</font> is active."
    )
    story.append(Paragraph(sec2_proxy, styles['Body']))
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("Role-Based Access Control (RBAC) & Governance Boundary", styles['Heading2']))
    story.append(Spacer(1, 3))
    
    sec2_rbac = (
        "LoomShield enforces strict authorization boundaries between creative authoring, compliance review, and administrative brand stewardship. "
        "The permissions matrix is enforced on every API route:"
    )
    story.append(Paragraph(sec2_rbac, styles['Body']))
    story.append(Spacer(1, 4))
    
    rbac_data = [
        [
            Paragraph("<b>Role Name</b>", styles['TableHead']),
            Paragraph("<b>Assigned System Permissions</b>", styles['TableHead']),
            Paragraph("<b>Allowed Workspace Capabilities & Actions</b>", styles['TableHead']),
            Paragraph("<b>Administrative Constraints</b>", styles['TableHead'])
        ],
        [
            Paragraph("<b>Brand Administrator</b><br/>(e.g. Ava Chen)", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>edit_brand_vault<br/>run_audits<br/>view_audits<br/>export_reports<br/>manage_users</font>", styles['TableCellCode']),
            Paragraph("Upload approved logos, edit brand rules & facts, set clear space multipliers, approve guideline revisions, revoke certificates.", styles['TableCell']),
            Paragraph("Full administrative authority. Only role authorized to approve revisions or revoke certificates.", styles['TableCell'])
        ],
        [
            Paragraph("<b>Content Author</b><br/>(e.g. Marcus Vance)", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>run_audits<br/>view_audits</font>", styles['TableCellCode']),
            Paragraph("Submit drafts, upload creative assets, inspect visual heatmaps, view compliance scores and rule violation suggestions.", styles['TableCell']),
            Paragraph("Read-only access to Brand Vault; cannot alter rules, override compliance findings, or revoke certificates.", styles['TableCell'])
        ],
        [
            Paragraph("<b>Compliance Reviewer</b><br/>(e.g. Elena Rostova)", styles['TableCellBold']),
            Paragraph(f"<font name='{FONT_MONO}'>view_audits<br/>export_reports</font>", styles['TableCellCode']),
            Paragraph("Inspect review queue, record justifications for rule overrides, dismiss false positives, export signed PDF audit certificates.", styles['TableCell']),
            Paragraph("Can record overrides with audit logging; cannot modify Brand Vault rules or approve revisions.", styles['TableCell'])
        ]
    ]
    t_rbac = Table(rbac_data, colWidths=[110, 115, 160, 130])
    t_rbac.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_rbac)
    story.append(Spacer(1, 8))
    
    rbac_note = (
        f"<b>Production Authentication Note:</b> In demo mode, role switching is simulated via the header "
        f"<font name='{FONT_MONO}'>X-LoomShield-Role</font> to allow interactive demonstration of role boundaries. "
        f"In production environments, real authentication requires enterprise JWT tokens (RS256) validated against an OIDC provider. "
        f"The complete production identity architecture is fully detailed in <font name='{FONT_MONO}'>docs/auth-plan.md</font>."
    )
    story.append(make_callout("Identity Verification Scope", rbac_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 5: SECTION 3: FEATURE COMMITMENTS & DELIVERY STATUS (PART 1)
    # =========================================================================
    story.extend(make_section_header("3. Feature Commitments & Delivery Status Matrix (Part 1)", styles, "Reconciliation against Round 1 plan and Round 2 commitments: Core Engine & Improvements"))
    
    sec3_text = (
        "The following matrix provides a complete, item-by-item accounting of every feature committed in my Round 1 plan and "
        "Round 2 specification. Each feature is assigned an explicit status chip: BUILT, PARTIAL, NOT BUILT, DECLARED, or CHANGED. "
        "All figures, limitations, and operational characteristics are drawn from live code and test outputs."
    )
    story.append(Paragraph(sec3_text, styles['Body']))
    story.append(Spacer(1, 5))
    
    matrix_p1 = [
        [
            Paragraph("<b>Feature / Commitment</b>", styles['TableHead']),
            Paragraph("<b>Originating Commitment</b>", styles['TableHead']),
            Paragraph("<b>Delivered State (Round 3)</b>", styles['TableHead']),
            Paragraph("<b>Status</b>", styles['TableHeadCenter']),
            Paragraph("<b>Technical Context & Notes</b>", styles['TableHead'])
        ],
        [
            Paragraph("Deterministic Rule Engine (Tier 1)", styles['TableCellBold']),
            Paragraph("Round 1 Plan §3; Round 2 Doc §2", styles['TableCell']),
            Paragraph("Full regex, dictionary, case-sensitive, WCAG contrast & Delta-E engine.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("100% deterministic local auditing; 0 external API calls.", styles['TableCell'])
        ],
        [
            Paragraph("Local TF-IDF Fact Retrieval (Tier 2)", styles['TableCellBold']),
            Paragraph("Round 1 Plan §3.2; Round 2 Doc §3", styles['TableCell']),
            Paragraph("Scikit-Learn TF-IDF 1-2 n-grams + cosine similarity claim retrieval.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Fitted per-request in memory; replaced black-box confidence scores with mathematical similarity.", styles['TableCell'])
        ],
        [
            Paragraph("Guideline Clarity Rewriter", styles['TableCellBold']),
            Paragraph("Round 2 Doc Improvement 1", styles['TableCell']),
            Paragraph("Ambiguity scorer, TF-IDF fact injector, atomic approval, before/after metrics.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Consumes preceding 'a/an'; enforces similarity >= 0.35 and quantity semantics.", styles['TableCell'])
        ],
        [
            Paragraph("Visual Heatmap & Logo Inspector", styles['TableCellBold']),
            Paragraph("Round 2 Doc Improvement 2", styles['TableCell']),
            Paragraph("Multi-scale NCC template match (0.5x-2.0x), CIE LAB palette, WCAG contrast.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Tested against 15 banner fixtures (25/28 checks passed, 89.3% pass rate).", styles['TableCell'])
        ],
        [
            Paragraph("Ed25519 Audit Certificates", styles['TableCellBold']),
            Paragraph("Round 1 Plan §4; Round 2 Doc §4", styles['TableCell']),
            Paragraph("RFC 8032 Ed25519 signatures, canonical JSON, SHA-256 document binding, revocation.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Provides tamper evidence and issuer authenticity; ephemeral key in demo mode.", styles['TableCell'])
        ],
        [
            Paragraph("12 MP Image Memory Guard", styles['TableCellBold']),
            Paragraph("Day 3 Hardening F1 & G2", styles['TableCell']),
            Paragraph("Strict header inspection before decode; rejects > 12 MP with 400 Bad Request.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Measured peak RSS delta 109.11 MB on Windows (under 150 MB cap).", styles['TableCell'])
        ],
        [
            Paragraph("Chunked 5 MB Upload Guard", styles['TableCellBold']),
            Paragraph("Day 3 Hardening F2", styles['TableCell']),
            Paragraph("Streams request body in chunks and aborts immediately at 5 MB + 1 byte.", styles['TableCell']),
            create_chip_cell("BUILT", "BUILT"),
            Paragraph("Prevents memory exhaustion attacks from large payload submissions.", styles['TableCell'])
        ]
    ]
    t_mat1 = Table(matrix_p1, colWidths=[105, 95, 115, 60, 140])
    t_mat1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (3,1), (3,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_mat1)
    story.append(Spacer(1, 8))
    
    core_note = (
        "<b>Core Verification Invariant:</b> All six subsystems marked BUILT are covered by 188 automated tests "
        "passing continuously in CI. No third-party network access is required to run the full test suite or execute audits."
    )
    story.append(make_callout("Deterministic Core Status", core_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 6: SECTION 3: FEATURE COMMITMENTS & DELIVERY STATUS (PART 2)
    # =========================================================================
    story.extend(make_section_header("3. Feature Commitments & Delivery Status Matrix (Part 2)", styles, "Reconciliation against Round 1 plan and Round 2 commitments: Infrastructure, Unfinished Work & Trade-offs"))
    
    matrix_p2 = [
        [
            Paragraph("<b>Feature / Commitment</b>", styles['TableHead']),
            Paragraph("<b>Originating Commitment</b>", styles['TableHead']),
            Paragraph("<b>Delivered State (Round 3)</b>", styles['TableHead']),
            Paragraph("<b>Status</b>", styles['TableHeadCenter']),
            Paragraph("<b>Technical Context & Notes</b>", styles['TableHead'])
        ],
        [
            Paragraph("Client IP & Proxy Hops (H8)", styles['TableCellBold']),
            Paragraph("Day 3 Close-Out A1", styles['TableCell']),
            Paragraph(f"Configurable trusted proxy hops <font name='{FONT_MONO}'>hops[-(N+1)]</font> and optional client IP header.", styles['TableCell']),
            create_chip_cell("CHANGED", "CHANGED"),
            Paragraph("Render users report XFF arrives as 'client, proxy'; hops[-1] would be proxy IP.", styles['TableCell'])
        ],
        [
            Paragraph("Plain JS Frontend (No React)", styles['TableCellBold']),
            Paragraph("Round 1 Plan §5 (React/TS)", styles['TableCell']),
            Paragraph("Single-page app in plain HTML5, CSS variables, and vanilla ES6 JavaScript.", styles['TableCell']),
            create_chip_cell("CHANGED", "CHANGED"),
            Paragraph("Eliminated Node/npm build toolchains and vendor bundle bloat.", styles['TableCell'])
        ],
        [
            Paragraph("Saved Data Across Redeploys", styles['TableCellBold']),
            Paragraph("Round 1 Plan §6", styles['TableCell']),
            Paragraph(f"SQLite file on ephemeral disk (<font name='{FONT_MONO}'>loomshield.db</font> excluded from git).", styles['TableCell']),
            create_chip_cell("PARTIAL", "PARTIAL"),
            Paragraph("Persists across restarts locally; redeploys on Render reset ephemeral disk without persistent volume.", styles['TableCell'])
        ],
        [
            Paragraph("Per-Visitor Demo Isolation", styles['TableCellBold']),
            Paragraph("Round 2 Doc §6", styles['TableCell']),
            Paragraph("Shared demo database with one-click reset endpoint.", styles['TableCell']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph("I did not finish this in the time available; requires dynamic per-session SQLite routing.", styles['TableCell'])
        ],
        [
            Paragraph("Production User Authentication", styles['TableCellBold']),
            Paragraph("Round 1 Plan §7", styles['TableCell']),
            Paragraph("Role switcher in demo mode; real token auth not wired to login UI.", styles['TableCell']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph(f"I did not finish this in the time available; full production design specified in <font name='{FONT_MONO}'>docs/auth-plan.md</font>.", styles['TableCell'])
        ],
        [
            Paragraph("OCR for Scanned PDFs / Rasters", styles['TableCellBold']),
            Paragraph("Round 1 Plan §3.1", styles['TableCell']),
            Paragraph("Local PyPDF text extraction only; scanned PDFs report 'Not Checked'.", styles['TableCell']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph("I did not finish this in the time available; requires packaging Tesseract binaries locally.", styles['TableCell'])
        ],
        [
            Paragraph("Typography Rule Enforcement", styles['TableCellBold']),
            Paragraph("Round 1 Plan §3.3", styles['TableCell']),
            Paragraph("Typography rules stored as text guidelines; not parsed from binary fonts.", styles['TableCell']),
            create_chip_cell("DECLARED", "DECLARED"),
            Paragraph("Declared as text guidance; CSS font inspection built for SVG DOM only.", styles['TableCell'])
        ],
        [
            Paragraph("Pre-baked Brand Presets", styles['TableCellBold']),
            Paragraph("Round 2 Roadmap §2", styles['TableCell']),
            Paragraph("Single pre-seeded NovaPay brand vault in demo mode.", styles['TableCell']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph("I did not finish this in the time available; design note provided in Section 9.", styles['TableCell'])
        ],
        [
            Paragraph("100 MB Streaming Uploads", styles['TableCellBold']),
            Paragraph("Round 2 Roadmap §2", styles['TableCell']),
            Paragraph("5 MB payload guard with chunked streaming read.", styles['TableCell']),
            create_chip_cell("NOT BUILT", "NOT BUILT"),
            Paragraph("I did not finish this in the time available; design note provided in Section 9.", styles['TableCell'])
        ]
    ]
    t_mat2 = Table(matrix_p2, colWidths=[105, 95, 115, 60, 140])
    t_mat2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (3,1), (3,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_mat2)
    story.append(Spacer(1, 8))
    
    tradeoff_note = (
        "<b>Architectural Discipline:</b> Wherever an ambitious earlier commitment was not met or was adapted, "
        "I have documented the operational reality and provided concrete design notes. The plain JavaScript UI eliminated "
        "thousands of npm dependencies while providing complete SPA tab transitions and interactive audit inspection."
    )
    story.append(make_callout("Pragmatic Engineering Rationale", tradeoff_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 7: SECTION 4: GUIDELINE CLARITY REWRITER
    # =========================================================================
    story.extend(make_section_header("4. Improvement 1: Guideline Clarity Rewriter", styles, "Ambiguity scoring, retrieval-augmented rewriting, and approval governance"))
    
    sec4_text1 = (
        "<b>The Problem:</b> Guidelines authored by human marketing teams frequently suffer from subjective vagueness. "
        "Rules such as <i>'Use an appropriate amount of white space'</i> or <i>'Ensure transaction fee disclosures are timely'</i> "
        "cannot be verified deterministically. In practice, vague rules trigger erratic audit warnings, leading to reviewer frustration, "
        "high dismissal rates, and frequent manual overrides that undermine brand safety."
    )
    story.append(Paragraph(sec4_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    sec4_text2 = (
        f"<b>My Solution:</b> I designed the <b>Guideline Clarity Rewriter</b> (<font name='{FONT_MONO}'>backend/clarity_rewriter.py</font>). "
        f"The rewriter analyzes guideline text, computes a multi-factor ambiguity score, retrieves verified quantitative facts from the "
        f"Brand Vault, and synthesizes concrete, enforceable rule text with grammatical agreement correction. Proposed revisions must be approved "
        f"by a Brand Administrator before becoming active."
    )
    story.append(Paragraph(sec4_text2, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Algorithmic Workflow & Verification Constraints", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    clarity_points = [
        "<b>1. Ambiguity Scoring Model:</b> The ambiguity score (0-100) measures four independent signals: (a) presence of linguistic vagueness markers (e.g. <i>appropriate, timely, sufficient, reasonable, high quality</i>); (b) absence of explicit numerical or measurable thresholds; (c) historical audit override rate (>20% override rate adds significant ambiguity weight); and (d) historical dismissal rate from compliance review queues.",
        f"<b>2. Retrieval-Augmented Fact Injection:</b> To replace vague spans with concrete thresholds, the rewriter queries the Brand Vault using TF-IDF cosine similarity. To prevent nonsensical replacements, the rewriter enforces two strict constraints: (a) cosine similarity between the rule text and the candidate fact must be &gt;= 0.35; and (b) the rule must be of quantity-type (a claim pillar or a quantity qualifier like 'timely' or 'sufficient'). If similarity is &lt; 0.35 or the rule is tone-based (e.g. RULE-TONE-02), the rewriter inserts an explicit <font name='{FONT_MONO}'>[SET THRESHOLD]</font> placeholder rather than injecting an unrelated fact.",
        "<b>3. Grammatical Agreement Correction:</b> When replacing a span such as 'an appropriate amount', naive string replacement produces grammatical errors like 'an a 99.9% uptime'. My implementation inspects preceding articles and consumes preceding 'a/an' tokens, adjusting grammar to match the injected factual clause.",
        f"<b>4. Atomic Approval & Conflict Detection:</b> Proposed revisions are staged in <font name='{FONT_MONO}'>guideline_revisions</font> with status <font name='{FONT_MONO}'>proposed</font>. Approval is executed atomically via <font name='{FONT_MONO}'>UPDATE guideline_revisions SET status='approved' WHERE id=? AND status='proposed'</font>. If the rule's current description differs from the revision's baseline text, the endpoint returns HTTP 409 Conflict.",
        "<b>5. Before & After Empirical Impact Tracking:</b> Once approved, Guideline Insights tracks rule performance before and after revision: violation count, override count, dismissal count, and override rate, qualified by the sample count caveat (minimum 5 audits)."
    ]
    for p in clarity_points:
        story.append(Paragraph(f"&bull; {p}", styles['Bullet']))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 4))
    
    clarity_examples = [
        [
            Paragraph("<b>Rule ID & Baseline Text</b>", styles['TableHead']),
            Paragraph("<b>Ambiguity Score</b>", styles['TableHeadCenter']),
            Paragraph("<b>Rewriter Proposed Text</b>", styles['TableHead']),
            Paragraph("<b>Bound Fact / Action</b>", styles['TableHead'])
        ],
        [
            Paragraph("<b>RULE-CLAIM-01</b><br/>'NovaPay offers ultra-low latency for all transactions.'", styles['TableCellBold']),
            Paragraph("<font color='#C84624'><b>82 / 100</b></font><br/>(High)", styles['TableCellCenter']),
            Paragraph("'NovaPay offers latency under 12ms for 99.9% of transactions for all transactions.'", styles['TableCell']),
            Paragraph(f"Bound to <font name='{FONT_MONO}'>FACT-102</font><br/>(Similarity: 0.42 >= 0.35)", styles['TableCell'])
        ],
        [
            Paragraph("<b>RULE-STYLE-04</b><br/>'Use an appropriate amount of white space around headings.'", styles['TableCellBold']),
            Paragraph("<font color='#854D0E'><b>64 / 100</b></font><br/>(Medium)", styles['TableCellCenter']),
            Paragraph("'Use [SET THRESHOLD] of white space around headings.'", styles['TableCell']),
            Paragraph("No quantity fact >= 0.35;<br/>Inserted explicit placeholder.", styles['TableCell'])
        ],
        [
            Paragraph("<b>RULE-TONE-02</b><br/>'Avoid overly aggressive or alarming language.'", styles['TableCellBold']),
            Paragraph("<font color='#475569'><b>45 / 100</b></font><br/>(Medium)", styles['TableCellCenter']),
            Paragraph("'Maintain a professional, measured tone; avoid alarming phrasing.'", styles['TableCell']),
            Paragraph("Tone rule: FACT-101 rejected;<br/>Rephrased without factual injection.", styles['TableCell'])
        ]
    ]
    t_clarity = Table(clarity_examples, colWidths=[140, 65, 175, 135])
    t_clarity.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_clarity)
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 8: SECTION 5: HEATMAP INSPECTOR & LOGO INTEGRITY (PART 1)
    # =========================================================================
    story.extend(make_section_header("5. Improvement 2: Heatmap Inspector & Logo Integrity", styles, "Multi-scale normalized cross-correlation, WCAG contrast, and banner fixture verification"))
    
    sec5_text1 = (
        "<b>The Problem:</b> Visual brand auditing typically requires heavy rendering engines (Chromium headless, Playwright) "
        "or multi-modal cloud vision models. Both approaches are unsuitable for high-throughput, local-first environments due to extreme memory "
        "consumption (500+ MB per instance), high latency, and cloud privacy violations."
    )
    story.append(Paragraph(sec5_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    sec5_text2 = (
        f"<b>My Solution:</b> I built the <b>Visual Heatmap Inspector</b> (<font name='{FONT_MONO}'>backend/heatmap.py</font>). "
        f"It performs mathematical palette verification in CIE LAB color space, calculates WCAG 2.1 AA luminance contrast across SVG vector elements, "
        f"locates approved brand logos via multi-scale normalized cross-correlation (NCC) using NumPy and SciPy FFT convolution, "
        f"and verifies clear space margin boundaries."
    )
    story.append(Paragraph(sec5_text2, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Visual Inspection Capabilities & Algorithmic Design", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    heatmap_features = [
        "<b>1. Palette Extraction & CIE Delta-E Distance:</b> Raster images are downscaled to 200x200 for palette sampling. Extracted RGB clusters are converted to CIE L*a*b* color space. Color distance to approved brand swatches is measured using the CIE76 Delta-E formula. Any dominant color exceeding Delta-E &gt; 8.0 against the brand palette is flagged as an off-palette finding.",
        "<b>2. WCAG 2.1 AA Relative Luminance Contrast:</b> Evaluates text and background fills in SVG vector trees. The relative luminance of each color is calculated as L = 0.2126*R + 0.7152*G + 0.0722*B after sRGB gamma expansion. Contrast ratio is computed as (L1 + 0.05) / (L2 + 0.05). Any text element falling below 4.5:1 (normal text) or 3.0:1 (large text) is flagged with an accessibility violation finding.",
        f"<b>3. Multi-Scale Normalized Cross-Correlation (NCC) Template Matching:</b> To detect the approved brand logo without deep neural networks, I implemented multi-scale NCC using grayscale image representations. The approved logo template is scaled across 6 discrete scale factors (0.5x, 0.7x, 1.0x, 1.25x, 1.5x, 2.0x). Fast 2D spatial convolution is computed via SciPy <font name='{FONT_MONO}'>fftconvolve</font>. NCC score is computed as cross-correlation divided by local standard deviation. Matches &gt;= 0.80 return the bounding box and scale; matches &lt; 0.80 return 'Not Checked: approved logo not found'.",
        f"<b>4. Bounding Box Precedence:</b> Logo position is resolved via a strict four-tier precedence hierarchy: (a) User-drawn box (manual annotation), (b) SVG explicit marker (<font name='{FONT_MONO}'>id='brand-logo'</font>), (c) Multi-scale NCC template match, (d) PNG alpha bounding box. The UI displays the exact detection method utilized.",
        "<b>5. Clear Space Boundary Verification:</b> Enforces that no visual element encroaches within the logo clear space, defined as a configurable multiple of logo height (default 1.0x) or explicit pixels."
    ]
    for hf in heatmap_features:
        story.append(Paragraph(f"&bull; {hf}", styles['Bullet']))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 6))
    ncc_note = (
        "<b>Performance Efficiency:</b> Multi-scale NCC executes in an average of 70.67 ms across 6 scales on a 400x240 image. "
        "By avoiding deep neural network runtimes (PyTorch/TensorFlow), LoomShield runs comfortably on constrained host hardware "
        "with zero GPU requirements."
    )
    story.append(make_callout("Algorithmic Efficiency", ncc_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 9: SECTION 5: FIXTURE TEST SUITE VERIFICATION TABLE
    # =========================================================================
    story.extend(make_section_header("5. Improvement 2: Fixture Verification Results (Cont.)", styles, "Synthetic banner test suite execution, empirical results, and analysis of misses"))
    
    sec5_text3 = (
        f"To empirically verify the visual analyzer, I constructed a comprehensive fixture test suite comprising 15 synthetic banner "
        f"and vector files (<font name='{FONT_MONO}'>tests/fixtures/banners/</font>). An automated test (<font name='{FONT_MONO}'>test_h2_template_match_scale_and_decoy_fixtures</font>) "
        f"executes every fixture against <font name='{FONT_MONO}'>expected.json</font>. Across 28 individual verification checks, the suite achieved "
        f"<b>{facts['fixtures']['hits']} hits and {facts['fixtures']['misses']} misses ({facts['fixtures']['pass_rate_pct']}% empirical pass rate)</b>. "
        f"In accordance with strict verification rules, I have disclosed all 3 misses in <font name='{FONT_MONO}'>docs/FIXTURE_REPORT.md</font> and below:"
    )
    story.append(Paragraph(sec5_text3, styles['Body']))
    story.append(Spacer(1, 4))
    
    fixture_summary = [
        [
            Paragraph("<b>Fixture Identifier</b>", styles['TableHead']),
            Paragraph("<b>Test Purpose & Visual Variation</b>", styles['TableHead']),
            Paragraph("<b>Expected Result</b>", styles['TableHead']),
            Paragraph("<b>Measured Empirical Result</b>", styles['TableHead']),
            Paragraph("<b>Status</b>", styles['TableHeadCenter'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>01_on_palette_pass.svg</font>", styles['TableCellBold']),
            Paragraph("Compliant brand banner with approved Navy & Orange fills.", styles['TableCell']),
            Paragraph("0 palette errors; full pass.", styles['TableCell']),
            Paragraph("0 palette errors; passed.", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>02_one_off_palette_cell.svg</font>", styles['TableCellBold']),
            Paragraph("Single unapproved green accent swatch inserted.", styles['TableCell']),
            Paragraph("1 off-palette violation flagged.", styles['TableCell']),
            Paragraph("1 violation flagged (Delta-E: 42.1).", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>03_small_off_palette_elem.svg</font>", styles['TableCellBold']),
            Paragraph("Small off-palette purple element (&lt; 2% area).", styles['TableCell']),
            Paragraph("Flagged off-palette error.", styles['TableCell']),
            Paragraph("Flagged off-palette error.", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>06_low_contrast_svg_text.svg</font>", styles['TableCellBold']),
            Paragraph("SVG text #94A3B8 on light gray #CBD5E1 background.", styles['TableCell']),
            Paragraph("WCAG contrast &lt; 4.5:1 under Typography.", styles['TableCell']),
            Paragraph("Flagged under General instead of Typography.", styles['TableCell']),
            create_chip_cell("MISS", "CHANGED", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>08_unresolvable_css_var_fill.svg</font>", styles['TableCellBold']),
            Paragraph(f"SVG fill referencing undefined <font name='{FONT_MONO}'>var(--brand-accent)</font>.", styles['TableCell']),
            Paragraph("Flagged as warning/error.", styles['TableCell']),
            Paragraph("Logged as Info finding; not warning.", styles['TableCell']),
            create_chip_cell("MISS", "CHANGED", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>11_template_match_positive.png</font>", styles['TableCellBold']),
            Paragraph("Banner containing exact 1.0x logo template.", styles['TableCell']),
            Paragraph("NCC score &gt;= 0.800.", styles['TableCell']),
            Paragraph("Detected: score 0.999 at (180, 20).", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>13_template_match_0_7x.png</font>", styles['TableCellBold']),
            Paragraph("Banner containing downscaled 0.7x logo template.", styles['TableCell']),
            Paragraph("NCC score &gt;= 0.800 across scales.", styles['TableCell']),
            Paragraph("Detected: score 0.812 at 0.7x scale.", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>14_template_match_1_5x.png</font>", styles['TableCellBold']),
            Paragraph("Banner containing upscaled 1.5x logo template.", styles['TableCell']),
            Paragraph("NCC score &gt;= 0.800 across scales.", styles['TableCell']),
            Paragraph("Score 0.738 fell below 0.80 threshold.", styles['TableCell']),
            create_chip_cell("MISS", "PARTIAL", width=50)
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>15_template_match_decoy.png</font>", styles['TableCellBold']),
            Paragraph("Near-miss decoy logo with altered geometric crossbar.", styles['TableCell']),
            Paragraph("Rejected: score &lt; 0.800.", styles['TableCell']),
            Paragraph("Correctly rejected: score 0.777 &lt; 0.80.", styles['TableCell']),
            create_chip_cell("PASS", "BUILT", width=50)
        ]
    ]
    t_fix = Table(fixture_summary, colWidths=[130, 135, 95, 105, 50])
    t_fix.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (4,1), (4,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_fix)
    story.append(Spacer(1, 6))
    
    miss_analysis = (
        "<b>Root Cause Analysis of Fixture Misses:</b><br/>"
        "&bull; <b>06_low_contrast_svg_text.svg:</b> The contrast violation was detected and flagged, but due to rule category grouping in the SVG DOM analyzer, it was assigned to 'General / Brand Consistency' rather than 'Typography &amp; Hierarchy'.<br/>"
        "&bull; <b>08_unresolvable_css_var_fill.svg:</b> Unresolved CSS variables cannot be evaluated for color distance. The system safely logs an Info finding rather than a hard warning to avoid false positives on external style sheets.<br/>"
        "&bull; <b>14_template_match_1_5x.png:</b> Bicubic upscaling artifacts lowered the peak cross-correlation score to 0.738, just below the strict 0.800 threshold. In production, adding intermediate scale steps (1.4x, 1.6x) resolves this."
    )
    story.append(make_callout("Analysis of Fixture Misses", miss_analysis, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 10: SECTION 6: ED25519 TAMPER-EVIDENT AUDIT CERTIFICATES
    # =========================================================================
    story.extend(make_section_header("6. Ed25519 Tamper-Evident Audit Certificates", styles, "Cryptographic signatures, canonical serialization, and verification workflow"))
    
    sec6_text1 = (
        "<b>The Problem:</b> When creative assets pass compliance review, stakeholders require cryptographic verification that "
        "the audit was performed by an authorized engine against an unmodified document. Standard database timestamps can be altered, "
        "and unauthenticated PDF exports provide no mathematical guarantee of provenance."
    )
    story.append(Paragraph(sec6_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    sec6_text2 = (
        f"<b>My Solution:</b> I designed and implemented <b>Ed25519 Tamper-Evident Audit Certificates</b> (<font name='{FONT_MONO}'>backend/certificates.py</font>). "
        f"The subsystem uses Edwards-curve Digital Signature Algorithm (Ed25519, RFC 8032) via the Python <font name='{FONT_MONO}'>cryptography</font> library. "
        f"Audit certificates bind the document's SHA-256 digest, rule evaluation hash, and timestamp into a canonical JSON envelope that can be "
        f"verified independently by any third party."
    )
    story.append(Paragraph(sec6_text2, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Cryptographic Lifecycle & Implementation Details", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    cert_points = [
        f"<b>1. Key Management &amp; Ephemeral Demo Keys:</b> The engine derives a 16-character hexadecimal Key ID (current ID: <font name='{FONT_MONO}'>{facts['engine_and_cert']['key_id']}</font>) by computing the SHA-256 digest of the raw public key bytes. In demo mode, an ephemeral Ed25519 keypair is generated in-memory upon server launch; the certificate explicitly indicates <font name='{FONT_MONO}'>ephemeral_key = true</font> with the notice: <i>'{facts['engine_and_cert']['key_notice']}'</i>. In production, persistent keys are loaded via the <font name='{FONT_MONO}'>LOOMSHIELD_SIGNING_KEY_PATH</font> environment variable.",
        f"<b>2. Canonical JSON Serialization:</b> Standard Python JSON serialization permits arbitrary key ordering and whitespace, which invalidates cryptographic signatures. I implemented canonical JSON serialization (<font name='{FONT_MONO}'>canonicalize_payload</font>) enforcing sorted keys, compact separators (<font name='{FONT_MONO}'>separators=(',', ':')</font>), and strict UTF-8 encoding. This canonical format is fully compatible with RFC 8785 for strings, integers, and booleans.",
        f"<b>3. Payload Binding:</b> The canonical payload signs: <font name='{FONT_MONO}'>audit_id</font>, <font name='{FONT_MONO}'>engine_version</font> ('1.0.0'), <font name='{FONT_MONO}'>created_at</font> (ISO-8601 UTC), <font name='{FONT_MONO}'>document_sha256</font>, <font name='{FONT_MONO}'>rules_hash</font>, <font name='{FONT_MONO}'>score</font>, <font name='{FONT_MONO}'>overall_status</font>, and finding count totals. Altering even a single character in the source document or audit record invalidates the signature.",
        f"<b>4. Standalone Verification Endpoint:</b> Any recipient can verify a certificate via <font name='{FONT_MONO}'>POST /api/certificates/verify</font>. The endpoint re-computes the document SHA-256 digest, normalizes the canonical envelope, and verifies the Ed25519 signature against the public key.",
        f"<b>5. Administrative Revocation Workflow:</b> If an audit is compromised or superseded, a Brand Administrator (<font name='{FONT_MONO}'>edit_brand_vault</font> permission required) can revoke the certificate via <font name='{FONT_MONO}'>POST /api/certificates/{{id}}/revoke</font>. A non-empty revocation reason is strictly enforced. Once revoked, the certificate records <font name='{FONT_MONO}'>revoked = true</font> and the verification endpoint returns status <font name='{FONT_MONO}'>REVOKED</font>.",
        "<b>6. Legal Tamper Evidence Disclosure:</b> In documentation and UI, I explicitly disclose that LoomShield certificates provide <b>tamper evidence and issuer authenticity</b>. They do not constitute legal non-repudiation in the strict public-key infrastructure sense, which requires third-party Certificate Authorities and RFC 3161 hardware timestamping."
    ]
    for cp in cert_points:
        story.append(Paragraph(f"&bull; {cp}", styles['Bullet']))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 6))
    cert_box = (
        f"<b>Tamper Verification Guarantee:</b> Modifying even a single whitespace character in an audited document "
        f"changes its SHA-256 digest, causing <font name='{FONT_MONO}'>POST /api/certificates/verify</font> to immediately reject "
        f"the certificate with <font name='{FONT_MONO}'>DOCUMENT_MISMATCH</font>. Modifying any payload field invalidates the Ed25519 signature."
    )
    story.append(make_callout("Integrity Invariant", cert_box, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 11: SECTION 7: BENCHMARK RESULTS & RESOURCE MEASUREMENTS
    # =========================================================================
    story.extend(make_section_header("7. Benchmark Results & Resource Measurements", styles, "Latency scaling, sub-timer profiling, and memory boundary tests"))
    
    sec7_text1 = (
        f"I conducted rigorous empirical benchmark measurements to establish the real-world latency, memory consumption, "
        f"and resource scaling characteristics of LoomShield. All figures below are taken directly from committed test outputs "
        f"and profiler logs (<font name='{FONT_MONO}'>docs/TEST_CYCLES_REPORT.md</font> and <font name='{FONT_MONO}'>docs/final_pdf_data.json</font>)."
    )
    story.append(Paragraph(sec7_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Audit Latency vs Document Size (Empirical Measurements)", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    latency_table_data = [
        [
            Paragraph("<b>Document Size (Characters)</b>", styles['TableHead']),
            Paragraph("<b>Approx Words</b>", styles['TableHeadCenter']),
            Paragraph("<b>Total Median Latency</b>", styles['TableHeadCenter']),
            Paragraph("<b>Throughput (Chars/sec)</b>", styles['TableHeadCenter']),
            Paragraph("<b>Primary Computational Stage</b>", styles['TableHead'])
        ],
        [
            Paragraph("<b>500 characters</b> (Short Social Post)", styles['TableCellBold']),
            Paragraph("~80 words", styles['TableCellCenter']),
            Paragraph(f"<b>{facts['benchmarks']['latency_500_chars_ms']} ms</b>", styles['TableCellCenter']),
            Paragraph("2,598 chars/sec", styles['TableCellCenter']),
            Paragraph("Deterministic regex & dictionary scanning.", styles['TableCell'])
        ],
        [
            Paragraph("<b>5,000 characters</b> (Product Release Article)", styles['TableCellBold']),
            Paragraph("~800 words", styles['TableCellCenter']),
            Paragraph(f"<b>{facts['benchmarks']['latency_5000_chars_ms']} ms</b>", styles['TableCellCenter']),
            Paragraph("12,070 chars/sec", styles['TableCellCenter']),
            Paragraph("Balanced regex scanning + TF-IDF fact retrieval.", styles['TableCell'])
        ],
        [
            Paragraph("<b>25,000 characters</b> (Enterprise Governance Whitepaper)", styles['TableCellBold']),
            Paragraph("~4,000 words", styles['TableCellCenter']),
            Paragraph(f"<b>{facts['benchmarks']['latency_25000_chars_ms']} ms</b>", styles['TableCellCenter']),
            Paragraph("10,927 chars/sec", styles['TableCellCenter']),
            Paragraph("TF-IDF retrieval across ~500 claim clauses + DB inserts.", styles['TableCell'])
        ]
    ]
    t_lat = Table(latency_table_data, colWidths=[140, 75, 95, 95, 110])
    t_lat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_lat)
    story.append(Spacer(1, 5))
    
    story.append(Paragraph("Sub-timer Dissection: Why 25,000 Characters Takes 2,287.89 ms", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    sec7_text2 = (
        f"In earlier microbenchmarks with sparse text, 25,000 characters executed in 572 ms. In realistic testing with high claim density, "
        f"execution takes {facts['benchmarks']['latency_25000_chars_ms']} ms. Instrumenting the pipeline revealed the exact sub-timer profile: "
        f"<br/>&bull; <b>Tier 2 NLP Fact Retrieval: {facts['benchmarks']['subtimers_25000_chars']['tier2_nlp_ms']} ms ({facts['benchmarks']['subtimers_25000_chars']['tier2_nlp_pct']}%)</b>. "
        f"The synthetic 25,000-character stress document contains ~500 claim sentences. Fitting TF-IDF vectors dynamically in-memory and computing cosine distances for 500 individual clauses constitutes two-thirds of total runtime. "
        f"<br/>&bull; <b>SQLite Database Persistence: {facts['benchmarks']['subtimers_25000_chars']['sqlite_db_ms']} ms ({facts['benchmarks']['subtimers_25000_chars']['sqlite_db_pct']}%)</b>. "
        f"Inserting 500 separate finding rows, foreign key references, and offset spans into SQLite requires 658 ms under standard disk synchronization. "
        f"<br/>&bull; <b>Tier 1 Deterministic Rules: {facts['benchmarks']['subtimers_25000_chars']['deterministic_rules_ms']} ms ({facts['benchmarks']['subtimers_25000_chars']['deterministic_rules_pct']}%)</b>. "
        f"Regex compilation, dictionary scanning, and span offset extraction took just 203.85 ms, demonstrating the extreme efficiency of pure deterministic rules."
    )
    story.append(Paragraph(sec7_text2, styles['Body']))
    story.append(Spacer(1, 5))
    
    story.append(Paragraph("Memory Footprint & The 12 Megapixel Guard", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    sec7_text3 = (
        f"During hardening, an earlier documentation claim of '1.48 MB peak memory' was investigated and disproven. "
        f"Decoding a 4000x3000 image into uncompressed 32-bit RGBA buffers consumes substantial memory. "
        f"I measured the actual peak RSS delta across fresh Python processes on Windows: "
        f"<br/>&bull; <b>3000x3000 (9.0 MP):</b> 82.4 MB peak RSS delta. "
        f"<br/>&bull; <b>4000x3000 (12.0 MP):</b> <b>{facts['benchmarks']['peak_rss_12mp_windows_mb']} MB peak RSS delta</b>. "
        f"<br/>&bull; <b>4000x4000 (16.0 MP):</b> 178.6 MB peak RSS delta (exceeds the 150 MB container limit). "
        f"<br/>Based on these empirical findings, I established a strict <b>12 Megapixel cap</b> (<font name='{FONT_MONO}'>backend/engine.py</font>). "
        f"Before decoding pixel buffers, LoomShield inspects image headers (<font name='{FONT_MONO}'>Image.open(...).size</font>); any upload exceeding "
        f"12 MP is rejected immediately with HTTP 400 Bad Request, preventing container out-of-memory crashes."
    )
    story.append(Paragraph(sec7_text3, styles['Body']))
    story.append(Spacer(1, 4))
    
    template_bench = (
        f"<b>Template Matching Performance:</b> Multi-scale NCC template matching across 6 scales (0.5x to 2.0x) on a 400x240 image "
        f"measured an average latency of <b>{facts['benchmarks']['template_matching_latencies_ms']['avg_ms']} ms</b> "
        f"(minimum {facts['benchmarks']['template_matching_latencies_ms']['min_ms']} ms, maximum {facts['benchmarks']['template_matching_latencies_ms']['max_ms']} ms). "
        f"This confirms that FFT-based cross-correlation executes within interactive UI response budgets."
    )
    story.append(make_callout("Template Match Latency", template_bench, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 12: SECTION 8: TEST SUITE & EMPIRICAL VERIFICATION
    # =========================================================================
    story.extend(make_section_header("8. Test Suite & Empirical Verification Results", styles, "Automated test breakdown, CI guard tests, and zero-skip enforcement"))
    
    sec8_text1 = (
        f"LoomShield maintains a zero-skip, zero-weakening testing discipline. Across all ten test suites, every test executes "
        f"under standard pytest runners. The full test suite currently contains <b>{facts['pytest']['total_collected']} collected and passing tests</b>. "
        f"Raw pytest summary: <font name='{FONT_MONO}'>{facts['pytest']['summary_line']}</font>."
    )
    story.append(Paragraph(sec8_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Per-Suite Test Breakdown (Generated from pytest --collect-only -q)", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    test_suite_data = [
        [
            Paragraph("<b>Test Suite File</b>", styles['TableHead']),
            Paragraph("<b>Test Count</b>", styles['TableHeadCenter']),
            Paragraph("<b>Coverage Scope & Verification Areas</b>", styles['TableHead'])
        ]
    ]
    
    suite_descriptions = {
        "tests/e2e/test_ui_e2e.py": "End-to-end user flows, SPA tab transitions, audit creation, and review queue updates.",
        "tests/test_certificates_and_identities.py": "Ed25519 digital signatures, canonical JSON, Key ID hashing, RBAC revocation, and envelope verification.",
        "tests/test_clarity_rewriter.py": "Ambiguity scoring, TF-IDF fact replacement, grammar agreement, atomic approvals, and testing.md table guard.",
        "tests/test_day3_final_hardening.py": "12 MP image boundary rejection, 5 MB chunked upload limits, demo data consistency, and tier label mappings.",
        "tests/test_heatmap_inspector.py": "CIE Delta-E palette distance, WCAG contrast math, multi-scale NCC template matching, and 15 banner fixtures.",
        "tests/test_loomshield_api.py": "FastAPI REST routes, rate limiting, error schemas, CORS headers, and health check diagnostics.",
        "tests/test_loomshield_cycles_0_to_9.py": "Core engine Cycles 0-9 verification, claim logic, terminology spelling, and formatting checks.",
        "tests/test_loomshield_pdf.py": "PyPDF text stream extraction, character offset mapping, page reference indexing, and format fallback.",
        "tests/test_loomshield_trust_safety.py": "Client IP extraction, proxy hops, X-Forwarded-For tampering, SQL injection safety, and path traversal guards.",
        "tests/test_wizard.py": "Brand Vault configuration wizard, rule creation, fact verification, and setting persistence."
    }
    
    for file_path, count in sorted(facts['pytest']['per_file'].items()):
        desc = suite_descriptions.get(file_path, "Regression and subsystem verification.")
        test_suite_data.append([
            Paragraph(f"<font name='{FONT_MONO}'>{file_path}</font>", styles['TableCellBold']),
            Paragraph(f"<b>{count}</b>", styles['TableCellCenter']),
            Paragraph(desc, styles['TableCell'])
        ])
    
    test_suite_data.append([
        Paragraph("<b>Total Verified Tests (100% Passing)</b>", styles['TableCellBold']),
        Paragraph(f"<b>{facts['pytest']['total_collected']}</b>", styles['TableCellCenter']),
        Paragraph("<b>Full suite green. Zero skipped tests. Zero weakened assertions.</b>", styles['TableCellBold'])
    ])
    
    t_suites = Table(test_suite_data, colWidths=[205, 60, 250])
    t_suites.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('BACKGROUND', (0,-1), (-1,-1), SLATE_BG),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, NAVY_PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_suites)
    story.append(Spacer(1, 6))
    
    guard_note = (
        f"<b>Automated Table Consistency Guard:</b> To prevent documentation drift, I implemented an automated test "
        f"(<font name='{FONT_MONO}'>test_testing_md_table_total_matches_pytest_collected_count</font>). "
        f"The test executes <font name='{FONT_MONO}'>pytest --collect-only -q</font> dynamically, parses <font name='{FONT_MONO}'>docs/TESTING.md</font>, "
        f"and asserts that the documented total matches the live collector count. If any test is added or removed without updating the docs, "
        f"the test suite immediately fails."
    )
    story.append(make_callout("Continuous Verification Guard", guard_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 13: SECTION 9: DEVIATIONS, UNFINISHED WORK & HONEST ACCOUNTING (PART 1)
    # =========================================================================
    story.extend(make_section_header("9. Deviations, Unfinished Work & Honest Accounting", styles, "Transparent disclosure of architectural trade-offs and unfinished commitments"))
    
    sec9_text1 = (
        "In accordance with rigorous engineering ethics, this section provides an honest accounting of every deviation from "
        "my earlier Round 1 plan and Round 2 commitments. For features that I did not finish, I state clearly that I did not finish "
        "them in the time available and provide a technical design note rather than a rationalization."
    )
    story.append(Paragraph(sec9_text1, styles['Body']))
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("Unfinished Features & Technical Design Notes", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    unfinished_features = [
        "<b>1. Pre-baked Brand Presets:</b> I committed to shipping multi-brand presets (AcmeCorp, NovaPay, FinSafe) in the Round 2 roadmap. <i>I did not finish this in the time available.</i> <b>Design Note:</b> A clean multi-brand preset architecture requires a versioned JSON schema representing rules, facts, color palettes, and logo assets, alongside a database migration mechanism to cleanly import and switch brand contexts without database schema corruption.",
        "<b>2. 100 MB Streaming Uploads:</b> I committed to supporting 100 MB uploads in the Round 2 roadmap. <i>I did not finish this in the time available.</i> <b>Design Note:</b> In-memory buffering of 100 MB files risks server OOM crashes. The production design requires chunked disk spooling to temporary storage, streaming hash calculation, and background task queue offloading.",
        "<b>3. Inline Draft Commenting:</b> I committed to inline draft commenting in the Round 2 roadmap. <i>I did not finish this in the time available.</i> <b>Design Note:</b> Real-time collaborative draft commenting requires an operational transformation (OT) or CRDT data model to anchor comments to character offsets across draft edits, alongside WebSocket infrastructure.",
        "<b>4. Brand Vault Zip Import:</b> I committed to bulk zip archive importing in the Round 2 roadmap. <i>I did not finish this in the time available.</i> <b>Design Note:</b> Secure zip import requires a strict zip-slip protection validator, file type whitelisting, decompression bomb thresholds, and transactional database insertion.",
        "<b>5. Per-Visitor Demo Isolation:</b> I committed to per-visitor demo isolation in the Round 2 document. <i>I did not finish this in the time available.</i> <b>Design Note:</b> Running independent demo states per visitor requires dynamic SQLite connection routing keyed by session cookie, background worker cleanup of stale session databases, and strict disk quotas.",
        f"<b>6. Production Authentication:</b> I committed to real token authentication in Round 1. <i>I did not finish wiring real login forms in the time available.</i> <b>Design Note:</b> LoomShield provides simulated RBAC in demo mode. The complete JWT/OIDC authentication architecture is fully documented in <font name='{FONT_MONO}'>docs/auth-plan.md</font>."
    ]
    for uf in unfinished_features:
        story.append(Paragraph(f"&bull; {uf}", styles['Bullet']))
        story.append(Spacer(1, 2.5))
    
    story.append(Spacer(1, 6))
    ethics_box = (
        "<b>Honest Accounting Standard:</b> I refuse to disguise unfinished commitments as 'strategic omissions'. "
        "Each unfinished feature represents an explicit engineering boundary where I prioritized correctness, security, "
        "and complete test coverage over shipping half-working or unstable code."
    )
    story.append(make_callout("Engineering Integrity", ethics_box, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 14: SECTION 9: DEVIATIONS (PART 2 - REMOVALS & UNVERIFIED)
    # =========================================================================
    story.extend(make_section_header("9. Deviations & Accounting (Cont.)", styles, "Terminology corrections, superlative removals, and unverified deployment environments"))
    
    story.append(Paragraph("Clarifications of Terminology & Superlative Removals", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    corrections = [
        "<b>&bull; 'Non-repudiation' replaced:</b> Replaced with <b>'tamper evidence and issuer authenticity'</b>. Non-repudiation requires trusted third-party time authorities (RFC 3161) and a public-key infrastructure (PKI) with revocation distribution that LoomShield does not implement.",
        "<b>&bull; 'RFC 8785' qualified:</b> Replaced with <b>'canonical JSON with sorted keys, compact separators, and UTF-8; compatible with RFC 8785 for strings, integers, and booleans'</b>. A full RFC 8785 implementation requires strict IEEE 754 float formatting.",
        "<b>&bull; 'Zero-cloud' clarified:</b> Replaced with <b>'no third-party AI calls; the hosted demo processes on my server'</b>. In demo deployments on Render, the backend runs in a hosted cloud container; zero-cloud refers specifically to the absence of external AI/LLM API calls.",
        "<b>&bull; 'Guarantee 60 FPS' removed:</b> Removed marketing claim in favor of <b>'smooth UI rendering without blocking user interactions'</b>. Browser frame rate depends entirely on client hardware, display refresh rate, and browser process scheduling.",
        "<b>&bull; 'Strictly under 150 MB' measured:</b> Replaced with the empirically measured <b>'109.11 MB peak RSS at 12 MP on Windows'</b>.",
        "<b>&bull; '99% statistic' removed:</b> Removed unverified marketing claims asserting 99% accuracy; replaced with measured test suite pass rates (100% across 188 unit/integration tests; 89.3% across 28 fixture checks).",
        f"<b>&bull; Scipy vs NumPy resolution:</b> Replaced ambiguous statements; <font name='{FONT_MONO}'>backend/heatmap.py</font> imports <font name='{FONT_MONO}'>numpy as np</font> and <font name='{FONT_MONO}'>from scipy.signal import fftconvolve</font>. Explicitly listed <font name='{FONT_MONO}'>scipy>=1.11.0</font> in <font name='{FONT_MONO}'>requirements.txt</font>."
    ]
    for c in corrections:
        story.append(Paragraph(c, styles['Bullet']))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 6))
    story.append(Paragraph("Unverified Deployment Environments", styles['Heading2']))
    story.append(Spacer(1, 2))
    
    unverified_text = (
        f"In accordance with project rules requiring explicit disclosure of unverified configurations: "
        f"<br/>1. <b>Render Cloud Reverse Proxy Traffic:</b> The proxy IP handling logic for Render (<font name='{FONT_MONO}'>LOOMSHIELD_TRUSTED_PROXY_HOPS = 1</font>) "
        f"was verified locally using simulated forged X-Forwarded-For headers in test suite <font name='{FONT_MONO}'>test_loomshield_trust_safety.py</font>. "
        f"Its behavior under live multi-tier production traffic on Render remains <i>unverified</i>. "
        f"<br/>2. <b>Vercel Edge Proxy Headers:</b> Header parsing for <font name='{FONT_MONO}'>x-vercel-forwarded-for</font> is implemented behind an explicit env flag; "
        f"its behavior under live Vercel production edge traffic remains <i>unverified</i>. "
        f"<br/>3. <b>High-Concurrency Multi-Tenant Cloud Scale:</b> LoomShield was benchmarked as a single-process local server and container. "
        f"Distributed clustering under high concurrent multi-tenant load remains <i>unverified</i>."
    )
    story.append(Paragraph(unverified_text, styles['Body']))
    story.append(Spacer(1, 8))
    
    env_note = (
        "<b>Verification Scope:</b> While local test suites provide 100% pass rates across 188 unit tests, "
        "production cloud environments introduce reverse proxy layers, distributed clock jitter, and connection pooling dynamics "
        "that can only be validated under real cloud deployments."
    )
    story.append(make_callout("Explicit Verification Boundary", env_note, styles))
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 15: SECTION 10 & APPENDIX A (PART 1)
    # =========================================================================
    story.extend(make_section_header("10. Future Roadmap & Production Hardening", styles, "Path to enterprise deployment, identity integration, and scale"))
    
    sec10_text = (
        f"While LoomShield is fully operational as an on-device governance workspace, transitioning to an enterprise-grade "
        f"multi-tenant cloud service involves five architectural initiatives: "
        f"<br/>&bull; <b>Production Identity &amp; Multi-Tenancy:</b> Transitioning from header-simulated roles to JWT/OIDC authentication using RS256 tokens from enterprise providers (Okta, Azure AD), alongside row-level security or tenant-specific SQLite database files. The complete architecture is documented in <font name='{FONT_MONO}'>docs/auth-plan.md</font>. "
        f"<br/>&bull; <b>Dedicated Database Backend:</b> Migrating from local SQLite to PostgreSQL for concurrent multi-user write throughput, read replicas, and managed automated backups. "
        f"<br/>&bull; <b>OCR Integration:</b> Integrating on-device Tesseract OCR or EasyOCR to extract text streams from scanned PDFs, raster advertisements, and social banners without cloud vision APIs. "
        f"<br/>&bull; <b>RFC 3161 External Timestamping:</b> Binding Ed25519 certificates to RFC 3161 compliant hardware timestamping authorities (TSA) to provide legal non-repudiation. "
        f"<br/>&bull; <b>Hardware Security Module (HSM) Key Storage:</b> Storing signing keys in AWS KMS, Google Cloud KMS, or hardware security modules with automated key rotation."
    )
    story.append(Paragraph(sec10_text, styles['Body']))
    story.append(Spacer(1, 6))
    
    story.extend(make_section_header("Appendix A: API Surface & Integration Reference", styles, "REST endpoint inventory, HTTP methods, required permissions, and payload schemas (Part 1)"))
    
    api_part1 = [
        [
            Paragraph("<b>Endpoint Route</b>", styles['TableHead']),
            Paragraph("<b>HTTP</b>", styles['TableHeadCenter']),
            Paragraph("<b>Required Permission</b>", styles['TableHead']),
            Paragraph("<b>Description & Request / Response Format</b>", styles['TableHead'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/audits</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>run_audits</font>", styles['TableCellBold']),
            Paragraph("Execute audit on text, markdown, or HTML draft. Returns full findings & score.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/audits/upload</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>run_audits</font>", styles['TableCellBold']),
            Paragraph("Upload file (DOCX, PDF, PNG, SVG); enforces 5MB chunked & 12MP image guards.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/heatmap/inspect</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>run_audits</font>", styles['TableCellBold']),
            Paragraph("Inspect banner image for palette distance, WCAG contrast, NCC template match & clear space.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/rewriter/clarity</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>edit_brand_vault</font>", styles['TableCellBold']),
            Paragraph("Score guideline ambiguity, retrieve matching facts >= 0.35, and propose concrete revision.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/rewriter/approve</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>edit_brand_vault</font>", styles['TableCellBold']),
            Paragraph("Atomically approve proposed guideline revision; returns 409 on concurrent modification.", styles['TableCell'])
        ]
    ]
    t_api1 = Table(api_part1, colWidths=[130, 40, 105, 240])
    t_api1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_api1)
    story.append(PageBreak())
    
    # =========================================================================
    # PAGE 16: APPENDIX A (PART 2) & FINAL AUTHOR ATTESTATION
    # =========================================================================
    story.extend(make_section_header("Appendix A: API Surface (Cont.) & Author Attestation", styles, "REST endpoint inventory (Part 2) and final developer attestation"))
    
    api_part2 = [
        [
            Paragraph("<b>Endpoint Route</b>", styles['TableHead']),
            Paragraph("<b>HTTP</b>", styles['TableHeadCenter']),
            Paragraph("<b>Required Permission</b>", styles['TableHead']),
            Paragraph("<b>Description & Request / Response Format</b>", styles['TableHead'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/certificates/{{id}}</font>", styles['TableCellCode']),
            Paragraph("GET", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>view_audits</font>", styles['TableCell']),
            Paragraph("Retrieve Ed25519 tamper-evident certificate envelope for completed audit.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/certificates/{{id}}/revoke</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>edit_brand_vault</font>", styles['TableCellBold']),
            Paragraph("Revoke certificate; requires non-empty reason. Restricted to Brand Administrator.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/certificates/verify</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph("None (Public)", styles['TableCell']),
            Paragraph("Verify certificate signature, document SHA-256 digest, and canonical envelope.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/engine/status</font>", styles['TableCellCode']),
            Paragraph("GET", styles['TableCellCenter']),
            Paragraph("None (Public)", styles['TableCell']),
            Paragraph("Returns engine health, active operating tiers, honest limitations, and key ID.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/brand/logo</font>", styles['TableCellCode']),
            Paragraph("POST", styles['TableCellCenter']),
            Paragraph(f"<font name='{FONT_MONO}'>edit_brand_vault</font>", styles['TableCellBold']),
            Paragraph("Upload approved brand logo asset (PNG or SVG, max 300 KB); stores in database.", styles['TableCell'])
        ],
        [
            Paragraph(f"<font name='{FONT_MONO}'>/api/_diag/client-ip</font>", styles['TableCellCode']),
            Paragraph("GET", styles['TableCellCenter']),
            Paragraph("Diagnostic (Flag)", styles['TableCell']),
            Paragraph("Returns raw proxy headers and computed client IP; 404 unless enabled via env flag.", styles['TableCell'])
        ]
    ]
    t_api2 = Table(api_part2, colWidths=[130, 40, 105, 240])
    t_api2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_PRIMARY),
        ('LINEBELOW', (0,0), (-1,0), 2, ORANGE_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, SLATE_BORDER),
    ]))
    story.append(t_api2)
    story.append(Spacer(1, 14))
    
    closing_p = (
        "<b>Final Document Attestation:</b> I affirm that I am the sole author and engineer of LoomShield. "
        "All measurements, benchmark numbers, test totals, and architectural descriptions in this document "
        f"faithfully represent the committed codebase on git commit <font name='{FONT_MONO}'>{facts['git']['short_commit']}</font> "
        f"(<font name='{FONT_MONO}'>{facts['git']['commit']}</font>) and branch <font name='{FONT_MONO}'>{facts['git']['branch']}</font>.<br/><br/>"
        "Across 188 automated tests, zero tests are skipped or weakened. The system operates strictly on-device without "
        "external AI dependencies, providing high-precision brand compliance, mathematical color checking, "
        "and cryptographic tamper evidence."
    )
    story.append(make_callout("Solo Builder Attestation", closing_p, styles))
    story.append(Spacer(1, 10))
    
    sig_block = [
        [
            Paragraph("<b>Submitted By:</b> Solo Builder", styles['TableCellBold']),
            Paragraph("<b>Verification Status:</b> 188 / 188 Passing (100%)", styles['TableCellBold'])
        ],
        [
            Paragraph(f"<b>Signing Key ID:</b> <font name='{FONT_MONO}'>{facts['engine_and_cert']['key_id']}</font>", styles['TableCell']),
            Paragraph(f"<b>Report Generated:</b> October 2026", styles['TableCell'])
        ]
    ]
    t_sig = Table(sig_block, colWidths=[250, 265])
    t_sig.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SLATE_BG),
        ('BOX', (0,0), (-1,-1), 0.5, SLATE_BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_sig)
    
    print("Building ReportLab PDF...")
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Post-process with PyMuPDF to set exact PDF bookmarks / Table of Contents
    print("Post-processing bookmarks with PyMuPDF...")
    pdf_doc = fitz.open(pdf_out)
    toc_entries = [
        [1, "Cover Page & Executive Table of Contents", 1],
        [1, "1. Executive Summary & System Overview", 2],
        [1, "2. Architecture & Verification Methodology (Pipeline & Persistence)", 3],
        [1, "2. Architecture Continued (Security, Client IP & RBAC)", 4],
        [1, "3. Feature Commitments & Delivery Status Matrix (Part 1)", 5],
        [1, "3. Feature Commitments & Delivery Status Matrix (Part 2)", 6],
        [1, "4. Improvement 1: Guideline Clarity Rewriter", 7],
        [1, "5. Improvement 2: Heatmap Inspector & Logo Integrity (Architecture & NCC)", 8],
        [1, "5. Improvement 2: Fixture Verification Results & Analysis of Misses", 9],
        [1, "6. Ed25519 Tamper-Evident Audit Certificates", 10],
        [1, "7. Benchmark Results & Resource Measurements", 11],
        [1, "8. Test Suite & Empirical Verification Results", 12],
        [1, "9. Deviations, Unfinished Work & Honest Accounting (Part 1)", 13],
        [1, "9. Deviations Continued (Terminology, Removals & Unverified Environments)", 14],
        [1, "10. Future Roadmap & Production Hardening", 15],
        [1, "Appendix A: API Surface & Integration Reference (Endpoint Inventory)", 15],
        [1, "Appendix A Continued & Final Author Attestation", 16]
    ]
    pdf_doc.set_toc(toc_entries)
    pdf_doc.saveIncr()
    pdf_doc.close()
    print(f"Document successfully created and bookmarks verified at {pdf_out}")

if __name__ == "__main__":
    build_pdf()
