# LoomShield — Brand Governance Workspace

**Team Name:** `isaac.incognito007`  
**Lead Engineer & Architect:** Isaac Shiloah Herbert V (`isaac.incognito007@gmail.com`)  
**Operating Mode:** Two Local / In-Memory Verification Engines (`Tier 1: Deterministic Engine` + `Tier 2: Embedded Scikit-Learn TF-IDF NLP Engine`) • **Zero Mandatory External AI API Keys**

---

## Try it in 60 seconds (Evaluator Quickstart)
- **Live Frontend Application:** [https://inkloom-artloomshield-frontend.vercel.app](https://inkloom-artloomshield-frontend.vercel.app)
- **Hosted Backend API:** `https://inkloom-artloomshield.onrender.com`

> **Note on Free Instance Wake-up:** The Render free tier instance automatically spins down on inactivity. The first request after idle can take up to 60 seconds to wake the server. An active notification banner informs users during this initial wake-up.

### What is New in Round 2 (Verified in Code & Tests)
1. **Guided "New Audit" Setup:** 5-question wizard dynamically generating isolated, tailor-made compliance checks with 22 validated rule-set fragments across 6 industries, 6 occasions, 6 locales, and 4 tones.
2. **Server-Enforced Roles & Permissions:** Least-privilege server enforcement (`Content Creator`, `Reviewer`, `Brand Administrator`) with CAS concurrency control. Client role override is strictly isolated to demo mode.
3. **Honest Processing Architecture:** Dynamic labels distinguishing `Hosted verification engine` vs `Local processing` with zero third-party AI dependencies.
4. **Atomic Finding Corrections & Lock:** Concurrency-protected finding decisions with compare-and-swap; approved audits are permanently locked against drift.
5. **Robust Rate Limiting & DoS Protection:** Per-IP sliding window rate limiting with reverse proxy hop resolution (`x-vercel-forwarded-for` / multi-hop XFF), global request ceilings, and bounded memory tracking.
6. **Multi-Format Ingestion Suite:** Audits `.pdf`, `.docx`, `.md`, `.html`, `.txt`, `.svg`, `.png`, and `.jpg` with local extraction and page/paragraph mapping.
7. **Automated Test Pass Rate:** 100% automated test pass rate verified across trust & safety, wizard generation, PDF extraction, concurrency, and security regression suites.

### Round 3 Implementation Plan (Three Major Improvements)
1. **Guideline Clarity Rewriter:** Interactive rewriter analyzing baseline override feedback to resolve ambiguous rules into deterministic checks.
2. **4x4 Clear-Space & Contrast Heatmap:** Pixel-level canvas perimeter scanning for logo clear space and real-time WCAG 2.2 color contrast mapping.
3. **Cryptographically Signed Compliance Certificate:** Exportable SHA-256 signed audit certificate proving compliance against verified Brand guidelines versions.
4. **100 MB Streaming Uploads:** Chunked streaming file ingestion for large marketing PDFs and catalogs.
5. **Non-Destructive Preset Application:** Apply rule-set fragments to existing custom brands with one-click rollback.

### Render Deployment Configuration
```bash
LOOMSHIELD_WORKSPACE_MODE=demo
LOOMSHIELD_DEPLOYMENT=hosted
LOOMSHIELD_USER_ROLE=Brand Administrator
LOOMSHIELD_USER_NAME=Sample workspace user
LOOMSHIELD_CORS_ORIGINS=https://inkloom-artloomshield-frontend.vercel.app,http://localhost:3000
```

---

## 1. Product Vision & End-to-End User Journey

**LoomShield** is a brand-governance workspace that inspects marketing copy, product announcements, and visual assets against approved organisational guidelines before publication.

```text
CREATE CONTENT -> CHECK AGAINST BRAND RULES -> IDENTIFY ISSUES -> RETRIEVE RELEVANT EVIDENCE
  -> PROPOSE CORRECTIONS -> HUMAN REVIEW -> APPROVAL -> AUDIT HISTORY -> GUIDELINE IMPROVEMENT
```

---

## 2. Two-Tier Verification Engine Architecture (Zero Mandatory API Keys)

| Your Requirement | API Key? | NLP? | LoomShield Implementation |
| :--- | :--- | :--- | :--- |
| **Local deterministic engine only** | **No** | Basic, rule-based NLP | **Tier 1: Deterministic Engine** — Regex patterns, terminology & capitalization dictionaries, WCAG 2.1 contrast math, CIE LAB $\Delta E$ colour distance, HTML/SVG DOM structure checks. |
| **Local engine + embedded NLP model** | **No** | Yes, including machine-learning NLP | **Tier 2: Embedded Scikit-Learn TF-IDF Engine** — On-device `TfidfVectorizer` (1–2 n-grams) + `cosine_similarity` fact retrieval, numerical/percentage claim comparison against `Verified` facts, and evidence-backed replacement templates. |
| **Local engine + cloud AI fallback** | **No** | Planned / Not Implemented | **Tier 3: Cloud Escalation (Planned)** — Formally labeled as planned and not implemented in this build. All audits execute via deterministic checks and local NLP. |
| **Two local engines, both running on-device** | **No** | Yes, if the engines include NLP | **Primary Active Mode** — Tier 1 + Tier 2 execute together in-memory with zero external network calls. |

---

## 3. Six Audit Check Areas & Honest States

Every audit evaluates six distinct brand-governance check areas and reports one of five explicit states (`Passed`, `Findings`, `Needs Review`, `Not Checked`, `Check Failed`):

1. **Tone and Voice** — Detects alarmist urgency, fear-mongering, and off-brand tone heuristics.
2. **Terminology (Preferred words)** — Enforces approved product naming, case-sensitive brand spelling (`NovaPay`), and prohibited phrase replacements (`AI Engine` $\rightarrow$ `Local Governance Engine`).
3. **Messaging** — Verifies that automation claims include required human-approval guardrail framing.
4. **Promotional Claims** — Extracts numerical and superlative claims (`95% faster processing`) and compares them against `Verified` facts (`FACT-101`: `64% faster`) in the Brand guidelines via TF-IDF cosine retrieval. Claims with no matching fact in the Brand guidelines are honestly marked `Needs Review` (`"No supporting fact was found in the configured Brand guidelines. Human verification is required."`).
5. **Visual and Logo Consistency (Colours and logo)** — Checks declared hex colours and uploaded raster/SVG swatches against approved Brand guidelines colours using CIE LAB $\Delta E$ tolerance. Marked `Not Checked` when no visual colours or assets are provided.
6. **Accessibility** — Evaluates WCAG 2.1 AA contrast ratios, HTML heading hierarchy (`H2 -> H4` skips), visual asset alt-text requirements, and Flesch-Kincaid reading ease. Marked `Check Failed` if an uploaded file is corrupted or contains no selectable text.

---

## 4. Document Ingestion & Multi-Format PDF Auditing

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

## 5. Quick Start & Local Hosting

### Start the Workspace Server Locally
```bash
# 1. Clone the repository
git clone https://github.com/isaacincognito007-cloud/Inkloom-artLoomShield.git
cd Inkloom-artLoomShield

# 2. Install dependencies (Python 3.11 recommended)
pip install -r requirements.txt

# 3. Start local workspace server (Demo mode with evaluator role switcher)
python run_loomshield.py --demo

# Or start in standard production workspace mode:
# python run_loomshield.py
```
- **Local Workspace UI:** `http://127.0.0.1:8000` (or `http://localhost:8000`)
- **Interactive OpenAPI Documentation:** `http://127.0.0.1:8000/docs`
- **Engine Status & Privacy Disclosure:** `http://127.0.0.1:8000/api/engine-status`

### Run the Automated Test Suite (100% Automated Tests Passing)
```bash
# Run all unit, cycle, API, PDF, and wizard tests
python -m pytest -q
```

---

## 6. Deployment & Environment Configuration Reference

| Environment Variable | Allowed Values | Default | Purpose & Safety Guarantee |
| :--- | :--- | :--- | :--- |
| `LOOMSHIELD_DEPLOYMENT` | `local`, `hosted` | `hosted` (`local` in `run_loomshield.py`) | Controls privacy disclosure and operating mode notices. |
| `LOOMSHIELD_WORKSPACE_MODE` | `production`, `demo` | `production` | Isolates sample data (`loomshield_demo.db`) from production (`loomshield.db`). Role preview only enabled in demo. |
| `LOOMSHIELD_STORAGE` | `persistent`, `ephemeral` | `ephemeral` | Declares storage tier to clients and system telemetry. |
| `LOOMSHIELD_USER_ROLE` | `Brand Administrator`, `Reviewer`, `Content Creator` | `Content Creator` (hosted) / `Brand Administrator` (local) | Server-enforced role. Client headers cannot escalate role in production. |
| `LOOMSHIELD_USER_NAME` | String | `Workspace owner` | Display name stored in audit history and event log. |
| `LOOMSHIELD_DB_PATH` | File Path | `loomshield.db` | Explicit path to SQLite file (mount to persistent disk on Render). |
| `LOOMSHIELD_CORS_ORIGINS` | Comma-separated URLs | Default localhost + Vercel origins | Allowed origins for browser CORS access. |
| `LOOMSHIELD_MAX_UPLOAD_MB` | Integer (1-10) | `5` | File upload safety limit (5 MB). |
| `LOOMSHIELD_MAX_PDF_PAGES` | Integer (1-500) | `100` | PDF page processing quota. |
| `LOOMSHIELD_SIGNING_KEY` | Base64 32-byte Ed25519 seed | Ephemeral per-process key | Signs compliance certificates (`alg: "Ed25519"`). Never logged. |
| `LOOMSHIELD_SESSION_SECRET` | Secret string | Random 32-byte secret per process | Signs 8-hour HMAC-SHA256 demo identity tokens (`POST /api/demo/login`). |

---

## 7. Signed Compliance Certificate Threat Model & Separation of Duties

### Signed Compliance Certificate Threat Model (5-Line Summary)
1. **Cryptographic Issuer Proof:** Each certificate envelope (`{payload, alg: "Ed25519", kid, signature_b64}`) is signed with Ed25519 over canonical UTF-8 JSON (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`), proving which signing key (`kid`, first 16 hex chars of `SHA-256(public_key)`) issued the record.
2. **Tamper Evidence:** Any alteration to the certified payload (`content_sha256`, `original_content_sha256`, `brand_version`, `pillar_states`, `findings_summary`, `dismissals`, `approval`, or `issued_at`) invalidates the Ed25519 signature both in the online `/api/certificates/verify` endpoint and offline via `python scripts/verify_certificate.py cert.json --public-key <b64>`.
3. **Server Content-Hash Drift Detection:** When verified on the issuing server, `/api/certificates/verify` additionally checks whether the stored audit record's current content SHA-256 still matches the certified `content_sha256`.
4. **Non-Legal Scope:** A certificate proves who issued it and that the LoomShield review workflow was not altered after issuance; it **does not prove that the content is legally or regulatorily compliant** and is not legal advice.
5. **Ephemeral Demo Key Caveat:** When `LOOMSHIELD_SIGNING_KEY` is not set, the server generates an ephemeral Ed25519 key at startup and explicitly labels every certificate and verification response `"ephemeral demo key: valid only until the server restarts"`.

### Demo Identities & Separation of Duties
- **Seeded Demo Users:** `Priya Nair` (`usr_priya`, `Content Creator`), `Marcus Lee` (`usr_marcus`, `Reviewer`), and `Ava Chen` (`usr_ava`, `Brand Administrator`).
- **Signed Bearer Tokens:** `POST /api/demo/login` returns an 8-hour HMAC-SHA256 token (`Authorization: Bearer <token>`). Server role and actor identity come from the verified token, never from an unverified header.
- **Separation of Duties Rule:** In demo mode, the user who submitted an audit for review (`audits.submitted_by_user_id`) cannot approve that same audit (`403 PERMISSION_DENIED`); a different Reviewer or Brand Administrator must approve it.
- **Production Limitation:** Demo sign-in demonstrates separation of duties without requiring external accounts; anyone using the demo link can switch between demo users. Production mode (`LOOMSHIELD_WORKSPACE_MODE=production`) keeps its existing server-configured role behavior unless integrated with an enterprise identity provider.
