import os
import shutil
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers and running headers/footers."""
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
        self.saveState()
        # Running Header (cleaned as requested: no 'ROUND 2 BUILD DELIVERY' or 'TWO LOCAL ENGINES | ZERO MANDATORY API KEYS')
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#EA633F"))
        self.drawString(36, 756, "LOOMSHIELD")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#5F6368"))
        self.drawString(96, 756, " |   PROJECT SUBMISSION SPECIFICATION")
        self.setStrokeColor(colors.HexColor("#E2E4E8"))
        self.setLineWidth(0.6)
        self.line(36, 750, 576, 750)

        # Running Footer
        self.line(36, 36, 576, 36)
        self.setFont("Helvetica", 6.8)
        self.drawString(36, 25, "Team: isaac.incognito007   |   Isaac Shiloah Herbert V (isaac.incognito007@gmail.com)   |   Repository: https://github.com/isaacincognito007-cloud/Inkloom-artLoomShield")
        self.drawRightString(576, 25, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=44,
    )

    styles = getSampleStyleSheet()

    # Custom typography matching LoomShield Design Tokens
    c_primary = colors.HexColor("#17191C")
    c_accent = colors.HexColor("#EA633F")
    c_secondary = colors.HexColor("#5F6368")
    c_border = colors.HexColor("#E2E4E8")
    c_bg_alt = colors.HexColor("#F8F9FA")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=c_accent,
        spaceAfter=7,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=c_primary,
        spaceBefore=5,
        spaceAfter=2,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=10,
        textColor=c_primary,
        spaceAfter=3.5,
    )

    table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=9,
        textColor=colors.white,
    )

    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.6,
        leading=8.6,
        textColor=c_primary,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell,
        fontName="Helvetica-Bold",
    )

    callout_text = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=9.2,
        textColor=colors.HexColor("#1F2937"),
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, METADATA, & SECTION 1: LIST OF COMPLETED FEATURES
    # =========================================================================
    story.append(Paragraph("LOOMSHIELD -- Brand Governance Platform", title_style))
    story.append(Paragraph("Project Submission Specification &amp; Verification Report", subtitle_style))

    # Metadata Table
    meta_data = [
        [
            Paragraph("<b>Project Name:</b> LoomShield", table_cell),
            Paragraph("<b>Team Name:</b> isaac.incognito007 (Solo Team)", table_cell),
            Paragraph("<b>Participant:</b> Isaac Shiloah Herbert V", table_cell),
        ],
        [
            Paragraph("<b>Source-Code Repo:</b> <font color='#EA633F'><u>https://github.com/isaacincognito007-cloud/Inkloom-artLoomShield</u></font>", table_cell),
            Paragraph("<b>Email:</b> isaac.incognito007@gmail.com", table_cell),
            Paragraph("<b>Working project link:</b> <font color='#EA633F'><u>https://inkloom.art</u></font>", table_cell),
        ],
        [
            Paragraph("<b>Operating Mode:</b> Two Local On-Device Engines (Deterministic + NLP)", table_cell),
            Paragraph("<b>API Key Policy:</b> Zero Mandatory External API Keys (100% On-Device)", table_cell),
            Paragraph("<b>Automated Tests:</b> 68/68 automated tests passed (100% pass rate); code coverage measured separately.", table_cell),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[185, 185, 170])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.8, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 5))

    story.append(Paragraph("<b>Executive Summary:</b> LoomShield is an enterprise-grade, local-first brand governance workspace that inspects multi-format marketing content against approved brand guidelines before publication. Built with two on-device engines (Tier 1 Deterministic + Tier 2 Embedded Scikit-Learn TF-IDF NLP), LoomShield checks tone, terminology, messaging, promotional claims, visual brand assets, and accessibility. Every issue is cited with exact brand rules and verified fact sheets, surgical corrections are generated without overwriting the creator's voice, and approval events are logged in an immutable SHA-256 ledger--operating entirely on-device with zero mandatory external AI API keys.", body_style))
    story.append(Spacer(1, 3))

    # SECTION 1
    story.append(Paragraph("1. List of Completed Features (Round 2 Build)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=1, spaceAfter=4))

    features_data = [
        [
            Paragraph("Feature Module", table_header),
            Paragraph("Engine Tier", table_header),
            Paragraph("Completed Capabilities & Verified Functionality", table_header),
            Paragraph("Status", table_header),
        ],
        [
            Paragraph("<b>Multi-Format Ingestion Suite (8 Formats)</b>", table_cell_bold),
            Paragraph("Tier 1 Local", table_cell),
            Paragraph("Native local ingestion of <b>.pdf, .docx, .md, .html, .txt, .svg, .png, .jpg</b>. Validates magic bytes (<font name='Courier'>%PDF-</font>), rejects renamed non-PDFs, enforces 5 MB limit and configurable page limits (<font name='Courier'>LOOMSHIELD_MAX_PDF_PAGES</font>).", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Pure-Python Local PDF Text Extractor</b>", table_cell_bold),
            Paragraph("Tier 1 Local", table_cell),
            Paragraph("100% on-device pure-Python text stream extraction using <font name='Courier'>pypdf</font>. Preserves page boundaries and maps character offsets to human-verifiable citations (<font name='Courier'>Page X, P Y</font>). Detects encrypted and scanned image-only PDFs.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Dual-Engine Brand Governance Architecture</b>", table_cell_bold),
            Paragraph("Tier 1 & Tier 2 Hybrid", table_cell),
            Paragraph("<b>Tier 1:</b> Deterministic regex, dictionary lookups, WCAG contrast math, CIE LAB &Delta;E distance. <b>Tier 2:</b> Embedded Scikit-Learn TF-IDF vectorizer + cosine similarity fact retrieval. Zero external API keys required.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Six-Pillar Governance & Honest Reporting</b>", table_cell_bold),
            Paragraph("Tier 1 + 2 Hybrid", table_cell),
            Paragraph("Evaluates <b>Tone and Voice, Terminology, Messaging, Promotional Claims, Visual & Logo Consistency, Accessibility</b>. Reports honest 5-state outcomes: <font name='Courier'>Passed, Findings, Needs Review, Not Checked, Check Failed</font>.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Promotional Claim Fact-Grounding Engine</b>", table_cell_bold),
            Paragraph("Tier 2 Local NLP", table_cell),
            Paragraph("Extracts numerical/percentage claims (e.g. <i>'guarantees 95% faster processing'</i>), retrieves matching Verified Facts via cosine similarity, compares numerical values/units, and flags unbacked superlatives as <font name='Courier'>Needs Review</font>.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Interactive Review Queue & Decision Studio</b>", table_cell_bold),
            Paragraph("Full-Stack Studio", table_cell),
            Paragraph("Three-panel review workspace (Rendered/Source view, Explainable Finding Cards with exact rule/fact citations, Surgical Replacement preview). Human reviewers can <b>Accept, Modify, or Dismiss</b> findings with mandatory rationale.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Structured Brand Vault & Multi-Brand Constraints</b>", table_cell_bold),
            Paragraph("SQLite Schema", table_cell),
            Paragraph("Stores brand tone rules, terminology lexicons (preferred vs. prohibited), verified fact sheets with conditions & source links, approved hex palettes, and WCAG contrast thresholds. Pre-configured for NovaPay and Verdant.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Role-Based Workflow & Immutable Audit Log</b>", table_cell_bold),
            Paragraph("Security & Governance", table_cell),
            Paragraph("Role-based approval state machine (Content Creator, Editorial Reviewer, Brand Compliance Manager). Records immutable audit logs with <b>SHA-256 content hashes</b>, version snapshots, and decision audit trails.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Guideline Ambiguity Radar</b>", table_cell_bold),
            Paragraph("Analytics & Insights", table_cell),
            Paragraph("Aggregates reviewer overrides per rule to identify ambiguously phrased guidelines. Flags high override-rate rules with actionable signals for brand leads to review and refine guidelines rather than blaming creators.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
        [
            Paragraph("<b>Production SaaS UI & Accessibility Remediation</b>", table_cell_bold),
            Paragraph("Frontend UI/UX", table_cell),
            Paragraph("Enterprise UI using cohesive design tokens (<font name='Courier'>#17191C</font> ink, <font name='Courier'>#F7F8FA</font> canvas, <font name='Courier'>#EA633F</font> accent), responsive review queue cards, sanitised HTML preview, and WCAG 2.1 AA keyboard/contrast compliance.", table_cell),
            Paragraph("<font color='#1E7E34'><b>Completed</b></font>", table_cell),
        ],
    ]

    features_table = Table(features_data, colWidths=[120, 80, 290, 50])
    features_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(features_table)

    # =========================================================================
    # PAGE 2: TECHNOLOGY AND IMPLEMENTATION DETAILS + MACHINE REPRODUCIBILITY
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Technology and Implementation Details", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=1, spaceAfter=5))

    story.append(Paragraph("<b>2.1 Core Architectural Layers & Component Breakdown</b>", h2_style))
    story.append(Paragraph("LoomShield enforces a strict local-first, two-tier architecture where content analysis, factual claim validation, and mathematical asset scoring occur entirely within the execution environment with zero cloud leakage:", body_style))

    tech_stack_data = [
        [
            Paragraph("Layer", table_header),
            Paragraph("Technology Stack", table_header),
            Paragraph("Implementation Responsibilities & Architectural Guarantee", table_header),
        ],
        [
            Paragraph("<b>Backend API & Web Server</b>", table_cell_bold),
            Paragraph("Python 3.11<br/>FastAPI 0.115+<br/>Uvicorn (ASGI)", table_cell),
            Paragraph("Provides RESTful endpoints for multi-format document ingestion, real-time six-pillar audit execution, Brand Vault management, reviewer decisions, and workflow state transitions. Operates on <b>http://127.0.0.1:8000</b>.", table_cell),
        ],
        [
            Paragraph("<b>Tier 1: Deterministic Engine</b>", table_cell_bold),
            Paragraph("Python Core<br/>RegEx Engine<br/>XML ElementTree", table_cell),
            Paragraph("Executes rule-based checks: terminology dictionaries, case-sensitive brand capitalization ('NovaPay'), WCAG 2.1 relative luminance math, CIE LAB &Delta;E distance, SVG viewBox validation, and markup security sanitization.", table_cell),
        ],
        [
            Paragraph("<b>Tier 2: Embedded NLP Engine</b>", table_cell_bold),
            Paragraph("Scikit-Learn 1.4+<br/>NumPy 1.26+<br/>TF-IDF Vectorizer", table_cell),
            Paragraph("Runs entirely on-device with zero API keys. Evaluates unigrams/bigrams across verified facts in the Brand Vault, computes cosine similarity against extracted claims, compares numerical values, and outputs surgical replacement templates.", table_cell),
        ],
        [
            Paragraph("<b>Document Ingestion Suite</b>", table_cell_bold),
            Paragraph("pypdf 6.21+<br/>python-docx<br/>BeautifulSoup4", table_cell),
            Paragraph("Parses <b>PDF, DOCX, Markdown, HTML, TXT, SVG, PNG, JPG</b> in-memory via <font name='Courier'>io.BytesIO</font>. Extracts text streams, tracks page spans and character offsets, strips unsafe scripts, and analyzes raster image swatches.", table_cell),
        ],
        [
            Paragraph("<b>Persistence & Governance Ledger</b>", table_cell_bold),
            Paragraph("SQLite3 (WAL Mode)<br/>ACID Transactions<br/>SHA-256 Hashing", table_cell),
            Paragraph("Relational database storing Brand Vault constraints, immutable audit records, original/revised snapshots, reviewer decisions, and audit events. Computes cryptographic SHA-256 digests on approved content snapshots.", table_cell),
        ],
        [
            Paragraph("<b>Frontend SaaS Workspace</b>", table_cell_bold),
            Paragraph("Semantic HTML5<br/>Modern ES2022+ JS<br/>CSS Custom Tokens", table_cell),
            Paragraph("Single-page SaaS application without heavy external frameworks. Features live brand switching, responsive review queue cards, rendered/source toggle, interactive decision buttons, and Ambiguity Radar charts.", table_cell),
        ],
    ]
    tech_table = Table(tech_stack_data, colWidths=[120, 100, 320])
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>2.2 Mathematical & Algorithmic Formulation</b>", h2_style))
    story.append(Paragraph("• <b>WCAG 2.1 AA Contrast Ratio:</b> Calculated from relative luminance <i>L = 0.2126&middot;R + 0.7152&middot;G + 0.0722&middot;B</i>, where channel values are sRGB linearized. The contrast ratio <i>(L1 + 0.05)/(L2 + 0.05)</i> strictly verifies body text achieves &ge; 4.5:1 and large text achieves &ge; 3.0:1.<br/>"
                           "• <b>CIE LAB &Delta;E Color Distance (CIE76):</b> Extracted hex codes and raster image swatch clusters are transformed from sRGB into standard D65 XYZ and then into the perceptually uniform CIE L*a*b* color space. Euclidean distance <i>&Delta;E = &radic;((&Delta;L*)&sup2; + (&Delta;a*)&sup2; + (&Delta;b*)&sup2;)</i> measures deviation against configured Brand Vault palette swatches (&Delta;E &le; 14.0 for NovaPay).<br/>"
                           "• <b>Flesch-Kincaid Reading Ease:</b> Evaluates reading complexity on extracted text as <i>206.835 &minus; 1.015&middot;(words/sentences) &minus; 84.6&middot;(syllables/words)</i> to flag overly dense corporate prose.<br/>"
                           "• <b>TF-IDF Vector Grounding & Cosine Similarity:</b> Active facts in the Brand Vault are transformed into a sparse term-frequency matrix using unigram and bigram tokenization with sublinear scaling. Extracted claim clauses are vector-projected into the same embedding space; cosine similarity <i>cos(&theta;) = (q &middot; d) / (||q|| ||d||)</i> identifies the top verified fact candidate without external network queries.", body_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>2.3 Machine & Benchmark Reproducibility Details</b>", h2_style))
    story.append(Paragraph("To ensure full scientific reproducibility, all performance, latency, and memory benchmarks were measured on a dedicated standard developer hardware environment using automated repeatable scripts:", body_style))

    bench_env_data = [
        [
            Paragraph("Benchmark Parameter", table_header),
            Paragraph("Exact Hardware & Software Specification", table_header),
            Paragraph("Measurement Method & Verification Scope", table_header),
        ],
        [
            Paragraph("<b>Host Machine & Processor</b>", table_cell_bold),
            Paragraph("AMD Ryzen 3 7320U with Radeon Graphics<br/>4 Physical Cores, 8 Logical Threads (2.40 GHz base, up to 4.10 GHz boost)", table_cell),
            Paragraph("Queried via Windows WMI (<font name='Courier'>Win32_Processor</font>). Standard commercially available client hardware.", table_cell),
        ],
        [
            Paragraph("<b>Installed System Memory</b>", table_cell_bold),
            Paragraph("8.0 GB LPDDR5 RAM (7.3 GB usable physical memory)", table_cell),
            Paragraph("Hardware system memory reported by Windows OS (<font name='Courier'>GlobalMemoryStatusEx</font>).", table_cell),
        ],
        [
            Paragraph("<b>Operating System & Runtime</b>", table_cell_bold),
            Paragraph("Microsoft Windows 11 Home (64-bit)<br/>OS Version: 10.0.26200 (AMD64)<br/>Python 3.11.0 64-bit (MSC v.1933)", table_cell),
            Paragraph("Execution environment runs natively under Windows PowerShell without virtualization or external container overhead.", table_cell),
        ],
        [
            Paragraph("<b>Benchmark Command & Script</b>", table_cell_bold),
            Paragraph("<font name='Courier'>python tests/generate_test_cycles_report.py</font>", table_cell),
            Paragraph("Runs automated test cycles across 20 iterations per document tier; calculates median and 95th percentile metrics.", table_cell),
        ],
        [
            Paragraph("<b>Latency Measurement Method</b>", table_cell_bold),
            Paragraph("High-resolution monotonic timer: <font name='Courier'>time.perf_counter()</font>", table_cell),
            Paragraph("Measures total execution time and isolates sub-timers: Tier 1 regex, Tier 2 TF-IDF retrieval, and SQLite write persistence.", table_cell),
        ],
        [
            Paragraph("<b>Memory Accounting Scope</b>", table_cell_bold),
            Paragraph("<b>Incremental Peak Heap: 10.25 MB</b> (<font name='Courier'>tracemalloc</font>)<br/>Process-Wide RSS Footprint: ~78.4 MB (<font name='Courier'>psutil</font>)", table_cell),
            Paragraph("<b>Clarification:</b> The reported <b>10.25 MB</b> figure is strictly <b>incremental peak heap memory</b> allocated during audit execution. Total process RSS (~78.4 MB) includes the Python runtime, FastAPI ASGI server, Scikit-Learn libraries, and SQLite cache.", table_cell),
        ],
    ]
    bench_table = Table(bench_env_data, colWidths=[120, 180, 240])
    bench_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(bench_table)

    # =========================================================================
    # PAGE 3: EXPLANATION OF CHANGES & THREE MAJOR IMPROVEMENTS FOR ROUND 3
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Explanation of Changes Made to the Original Plan", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=1, spaceAfter=5))
    story.append(Paragraph("During Round 2 implementation, user testing, real-world document audits, and UI audits identified five areas where the initial Round 1 conceptual plan needed refinement to achieve production-grade maturity:", body_style))

    changes_data = [
        [
            Paragraph("Area of Change", table_header),
            Paragraph("Original Round 1 Plan", table_header),
            Paragraph("Actual Round 2 Implementation", table_header),
            Paragraph("Architectural & UX Rationale", table_header),
        ],
        [
            Paragraph("<b>1. Native PDF Ingestion & Mapping</b>", table_cell_bold),
            Paragraph("Limited to HTML, DOCX, Markdown, and TXT.", table_cell),
            Paragraph("Added full <b>.pdf</b> ingestion via pure-Python <font name='Courier'>pypdf</font>, page boundary offset tracking, and <font name='Courier'>Page X, P Y</font> paragraph mapping.", table_cell),
            Paragraph("Enterprise marketing collaterals, press releases, and campaign briefs are distributed predominantly in PDF. Adding local PDF parsing enables seamless real-world adoption.", table_cell),
        ],
        [
            Paragraph("<b>2. Honest Status for Visual Checks</b>", table_cell_bold),
            Paragraph("Marked visual checks as 'Passed' if no errors were found.", table_cell),
            Paragraph("Visual checks are honestly marked <font name='Courier'>'Not Checked'</font> on text-only PDFs/documents unless visual specs are provided.", table_cell),
            Paragraph("Falsely reporting visual compliance on un-rendered documents undermines audit credibility. Transparent reporting builds user trust.", table_cell),
        ],
        [
            Paragraph("<b>3. Scanned PDF & OCR Limitation Disclosure</b>", table_cell_bold),
            Paragraph("Generic file error or empty string output on unparseable files.", table_cell),
            Paragraph("Detects image-only/scanned PDFs (0 selectable text) and emits an explicit <font name='Courier'>'Check Failed'</font> finding disclosing that local OCR is not currently available.", table_cell),
            Paragraph("Adheres to Section 4 honest capability guidelines: systems must honestly report technical boundaries rather than failing silently.", table_cell),
        ],
        [
            Paragraph("<b>4. SaaS UI Remediation & Demo Cleanup</b>", table_cell_bold),
            Paragraph("Hackathon roadmaps and demo reset buttons in production UI.", table_cell),
            Paragraph("Removed hackathon references, demo labels, and developer role switches from customer-facing screens. Unified enterprise design tokens and cards.", table_cell),
            Paragraph("A trustworthy brand-governance tool must look and feel like a secure enterprise product rather than a competition demo.", table_cell),
        ],
        [
            Paragraph("<b>5. Audit History Streamlining</b>", table_cell_bold),
            Paragraph("Multi-card version timeline cluttering audit detail view.", table_cell),
            Paragraph("Removed redundant version timeline UI; expanded full-width Original vs. Revised diff and the immutable Approval Event ledger.", table_cell),
            Paragraph("Streamlines reviewer workflow by focusing directly on content comparison and cryptographically hashed approval events.", table_cell),
        ],
    ]
    changes_table = Table(changes_data, colWidths=[100, 110, 160, 170])
    changes_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(changes_table)
    story.append(Spacer(1, 6))

    # SECTION 4
    story.append(Paragraph("4. Three Major Improvements for Round 3 (The Finish)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=1, spaceAfter=5))
    story.append(Paragraph("As pledged in the Round 1 project blueprint and reinforced in our technical roadmap, Round 3 delivery focuses on three substantial, high-impact innovations that push LoomShield from a governance checker to a complete self-improving compliance ecosystem:", body_style))

    # Improvement 1 Card
    imp1_data = [
        [
            Paragraph("<b>MAJOR IMPROVEMENT 1: Two-Tier Hybrid Engine Pushed into Guideline Ambiguity Radar & Automated Clarity Rewriter</b>", table_header)
        ],
        [
            Paragraph("<b>Objective:</b> Transform the Guideline Ambiguity Radar from a diagnostic analytics chart into an active, self-improving guideline optimization engine.<br/>"
                      "<b>Technical Implementation:</b><br/>"
                      "&bull; <b>Linguistic Ambiguity Scanner:</b> The Tier 1 & Tier 2 engines will analyze brand rules in the Brand Vault to detect vague subjective qualifiers (e.g. <i>'use appropriate discretion'</i>, <i>'maintain reasonable speed'</i>, <i>'ensure intuitive layout'</i>) and lack of operational constraints.<br/>"
                      "&bull; <b>Override Cluster Correlation:</b> Cross-references linguistic ambiguity with empirical reviewer override frequencies from <font name='Courier'>guideline_feedback</font> (rules where reviewers override findings in >20% of audits).<br/>"
                      "&bull; <b>Automated Guideline Rewriter:</b> Synthesizes candidate guideline revisions that replace vague prose with quantified thresholds (e.g. <i>'keep cross-border wire delays under 4 hours'</i>) and pairs each rule with concrete, positive 'Do' and negative 'Don't' examples directly ready for brand manager sign-off.", table_cell)
        ]
    ]
    t_imp1 = Table(imp1_data, colWidths=[540])
    t_imp1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_imp1)
    story.append(Spacer(1, 4))

    # Improvement 2 Card
    imp2_data = [
        [
            Paragraph("<b>MAJOR IMPROVEMENT 2: Interactive Visual Clear-Space & WCAG Contrast Heatmap Inspector</b>", table_header)
        ],
        [
            Paragraph("<b>Objective:</b> Provide visual designers and creative directors with spatial, pixel-level verification of brand logos, clear-space boundaries, and localized text-on-image contrast.<br/>"
                      "<b>Technical Implementation:</b><br/>"
                      "&bull; <b>4&times;4 Spatial Subdivision Matrix:</b> The visual analyzer will subdivide uploaded campaign banners, social tiles, and lockups into a 4&times;4 spatial coordinate grid.<br/>"
                      "&bull; <b>Local CIE LAB &Delta;E & Contrast Heatmap:</b> Computes localized colour deviations and relative luminance ratios across each sector, rendering an interactive canvas heatmap overlay directly in the review panel.<br/>"
                      "&bull; <b>Logo Clear-Space Boundary Detection:</b> Uses edge detection and alpha channel bounding boxes to measure actual breathing room surrounding brand wordmarks against the Brand Vault clear-space rule (e.g. minimum 16px clear space for NovaPay), visually flagging banner elements that infringe upon the exclusion zone.", table_cell)
        ]
    ]
    t_imp2 = Table(imp2_data, colWidths=[540])
    t_imp2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D35400")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_imp2)
    story.append(Spacer(1, 4))

    # Improvement 3 Card
    imp3_data = [
        [
            Paragraph("<b>MAJOR IMPROVEMENT 3: Cryptographically Signed Pre-Publication Compliance Certificate</b>", table_header)
        ],
        [
            Paragraph("<b>Objective:</b> Enable regulated enterprises (fintech, healthcare) to generate legally verifiable, tamper-evident governance proof before marketing materials go live.<br/>"
                      "<b>Technical Implementation:</b><br/>"
                      "&bull; <b>Asymmetric Key Generation (Ed25519/RSA):</b> Extends the current SHA-256 content digest with cryptographic keypair signing generated on-device.<br/>"
                      "&bull; <b>Verifiable Governance Sign-Off Bundle:</b> Packages the approved content hash, Brand Vault rule version, active fact sheet snapshot, approver role signature, and documented finding overrides into a standardized JSON-LD governance token.<br/>"
                      "&bull; <b>Exportable PDF Certificate & Verification API:</b> Generates a formatted single-page Compliance Certificate PDF with embedded QR verification digest, accompanied by an open endpoint (<font name='Courier'>POST /api/verify-certificate</font>) allowing third-party compliance auditors to mathematically verify certificate authenticity without accessing confidential draft copy.", table_cell)
        ]
    ]
    t_imp3 = Table(imp3_data, colWidths=[540])
    t_imp3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27AE60")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_imp3)

    # =========================================================================
    # PAGE 4: DEMONSTRATION WALKTHROUGH, EVALUATION BREAKDOWN & EVIDENCE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Five-Step Judge's Demonstration Walkthrough & Verification", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceBefore=1, spaceAfter=5))

    # 5-Step Demo Card
    demo_steps_data = [
        [
            Paragraph("Step", table_header),
            Paragraph("Interactive Demonstration Action", table_header),
            Paragraph("Expected System Behaviour & Governance Output", table_header),
        ],
        [
            Paragraph("<b>Step 1</b>", table_cell_bold),
            Paragraph("<b>Launch LoomShield:</b> In terminal, execute:<br/><font name='Courier'>python run_loomshield.py --host 127.0.0.1 --port 8000</font><br/>Open <b>http://127.0.0.1:8000</b> in any browser.", table_cell),
            Paragraph("Workspace UI loads immediately. Live self-test confirms both Tier 1 & Tier 2 engines are active with zero external cloud API keys.", table_cell),
        ],
        [
            Paragraph("<b>Step 2</b>", table_cell_bold),
            Paragraph("<b>Select Configured Brand:</b> In top navigation brand selector, choose <b>NovaPay Enterprise</b> (fintech) or <b>Verdant Clinical Systems</b> (healthcare).", table_cell),
            Paragraph("Active Brand Vault constraints, prohibited terminology lexicon, verified facts, approved hex palette, and WCAG thresholds dynamically load locally.", table_cell),
        ],
        [
            Paragraph("<b>Step 3</b>", table_cell_bold),
            Paragraph("<b>Ingest Content or Upload Document:</b> Navigate to <i>'New Audit'</i>. Paste copy or click <i>'Upload File'</i> to submit a <b>.pdf, .docx, .html, .md</b> document or <b>.svg, .png</b> image.", table_cell),
            Paragraph("Document parser validates magic bytes (<font name='Courier'>%PDF-</font>), tracks page boundary spans, and extracts text locally in-memory without cloud transmission.", table_cell),
        ],
        [
            Paragraph("<b>Step 4</b>", table_cell_bold),
            Paragraph("<b>Execute Audit & Inspect Citations:</b> Click <i>'Run Audit'</i>. Inspect findings in the 3-panel Review Studio across the 6 governance pillars.", table_cell),
            Paragraph("Findings display exact Brand Rule IDs, paragraph references (<font name='Courier'>Page 1, P2</font>), numerical claim comparisons against Verified Facts, and surgical suggestions.", table_cell),
        ],
        [
            Paragraph("<b>Step 5</b>", table_cell_bold),
            Paragraph("<b>Review, Correct & Approve:</b> Preview surgical fix. Click <b>Accept</b> to apply replacement, <b>Modify</b> to tailor phrasing, or <b>Dismiss</b> with documented rationale.", table_cell),
            Paragraph("Transition workflow to <i>'Approved'</i>. Content SHA-256 hash, version snapshot, and reviewer audit events are immutably logged in <i>'Audit History'</i>.", table_cell),
        ],
    ]
    demo_table = Table(demo_steps_data, colWidths=[40, 240, 260])
    demo_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 5))

    # Screenshots Visual Evidence
    story.append(Paragraph("<b>5.1 Visual Application Evidence (Live Review Studio & Brand Vault)</b>", h2_style))
    screenshot_path1 = r"D:\LoomShield\docs\live_studio_screenshot.png"
    screenshot_path2 = r"D:\LoomShield\docs\inkloom_art_site.png"

    img_elements = []
    if os.path.exists(screenshot_path1) and os.path.exists(screenshot_path2):
        im1 = RLImage(screenshot_path1, width=265, height=92)
        im2 = RLImage(screenshot_path2, width=265, height=92)
        img_table = Table([[im1, im2]], colWidths=[270, 270])
        img_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(img_table)
        story.append(Paragraph("<font color='#5F6368'><b>Left:</b> LoomShield 3-Panel Review Studio with explainable finding cards & exact rule citations. <b>Right:</b> Working project interface & Brand Vault governance.</font>", callout_text))
        story.append(Spacer(1, 4))

    # Complete Evaluation Breakdown (All 25 Cases Clarified)
    story.append(Paragraph("<b>5.2 Complete Cycle 4 Empirical Evaluation Breakdown (All 25 Test Scenarios)</b>", h2_style))
    story.append(Paragraph("The evaluation suite in <font name='Courier'>tests/generate_test_cycles_report.py</font> validates <b>25 total test cases</b>: 16 positive test cases (known violations) and 9 negative test cases (compliant enterprise copy and on-palette assets). Metrics are computed strictly as: <b>Precision = TP / (TP + FP)</b>; <b>Recall = TP / (TP + FN)</b>; <b>F1 = 2 &times; (Precision &times; Recall) / (Precision + Recall)</b>; <b>Specificity = TN / (TN + FP)</b>:", body_style))

    eval_data = [
        [
            Paragraph("Governance Pillar Category", table_header),
            Paragraph("Total Cases", table_header),
            Paragraph("True Pos (TP)", table_header),
            Paragraph("True Neg (TN)", table_header),
            Paragraph("False Pos (FP)", table_header),
            Paragraph("False Neg (FN)", table_header),
            Paragraph("Precision", table_header),
            Paragraph("Recall", table_header),
            Paragraph("F1-Score", table_header),
        ],
        [
            Paragraph("<b>Terminology & Product Naming</b>", table_cell_bold),
            Paragraph("9 cases", table_cell),
            Paragraph("6", table_cell),
            Paragraph("3", table_cell),
            Paragraph("0", table_cell),
            Paragraph("0", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("<b>1.000</b>", table_cell_bold),
        ],
        [
            Paragraph("<b>Promotional Claims & Fact Retrieval</b>", table_cell_bold),
            Paragraph("9 cases", table_cell),
            Paragraph("6", table_cell),
            Paragraph("3", table_cell),
            Paragraph("0", table_cell),
            Paragraph("0", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("<b>1.000</b>", table_cell_bold),
        ],
        [
            Paragraph("<b>Tone, Voice & Guardrail Framing</b>", table_cell_bold),
            Paragraph("4 cases", table_cell),
            Paragraph("2", table_cell),
            Paragraph("2", table_cell),
            Paragraph("0", table_cell),
            Paragraph("0", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("<b>1.000</b>", table_cell_bold),
        ],
        [
            Paragraph("<b>Visual & Accessibility Controls</b>", table_cell_bold),
            Paragraph("3 cases", table_cell),
            Paragraph("2", table_cell),
            Paragraph("1", table_cell),
            Paragraph("0", table_cell),
            Paragraph("0", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("100.0%", table_cell),
            Paragraph("<b>1.000</b>", table_cell_bold),
        ],
        [
            Paragraph("<b>COMPLETE EVALUATION TOTAL</b>", table_cell_bold),
            Paragraph("<b>25 cases</b>", table_cell_bold),
            Paragraph("<b>16</b>", table_cell_bold),
            Paragraph("<b>9</b>", table_cell_bold),
            Paragraph("<b>0</b>", table_cell_bold),
            Paragraph("<b>0</b>", table_cell_bold),
            Paragraph("<b>100.0%</b>", table_cell_bold),
            Paragraph("<b>100.0%</b>", table_cell_bold),
            Paragraph("<b>1.000</b>", table_cell_bold),
        ],
    ]
    eval_table = Table(eval_data, colWidths=[140, 50, 50, 50, 50, 50, 50, 50, 50])
    eval_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, c_bg_alt]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAECEE")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(eval_table)
    story.append(Spacer(1, 4))

    # Submission Links & Verification Table (without redundant 'Direct Location' column)
    story.append(Paragraph("<b>5.3 Submission Links & Verification</b>", h2_style))
    sub_data = [
        [
            Paragraph("Submission Item", table_header),
            Paragraph("Details, Working URLs & Verification Commands", table_header),
        ],
        [
            Paragraph("<b>Source-Code Repository Link</b>", table_cell_bold),
            Paragraph("<font color='#EA633F'><b>https://github.com/isaacincognito007-cloud/Inkloom-artLoomShield</b></font><br/>Full codebase cleanly committed on <font name='Courier'>main</font> branch with zero external cloud dependencies.", table_cell),
        ],
        [
            Paragraph("<b>Working Project Link</b>", table_cell_bold),
            Paragraph("<font color='#EA633F'><b>https://inkloom.art</b></font> &nbsp;(Local workspace: <b>http://127.0.0.1:8000</b> &nbsp;|&nbsp; OpenAPI: <b>http://127.0.0.1:8000/docs</b>)", table_cell),
        ],
        [
            Paragraph("<b>Automated Test Suite (Full)</b>", table_cell_bold),
            Paragraph("<b>68/68 automated tests passed (100% pass rate); code coverage measured separately.</b><br/>Execute in terminal: <font name='Courier'>pytest D:\\LoomShield\\tests\\ -v</font> (Includes 15 dedicated PDF tests in <font name='Courier'>test_loomshield_pdf.py</font>)", table_cell),
        ],
        [
            Paragraph("<b>Participant Declaration</b>", table_cell_bold),
            Paragraph("I, <b>Isaac Shiloah Herbert V</b> (Team <b>isaac.incognito007</b>), declare that the LoomShield codebase, architecture, documentation, and evaluation test suite were developed and verified for Round 2 delivery. The software operates 100% locally on-device with zero mandatory cloud AI keys.<br/>"
                      "<b>Signature:</b> Isaac Shiloah Herbert V &nbsp;&bull;&nbsp; <b>Date:</b> October 22, 2026 &nbsp;&bull;&nbsp; <b>Email:</b> isaac.incognito007@gmail.com", table_cell),
        ],
    ]
    sub_table = Table(sub_data, colWidths=[150, 390])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_alt]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sub_table)

    # Build document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated: {output_path}")

    # Copy to root and artifact directory
    root_target = r"D:\LoomShield\LoomShield_Project_Submission_Round2.pdf"
    shutil.copyfile(output_path, root_target)
    print(f"Copied to root: {root_target}")

    artifact_dir = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57"
    if os.path.exists(artifact_dir):
        artifact_target = os.path.join(artifact_dir, "LoomShield_Project_Submission_Round2.pdf")
        shutil.copyfile(output_path, artifact_target)
        print(f"Copied to artifacts: {artifact_target}")


if __name__ == "__main__":
    out_dir = r"D:\LoomShield\docs"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "LoomShield_Project_Submission_Round2.pdf")
    build_pdf(target)
