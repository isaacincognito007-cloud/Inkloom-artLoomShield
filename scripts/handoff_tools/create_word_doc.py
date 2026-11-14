import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

output_path = r"C:\Users\acer\Downloads\LoomShield_Submission_Answers.docx"
doc = Document()

# Set standard 1-inch margins
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

# Color Palette
PRIMARY_COLOR = RGBColor(11, 37, 69)      # Deep Navy #0B2545
SECONDARY_COLOR = RGBColor(19, 64, 116)   # Slate Blue #134074
TEXT_DARK = RGBColor(27, 38, 59)          # Charcoal #1B263B
MUTED_TEXT = RGBColor(100, 116, 139)      # Muted Slate #64748B
ACCENT_GREEN = RGBColor(16, 149, 102)     # Emerald
BORDER_COLOR = "CBD5E1"
BG_LIGHT = "F8FAFC"

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=140, bottom=140, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def add_title(text, subtitle):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = PRIMARY_COLOR

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(16)
    r_sub = p_sub.add_run(subtitle)
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(10.5)
    r_sub.font.color.rgb = MUTED_TEXT

def add_question_heading(num_str, title_str, instruction_str=""):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    
    r_num = p.add_run(num_str + " ")
    r_num.font.name = "Arial"
    r_num.font.size = Pt(13)
    r_num.font.bold = True
    r_num.font.color.rgb = SECONDARY_COLOR

    r_title = p.add_run(title_str)
    r_title.font.name = "Arial"
    r_title.font.size = Pt(13)
    r_title.font.bold = True
    r_title.font.color.rgb = PRIMARY_COLOR

    if instruction_str:
        p_inst = doc.add_paragraph()
        p_inst.paragraph_format.space_before = Pt(0)
        p_inst.paragraph_format.space_after = Pt(8)
        p_inst.paragraph_format.keep_with_next = True
        r_inst = p_inst.add_run(instruction_str)
        r_inst.font.name = "Arial"
        r_inst.font.size = Pt(9.5)
        r_inst.font.italic = True
        r_inst.font.color.rgb = MUTED_TEXT

def add_subheading(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = SECONDARY_COLOR

def add_body_p(text, bold_prefix="", space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = TEXT_DARK
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(10)
    r.font.color.rgb = TEXT_DARK

def add_bullet_item(text, bold_prefix=""):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = TEXT_DARK
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(10)
    r.font.color.rgb = TEXT_DARK

# Header & Metadata
add_title("LoomShield — Round 3 Final Submission Responses", 
          "Builder: Isaac Shiloah Herbert V (isaac.incognito007@gmail.com) | Team: isaac.incognito007\nLive App: https://inkloom-artloomshield-frontend.vercel.app | API: https://inkloom-artloomshield.onrender.com")

# ----------------------------------------------------
# QUESTION 1: WHAT YOU BUILT
# ----------------------------------------------------
add_question_heading("Question 1:", "What You Built", 
                     "Prompt: The complete list of features — every feature in the finished product, one per line. Only what is working in the link above.")

features = [
    "Guided 5-question audit setup wizard dynamically generating tailored brand compliance profiles.",
    "Rule-set composer merging 22 validated fragments across 6 industries, 6 occasions, 6 locales, and 4 tones.",
    "Tailored example draft generator producing intentional multi-pillar violations for instant testing.",
    "Multi-format ingestion parser auditing TXT, Markdown, HTML, DOCX, PDF, SVG, PNG, and JPG files.",
    "Six-pillar compliance audit engine covering Terminology, Promotional Claims, Tone and Voice, Messaging Principles, Visual Consistency, and Accessibility.",
    "Tier 1 Deterministic engine using word-boundary regexes, case-sensitive dictionaries, WCAG 2.1 AA relative luminance math, and CIE Delta-E 2000 color clustering.",
    "Tier 2 Embedded Scikit-Learn TF-IDF NLP engine substantiating numerical claims against verified facts with on-device cosine similarity retrieval.",
    "Concurrency-protected finding decisions supporting Accept (with replacement) and Dismiss (with mandatory rationale) guarded by Compare-And-Swap (CAS).",
    "Permanent post-approval compliance lock preventing silent content drift after sign-off.",
    "Review queue with multi-status workflow filtering (Draft, In Review, Changes Requested, Approved).",
    "Five-tab Brand Vault manager governing Tone & Voice, Preferred Words, Verified Facts, Colours/Logo, and Accessibility Rules.",
    "Guideline Insights ambiguity radar flagging high-friction, frequently overridden rules.",
    "Guideline Clarity Rewriter proposing fact-grounded rule rewrites, atomic version bumping (V → V+1), and Before vs. After loop metrics.",
    "Visual Heatmap & Clear-Space Inspector overlaying an interactive NxN grid, measuring logo exclusion clearance, and analyzing SVG vector text contrast.",
    "Approved reference logo management with multi-scale Normalized Cross-Correlation (NCC) template matching (0.5x to 2.0x) using fast 2D FFT convolution.",
    "Cryptographically signed compliance certificates (v2) using Ed25519 (RFC 8032) and canonical JSON (RFC 8785) with byte-level tamper evidence.",
    "Public certificate verification portal (#/verify) with badge indicators and public revocation status checks.",
    "Server-enforced least-privilege roles (Content Creator, Reviewer, Brand Administrator) with separation of duties blocking submitter self-approval.",
    "In-memory sliding-window rate limiter with reverse proxy hop anti-spoofing (LOOMSHIELD_TRUSTED_PROXY_HOPS).",
    "Soft Glass responsive design system strictly capped at 3 concurrent backdrop-filter elements with self-hosted WOFF2 fonts (InterVariable, GeistMono).",
    "Overview KPI dashboard with a 3-step evaluator quickstart walkthrough, hero launch card, and demo workspace reset protected by a 10-minute cooldown."
]

for f in features:
    add_bullet_item(f)

# ----------------------------------------------------
# QUESTION 2: TECHNICAL ARCHITECTURE & IMPLEMENTATION
# ----------------------------------------------------
add_question_heading("Question 2:", "Technical Architecture and Implementation Summary",
                     "Prompt: How the system is put together: components and how they talk to each other, data flow, models and APIs, infrastructure, and the hardest problem you solved.")

add_subheading("System Components & How They Communicate")
add_body_p("LoomShield is built on a zero-key, local-first client-server architecture consisting of three primary subsystems:")
add_bullet_item("Built with vanilla HTML5, modern CSS3 (Custom Properties with Soft Glass design tokens), and standard vanilla ES6 JavaScript modules. It has zero npm or Node.js build dependencies. A lightweight hash router manages all views (#/overview, #/new-audit, #/audit/{id}, #/vault, #/queue, #/insights, #/history, #/settings, #/verify) and communicates with the backend exclusively via asynchronous HTTP/REST calls.", "Frontend Client (SPA): ")
add_bullet_item("Python 3.11 service running on Uvicorn with Pydantic request/response schemas. It handles role-based access control (RBAC), sliding-window rate limiting, right-to-left reverse proxy IP resolution, and chunked multipart upload streaming.", "Backend API Service (FastAPI): ")
add_bullet_item("SQLite 3 database in Write-Ahead Logging mode (PRAGMA journal_mode = WAL;) with strict referential integrity (PRAGMA foreign_keys = ON;), combined with a pure Python Ed25519 cryptographic signer utilizing canonical JSON serialization (RFC 8785 compatible).", "Data & Cryptographic Engine: ")

add_subheading("Data Flow & Six-Pillar Engine Pipeline")
add_body_p("When content or files are uploaded, payloads stream into the backend in 64 KB chunks and abort immediately if exceeding safety caps. The text and visual assets are evaluated across a six-pillar inspection pipeline:")
add_bullet_item("Evaluated deterministically via Tier 1 regexes, case-sensitive dictionaries, word boundaries, and a curated dictionary of vague and alarmist phrases (vague_lexicon.json).", "1. Terminology, Tone, and Messaging: ")
add_bullet_item("Tier 1 extracts numbers, percentages, and units. Sentences are dynamically vectorized using an on-device scikit-learn TfidfVectorizer fitted per request and retrieved against active Brand Vault verified_facts via cosine similarity (>= 0.35 threshold). Discrepancies generate High-severity findings; unverified claims are flagged for human review.", "2. Promotional Claims & Fact Substantiation: ")
add_bullet_item("Evaluated via CIE Delta-E 2000 dominant color extraction, multi-scale Normalized Cross-Correlation (NCC) template matching (0.5x to 2.0x) using fast 2D FFT convolutions (SciPy/NumPy) for reference logos, and WCAG 2.1 AA relative luminance contrast math (4.5:1 / 3.0:1) on vector SVG text elements.", "3. Visual Consistency & Accessibility: ")

add_subheading("Infrastructure & External Dependencies")
add_body_p("The frontend is hosted on Vercel (https://inkloom-artloomshield-frontend.vercel.app) with edge routing and asset caching. The backend is hosted as a Render web service container (https://inkloom-artloomshield.onrender.com). The application contains zero external AI API keys, tokens, or third-party cloud model dependencies; all inspection runs 100% on-device.")

add_subheading("The Hardest Problem Solved")
add_body_p("The hardest engineering challenge was mapping and diffing character-level findings across multi-format document structures (.pdf, .docx, .html) without corrupting underlying document markup or layout offsets, while maintaining strict memory safety on free-tier 512 MB hosting. When processing large images, unbuffered Pillow decoding of a 16 MP image spiked memory by 158–204 MB, threatening container OOM kills. I solved this by implementing header-only pixel validation before full decompression, establishing a strict 12.0 Megapixel ceiling (12,000,000 pixels), sharing decoded RGBA buffers across template matching and color clustering analyzers, and optimizing 2D FFT cross-correlation convolutions to keep peak Windows RSS memory strictly at 109 MB.")

# ----------------------------------------------------
# QUESTION 3: TESTING DETAILS
# ----------------------------------------------------
add_question_heading("Question 3:", "Testing Details",
                     "Prompt: How you tested it: what you tested, how (manual, unit, integration, user testing), what you found and what you fixed. Include anything still known to be imperfect.")

add_subheading("Testing Methodology & Harness Architecture")
add_body_p("I verified LoomShield through a comprehensive automated test harness comprising 188 automated test executions across 10 specialized test suites with a 100% pass rate at commit f6a24f4:")
add_bullet_item("Foundational Cycles 0 to 9 covering lexicon matching, unit conflicts, contrast math, and CIE Delta-E (tests/test_loomshield_cycles_0_to_9.py, 43 tests); REST API contracts and workflow transitions (tests/test_loomshield_api.py, 10 tests); PDF text extraction, multi-page spans, and corrupt byte handling (tests/test_loomshield_pdf.py, 15 tests); and setup wizard rule composition with ReDoS safety (tests/test_wizard.py, 16 tests).", "Unit & Contract Tests: ")
add_bullet_item("Role-Based Access Control (RBAC) across Creator, Reviewer, and Admin roles; CAS concurrency guards on finding decisions; sliding-window rate limiting; and right-to-left reverse proxy anti-spoofing (tests/test_loomshield_trust_safety.py, 40 tests).", "Security & Trust & Safety Tests: ")
add_bullet_item("Ed25519 signing and verification, byte-level tamper detection, RFC 8785 canonical JSON key ordering, separation of duties, and public revocation ledger status checks (tests/test_certificates_and_identities.py, 24 tests).", "Cryptography & Identity Tests: ")
add_bullet_item("Guideline Clarity Rewriter determinism and closed-loop metrics (tests/test_clarity_rewriter.py, 13 tests); Visual Heatmap Inspector 12-fixture banner suite and clear-space math (tests/test_heatmap_inspector.py, 18 tests); and memory budgeting with 12 MP cap boundary tests (tests/test_day3_final_hardening.py, 6 tests).", "Round 3 Feature Suites: ")
add_bullet_item("Automated Playwright browser tests across Desktop (1280px), Tablet (768px with stacked cards and >= 44px touch targets), and Mobile (375px), verifying design tokens, axe-core accessibility contracts (0 critical violations), and naive & edge-case user journeys (tests/e2e/test_ui_e2e.py, 3 tests).", "End-to-End User Testing: ")

add_subheading("What I Found and What I Fixed")
add_bullet_item("Initial Render deployments crashed because Uvicorn was configured with static ports. Fixed by dynamically reading $PORT and binding to 0.0.0.0:$PORT.", "Render Ephemeral Port Crash: ")
add_bullet_item("Rate limiters were vulnerable to forged X-Forwarded-For client headers. Fixed by introducing right-anchored hop parsing (LOOMSHIELD_TRUSTED_PROXY_HOPS, default N=1).", "Reverse Proxy IP Spoofing: ")
add_bullet_item("High-resolution marketing images caused memory spikes up to 204 MB. Fixed by enforcing a 12.0 MP pre-decode cap, sharing RGBA buffers, and constraining peak RSS delta to 109 MB.", "Pillow Memory Exhaustion: ")
add_bullet_item("Simultaneous finding edits overwrote each other. Fixed by implementing Compare-And-Swap (CAS) returning HTTP 409 Conflict.", "Concurrent Finding Overwrites: ")
add_bullet_item("Malicious files renamed to .pdf crashed parsers. Fixed by validating initial %PDF- binary magic bytes and returning structured error findings instead of unhandled exceptions.", "PDF Magic Byte Spoofing: ")

add_subheading("Anything Still Known to Be Imperfect")
add_bullet_item("The backend container spins down on idle and takes ~60 seconds to wake on cold start (mitigated with an active UI warning banner).", "Render Free-Tier Spin-Down: ")
add_bullet_item("SQLite database changes reset when the free container restarts unless a Render Persistent Disk is attached (LOOMSHIELD_DB_PATH=/var/data/loomshield.db).", "Ephemeral Storage on Render Free Tier: ")
add_bullet_item("Flattened bitmap images (.png, .jpg) do not extract text via local OCR; vector SVG text is fully extracted and tested, but flat raster copy is honestly reported as 'Not Checked' with an explanatory card.", "Raster Image OCR Limitation: ")
add_bullet_item("Scanned image-only PDFs lacking selectable text streams cannot be parsed by pypdf and are flagged as 'Couldn't check'.", "Scanned Image-Only PDFs: ")
add_bullet_item("Evaluated against 12 labelled banner fixtures with 28 assertions, achieving 25 hits and 3 misses (89.3% pass rate), which are openly reported in docs/FIXTURE_REPORT.md (e.g. SVG DOM grouping placing contrast findings under General, unresolved CSS var fills logged as Info, and 1.5x upscaling interpolation falling just short of 0.800).", "Visual Heatmap Fixture Benchmark: ")

# ----------------------------------------------------
# QUESTION 4: THE THREE IMPROVEMENTS
# ----------------------------------------------------
add_question_heading("Question 4:", "The Three Improvements You Committed To",
                     "Prompt: At the end of Round 2 you named three major improvements. Answer for each one: what you said you would do, and what you actually delivered.")

add_subheading("Improvement 1 — Guideline Clarity Rewriter")
add_body_p("An ambiguity optimizer that analyzes reviewer overrides and proposes deterministic rule rewrites for admin approval, eliminating subjective disputes and turning vague rules into consistent automated checks. (Round 2 Done When criterion: An administrator can approve a rewrite, a new Vault version appears, and the app reports violations and overrides for that rule before and after the change.)", "What I Committed To: ")
add_body_p("Delivered and fully verified. Built an ambiguity scoring engine evaluating rules on documented vagueness indicators, missing measurable criteria, and override rates above a minimum sample threshold (default: 5 audits; test_b1_scorer_determinism_with_golden_fixtures). Implemented a candidate generator that retrieves active Brand Vault verified facts using TF-IDF cosine similarity (>= 0.35) and injects verified numeric thresholds without hallucination, falling back to explicit placeholders ([SET THRESHOLD: unit]) if absent (test_b3_property_no_candidate_contains_invented_number_and_placeholder_when_no_fact). Added atomic approval workflow that updates the rule description, creates an immutable revision log row, bumps the brand version by one (V → V+1), and detects concurrent modifications with HTTP 409 Conflict. Shipped the Before vs. After loop closure metrics table in Guideline Insights displaying violations, overrides, dismissals, and override rates before and after rule revision (test_h1_clarity_rewriter_before_after_loop_closure_metrics).", "What I Delivered: ")

add_subheading("Improvement 2 — Visual 4x4 Clear-Space & Accessibility Canvas Heatmap Inspector")
add_body_p("A computer-vision canvas scanner that detects logos, measures clear-space exclusion perimeters, and renders a visual contrast heatmap, giving designers visual bounding boxes on their artwork instead of text error codes. (Round 2 Done When criterion: Every labelled fixture produces its expected outcome, and any misses are reported openly.)", "What I Committed To: ")
add_body_p("Delivered and verified against committed fixture benchmarks. Implemented an interactive canvas overlay with NxN grid cells displaying pass, warning, and off-palette violation states based on CIE Delta-E 2000 color clustering against Brand Vault colors (test_c5_on_palette_tile_all_cells_pass). Built approved reference logo management in Brand Vault paired with multi-scale Normalized Cross-Correlation (NCC) template matching (0.5x to 2.0x) using SciPy fast 2D FFT convolution (test_h2_vault_approved_logo_upload_delete_and_clear_space_api). Added clear-space perimeter analysis calculating pixel distances from detected logo boundaries to canvas edges and sibling elements. Implemented WCAG 2.1 AA relative luminance contrast analysis for vector SVG text elements, resolving inherited group fills and gradient markers. Evaluated against a committed suite of 12 labelled banner fixtures plus 3 scale/decoy fixtures, achieving 25 hits out of 28 checks (89.3% pass rate). All 3 misses are documented transparently in docs/FIXTURE_REPORT.md (test_h2_heatmap_fixture_suite_against_expected_json).", "What I Delivered: ")

add_subheading("Improvement 3 — Cryptographically Signed Compliance Certificate")
add_body_p("A tamper-evident certificate generator that signs content SHA-256 hashes and Brand guidelines versions with an asymmetric private key, giving enterprises verifiable proof that published content was formally approved. (Round 2 Done When criterion: A certificate verifies against the public key, and changing any field makes verification fail.)", "What I Committed To: ")
add_body_p("Delivered and fully verified. Implemented an Ed25519 (RFC 8032) asymmetric signing pipeline with RFC 8785 canonical JSON serialization (sorted keys, compact delimiters, UTF-8) (test_certificate_sign_and_verify_round_trip). Defined the Version 2 certificate payload sealing: audit_id, brand_id, brand_version, document_name, content_sha256, original_content_sha256, submitted_by identity, approval record (approver user ID, role, override acknowledgment, timestamp), and revocation URL. Implemented byte-level tamper detection: flipping, adding, or deleting any byte in the envelope or payload breaks cryptographic signature verification (test_certificate_flipping_any_payload_byte_invalid). Built an administrative revocation ledger (POST /api/certificates/{id}/revoke) with a mandatory reason, and public status checking (GET /api/certificates/{id}/status). Created a public certificate verification portal (#/verify) with badge indicators and backward compatibility for v1 certificates. Enforced separation of duties: audit submitters cannot approve their own submissions (test_self_approval_blocked_and_different_reviewer_succeeds).", "What I Delivered: ")

# ----------------------------------------------------
# QUESTION 5: ANYTHING ELSE IMPROVED
# ----------------------------------------------------
add_question_heading("Question 5:", "Anything Else You Improved After Round 2",
                     "Prompt: Other work you did since Round 2 that was not one of the three. Write 'Nothing else' if there is none.")

add_bullet_item("Lowered the maximum image limit to 12.0 Megapixels (12,000,000 pixels) and enforced pre-decode dimension checks, locking peak Windows RSS memory delta strictly at 109 MB to prevent container crashes on 512 MB hosting (test_g2_image_cap_12mp_accepted_and_12mp_plus_1px_rejected).", "Memory Budgeting & 12.0 Megapixel Safety Cap: ")
add_bullet_item("Untracked backend/loomshield.db from git cache (git rm --cached) and added *.db to .gitignore, verifying that a clean clone creates and seeds an isolated database automatically on first startup.", "Git Repository Hygiene & Clean Seeding: ")
add_bullet_item("Audited the frontend UI and documentation to ensure shipped capabilities are not listed under future roadmap items (test_g3_about_page_does_not_list_shipped_features_under_roadmap).", "Accurate UI Capabilities & Roadmap Disclosures: ")
add_bullet_item("Aligned SQL aggregation queries across overview KPI cards and audit history to ensure identical record counts across both modes (test_g4_demo_and_production_audit_counts_agree_across_views).", "Reconciled Demo & Production Audit Counts: ")
add_bullet_item("Labeled every finding card with its exact underlying engine (Tier 1: Deterministic Engine vs. Tier 2: Embedded NLP Engine) and verified that pre-migration certificates remain mathematically valid (test_g5_tier_labels_and_pre_migration_certificate_remains_valid).", "Strict Processing Tier Transparency: ")
add_bullet_item("Refactored frontend navigation into a clean SPA hash router (#/overview, #/new-audit, #/audit/{id}, #/vault, #/queue, #/insights, #/history, #/settings, #/verify), eliminating hardcoded fallback IDs and supporting browser back/forward history navigation.", "Centralized URL Hash Router: ")
add_bullet_item("Created scripts/verify_certificate.py enabling compliance officers to mathematically verify Ed25519 certificates offline without network connectivity.", "Offline CLI Certificate Verifier: ")

# ----------------------------------------------------
# QUESTION 6: WHERE IT GOES NEXT
# ----------------------------------------------------
add_question_heading("Question 6:", "Where It Goes Next",
                     "Prompt: Product roadmap and future development plan — what you would build next and in what order, who it would be for, and what it would take to get there. Be specific.")

add_subheading("1. Phase 1: Enterprise Production Identity & Managed Database (Target: v2.3.0)")
add_bullet_item("Enterprise legal, compliance, and IT administration teams.", "Who It Is For: ")
add_bullet_item("Transition from demo tokens to enterprise Single Sign-On (SSO) via OpenID Connect (OIDC) and SAML 2.0 (Okta, Google Workspace, Microsoft Entra ID), implementing the architecture specified in docs/auth-plan.md. Transition container-local SQLite to managed PostgreSQL (or Litestream-replicated SQLite) to ensure audit history, Brand Vault versions, and certificates survive cloud container redeployments.", "What to Build: ")
add_bullet_item("Implementing OAuth2/OIDC JWT validation middleware in backend/config.py, multi-tenant organization/workspace database schemas, and migration scripts.", "What It Takes to Get There: ")

add_subheading("2. Phase 2: Asynchronous 100 MB Ingestion & Local Quantized OCR (Target: v2.4.0)")
add_bullet_item("Creative agencies and marketing operations auditing large catalog PDFs and flattened raster marketing graphics.", "Who It Is For: ")
add_bullet_item("Asynchronous disk-backed streaming for 100 MB files using tempfile.SpooledTemporaryFile with background worker queues (asyncio/Celery) to prevent ASGI thread blocking. Lightweight, self-hosted ONNX-quantized text detection model to extract text bounding boxes and evaluate WCAG contrast on flattened bitmap images (.png, .jpg).", "What to Build: ")
add_bullet_item("Building an asynchronous background job worker queue, streaming file writer, ONNX runtime inference integration, and bounding-box coordinate mapping.", "What It Takes to Get There: ")

add_subheading("3. Phase 3: Collaborative Inline Comments & Vault Archive Bundles (Target: v2.5.0)")
add_bullet_item("Creative copywriting squads and brand review teams.", "Who It Is For: ")
add_bullet_item("Free-form collaborative inline comments anchored to specific character spans in draft copy (audit_inline_comments table) supporting multi-user threads and resolution statuses. Portable, signed Brand Vault archive bundles (.loomshield-vault.json) with Ed25519 manifest verification for seamless guideline import/export between environments.", "What to Build: ")
add_bullet_item("Adding character-offset annotation UI in frontend/app.js, thread resolution REST endpoints, JSON archive schema validator, and cryptographic manifest signing.", "What It Takes to Get There: ")

add_subheading("4. Phase 4: Cryptographic Key Lifecycle & RFC 3161 Timestamping (Target: v3.0.0)")
add_bullet_item("Regulated financial and healthcare compliance officers requiring multi-year audit non-repudiation.", "Who It Is For: ")
add_bullet_item("Key ID (kid) directories supporting scheduled Ed25519 private key rotation with verification grace periods. RFC 3161 external Timestamp Authority (TSA) cryptographic anchoring, providing independent mathematical proof of exact signing times without third-party blockchain gas fees.", "What to Build: ")
add_bullet_item("Multi-key registry in backend/certificates.py, ASN.1 request/response parser for RFC 3161 timestamp tokens, and TSA signature verification routines.", "What It Takes to Get There: ")

# Save Document
doc.save(output_path)
print(f"Document successfully created at: {output_path}")
print(f"File size: {os.path.getsize(output_path)} bytes")
