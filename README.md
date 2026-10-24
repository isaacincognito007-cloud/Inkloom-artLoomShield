# LoomShield — Local-First Brand Governance Workspace

**Team Name:** `isaac.incognito007`  
**Lead Engineer & Architect:** Isaac Shiloah Herbert V (`isaac.incognito007@gmail.com`)  
**Operating Mode:** Two Local On-Device Engines (`Tier 1: Deterministic Engine` + `Tier 2: Embedded Scikit-Learn TF-IDF NLP Engine`) • **Zero Mandatory External AI API Keys**

---

## 1. Product Vision & End-to-End User Journey

**LoomShield** is a local-first, evidence-backed brand-governance workspace that inspects marketing copy, product announcements, and visual assets against approved organisational guidelines before publication.

```text
CREATE CONTENT -> CHECK AGAINST BRAND RULES -> IDENTIFY ISSUES -> RETRIEVE RELEVANT EVIDENCE
  -> PROPOSE CORRECTIONS -> HUMAN REVIEW -> APPROVAL -> AUDIT HISTORY -> GUIDELINE IMPROVEMENT
```

---

## 2. Two-Tier Local Engine Architecture (Zero Mandatory API Keys)

| Your Requirement | API Key? | NLP? | LoomShield Implementation |
| :--- | :--- | :--- | :--- |
| **Local deterministic engine only** | **No** | Basic, rule-based NLP | **Tier 1: Deterministic Engine** — Regex patterns, terminology & capitalization dictionaries, WCAG 2.1 contrast math, CIE LAB $\Delta E$ colour distance, HTML/SVG DOM structure checks. |
| **Local engine + embedded NLP model** | **No** | Yes, including machine-learning NLP | **Tier 2: Embedded Scikit-Learn TF-IDF Engine** — On-device `TfidfVectorizer` (1–2 n-grams) + `cosine_similarity` fact retrieval, numerical/percentage claim comparison against `Verified` facts, and evidence-backed replacement templates. |
| **Local engine + cloud AI fallback** | **No** | Planned / Not Implemented | **Tier 3: Cloud Escalation (Planned)** — Formally labeled as planned and not implemented in this build. All audits execute via on-device deterministic checks and local NLP. |
| **Two local engines, both running on-device** | **No** | Yes, if the engines include NLP | **Primary Active Mode** — Tier 1 + Tier 2 execute together in-memory on-device with zero external network calls. |

---

## 3. Six Audit Pillars & Honest Pillar States

Every audit evaluates six distinct brand-governance pillars and reports one of five explicit states (`Passed`, `Findings`, `Needs Review`, `Not Checked`, `Check Failed`):

1. **Tone and Voice** — Detects alarmist urgency, fear-mongering, and off-brand tone heuristics.
2. **Terminology** — Enforces approved product naming, case-sensitive brand spelling (`NovaPay`), and prohibited phrase replacements (`AI Engine` $\rightarrow$ `Local Governance Engine`).
3. **Messaging** — Verifies that automation claims include required human-approval guardrail framing.
4. **Promotional Claims** — Extracts numerical and superlative claims (`95% faster processing`) and compares them against `Verified` facts (`FACT-101`: `64% faster`) in the Brand Vault via TF-IDF cosine retrieval. Claims with no matching fact in the Brand Vault are honestly marked `Needs Review` (`"No supporting fact was found in the configured Brand Vault. Human verification is required."`).
5. **Visual and Logo Consistency** — Checks declared hex colours and uploaded raster/SVG swatches against approved Brand Vault colours using CIE LAB $\Delta E$ tolerance. Marked `Not Checked` when no visual colours or assets are provided.
6. **Accessibility** — Evaluates WCAG 2.1 AA contrast ratios, HTML heading hierarchy (`H2 -> H4` skips), visual asset alt-text requirements, and Flesch-Kincaid reading ease. Marked `Check Failed` if an uploaded file is corrupted or contains no selectable text.

---

## 4. Document Ingestion & Local PDF Auditing

LoomShield supports local ingestion and brand auditing across **8 document and asset formats**:
- **Text & Markup:** `.pdf`, `.docx`, `.md`, `.html`, `.txt`
- **Visual & Vector:** `.svg`, `.png`, `.jpg` / `.jpeg`

### Local PDF Processing Guarantees
- **100% Local & In-Memory:** Pure-Python text extraction using `pypdf` with zero external network or cloud AI calls.
- **Page & Paragraph Offset Mapping:** Findings map directly to PDF pages and paragraph positions (e.g. `Page 1, P2`) for human reviewer verification.
- **Integrity & Magic Byte Validation:** Verifies `%PDF-` file header signatures, rejecting renamed binaries or disguised scripts.
- **Configurable Safety Limits:** Enforces a 5 MB upload limit and configurable page limit (`LOOMSHIELD_MAX_PDF_PAGES`, default 100 pages). Password-protected or encrypted PDFs are safely rejected with actionable guidance.
- **Honest Limitation Reporting:** Scanned / image-only PDFs containing zero selectable text are detected and flagged as `Check Failed` with clear guidance that OCR is not currently supported. For text-based PDFs, `Visual and Logo Consistency` is honestly marked `Not Checked` unless visual color specs are supplied.

---

## 5. Quick Start & Verification

### Start the Workspace Server
```powershell
cd D:\LoomShield
python run_loomshield.py
```
- **Workspace UI:** `http://127.0.0.1:8000`
- **Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`

### Run the Automated Test Suite (68/68 Tests Passing)
```powershell
# Run all unit, cycle, API, and PDF tests
pytest D:\LoomShield\tests\ -v

# Run dedicated PDF verification suite (15 tests)
pytest D:\LoomShield\tests\test_loomshield_pdf.py -v
```

---

## 5. Round 3 Named Improvements (Scoped for Round 3 Delivery)

In accordance with competition rules, the central workflow runs end-to-end in this MVP, while the three named improvements are scoped for Round 3 delivery:
1. **Improvement 1:** Automated Guideline Clarity Rewriter (synthesizing candidate rule rewrites from Ambiguity Radar override clusters).
2. **Improvement 2:** Interactive $4\times 4$ Visual Clear-Space & Accessibility Heatmap.
3. **Improvement 3:** Cryptographically Signed Compliance Certificate (asymmetric Ed25519/RSA signing, distinct from the baseline SHA-256 content integrity hash).

# Inkloom-artLoomShield
LoomShield is a local-first brand governance platform that audits marketing content against brand guidelines, verified facts, terminology, visual identity, and accessibility rules. It provides explainable findings, focused corrections, and human-controlled review with zero mandatory external AI API keys for core checks.
 1fa509f994b0dde8aef42c955cf88c063ac1d1f0


### Deployment & Environment Configuration Reference

| Environment Variable | Allowed Values | Default | Purpose & Safety Guarantee |
| :--- | :--- | :--- | :--- |
| `LOOMSHIELD_DEPLOYMENT` | `local`, `hosted` | `hosted` (local in `run_loomshield.py`) | Controls privacy disclosure and least-privilege role defaulting. |
| `LOOMSHIELD_WORKSPACE_MODE` | `production`, `demo` | `production` | Isolates sample data (`loomshield_demo.db`) from production (`loomshield.db`). Role preview only enabled in `demo`. |
| `LOOMSHIELD_USER_ROLE` | `Brand Administrator`, `Reviewer`, `Content Creator` | Least-privilege (`Content Creator` on hosted; `Brand Administrator` on local) | Server-enforced role. Client headers/payloads cannot escalate role in production. |
| `LOOMSHIELD_USER_NAME` | String | `Workspace owner` | Display name stored in audit history and event log. |
| `LOOMSHIELD_DB_PATH` | File Path | `loomshield.db` | Explicit path to SQLite file (set to persistent disk mount on Render). |
| `LOOMSHIELD_MAX_UPLOAD_MB` | Integer (1–100) | `100` | Ingestion streaming safety limit. |
| `LOOMSHIELD_MAX_PDF_PAGES` | Integer (1–500) | `100` | PDF page processing quota. |
| `LOOMSHIELD_CORS_ORIGINS` | Comma-separated URLs | `*` | Inbound CORS origin allowlist (disables credentials when wildcard). |
