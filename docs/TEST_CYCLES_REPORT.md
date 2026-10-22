# LOOMSHIELD — MASTER TEST CYCLES & RELEASE GATE REPORT (v2.1.0)

**Application Version:** `2.1.0`  
**Team:** `isaac.incognito007` (Isaac Shiloah Herbert V)  
**Test Hardware & OS:** `Windows-10-10.0.26200-SP0` • `AMD64 Family 23 Model 160 Stepping 0, AuthenticAMD` • `Python 3.11.0`  
**Automated Test Suites:**
- [test_loomshield_cycles_0_to_9.py](file:///D:/LoomShield/tests/test_loomshield_cycles_0_to_9.py) (42 Cycle 0–9 tests)
- [test_loomshield_api.py](file:///D:/LoomShield/tests/test_loomshield_api.py) (10 API & workflow tests)
- [generate_test_cycles_report.py](file:///D:/LoomShield/tests/generate_test_cycles_report.py) (Empirical accuracy & latency benchmark harness)

---

## CYCLE 0 — TEST ENVIRONMENT AND BASELINE

* **Isolated Test Database:** Configured via `LOOMSHIELD_DB_PATH` in [database.py](file:///D:/LoomShield/backend/database.py#L6-L15) (`D:\LoomShield\tests\test_loomshield_isolated.db`), ensuring automated tests never mutate the live workspace database (`loomshield.db`).
* **Zero-Key Baseline:** `LOOMSHIELD_CLOUD_API_KEY` is unset; `external_api_key_required == False` and `external_api_key_configured == False`.
* **Result:** **PASSED** (`test_cycle0_isolated_environment_and_baseline`).

---

## CYCLE 1 — UNIT TESTING (34 Unit Test Cases Across 4 Engines)

| Engine | Cases Tested | Key Edge Cases Verified | Status |
| :--- | :---: | :--- | :---: |
| **A. Terminology Engine** | 10 / 10 | Preferred terms, prohibited terms, case-sensitive `NovaPay` vs `novapay`/`Novapay`/`NOVAPAY`, word-inside-larger-word guard (`novapayments`, `synergistic`), 6 violations in 1 paragraph, surrounding punctuation (`"unhackable,"`, `(NovaWallet)`), empty input, Unicode (`Café Zürich & 東京`), false-positive guards | **PASSED** (`A1`–`A10`) |
| **B. Promotional Claim Engine** | 10 / 10 | Approved `64% faster` (`FACT-101`), exaggerated `95% faster`, unsupported `89%`, superlatives (`#1 in the world`, `guaranteed zero risk`), empty fact vault, reworded valid claim, cross-metric conflict (`99.99% faster`), unit conflict (`38%` vs `38 basis points` in `FACT-104`), 3 claims in 1 document, `Pending Verification` fact (`FACT-105`) | **PASSED** (`B1`–`B10`) |
| **C. Accessibility Engine** | 7 / 7 | Sufficient contrast (`17.45:1`), insufficient contrast (`2.56:1`), white-on-white (`1.0:1`), missing alt-text, HTML (`<h1>` $\rightarrow$ `<h3>`) & Markdown (`#` $\rightarrow$ `###`) heading skips, invalid hex (`#GGGGGG` $\rightarrow$ `Check Failed`), unsupported `.zip` format | **PASSED** (`C1`–`C7`) |
| **D. Visual Engine** | 7 / 7 | Approved hex (`#17191C`), off-palette hex (`#00FF00` $\Delta E$), corrupt image stream (`Check Failed`), 100% transparent RGBA PNG, missing logo/visual asset (`Not Checked`), malformed SVG XML & negative `viewBox`, honest clear-space limitation note | **PASSED** (`D1`–`D7`) |

---

## CYCLE 2 — INTEGRATION TESTING

1. **Test 1 (Brand Vault $\rightarrow$ Terminology Engine):** Created terminology rule in SQLite, ran audit, verified `RULE-TERM-01` citation and character offsets.
2. **Test 2 (Verified Fact Sheet $\rightarrow$ Claim Engine):** Added `Verified` fact (`12500 invoices per minute`), submitted exaggerated claim (`50000 invoices per minute`), verified retrieval and source citation.
3. **Test 3 (Engine $\rightarrow$ Backend API):** Verified JSON schema, finding IDs, locations, pillar states, and `404`/`400` error handling.
4. **Test 4 (Backend $\rightarrow$ Database):** Verified audit findings, revisions, and decisions persist across database re-connections.
5. **Test 5 (Frontend $\rightarrow$ Backend):** Verified exact character-span slice alignment (`content[start_index:end_index] == flagged_text`) for source highlighting.
* **Result:** **PASSED** (`test_cycle2_integration_tests_1_to_5`).

---

## CYCLE 3 — END-TO-END FUNCTIONAL TESTING

* **Scenario A (First Audit):** Created brand profile (`aegiscloud`) $\rightarrow$ added terminology rule $\rightarrow$ added verified fact $\rightarrow$ audited launch paragraph $\rightarrow$ accepted correction $\rightarrow$ saved and reopened.
* **Scenario B (Modify a Suggestion):** Applied custom human-edited replacement (`modify`) $\rightarrow$ verified revision history (`v1` $\rightarrow$ `v3`) and preserved `original_content`.
* **Scenario C (Dismiss a Finding):** Dismissed finding with mandatory justification $\rightarrow$ verified status `dismissed` and Ambiguity Radar feedback log.
* **Scenario D (Incomplete Evidence):** Submitted unsupported claim (`47%` fan noise reduction) $\rightarrow$ marked `needs_review` with `"No supporting fact was found in the configured Brand Vault. Human verification is required."` and zero invented Fact IDs.
* **Scenario E (Failed Processing):** Submitted corrupted `.png` and `.docx` files $\rightarrow$ marked `Check Failed` (never `Passed`).
* **Result:** **PASSED** (`test_cycle3_scenarios_A_to_E`).

---

## CYCLE 4 — ENGINE ACCURACY AND FACTUAL VALIDATION (HONEST EMPIRICAL METRICS)

We evaluated the engine on two separate datasets:
1. **Standard Held-Out Test Set ($n = 22$ examples)** covering explicit rules and digit-based claims.
2. **Adversarial & Paraphrased Stress Set ($n = 30$ examples)** including spelled-out numbers (`"ninety-five percent"`), implicit sarcasm, and borderline industry jargon not yet in the Brand Vault.

| Detection Category | Dataset Tier | Precision | Recall | F1 Score | Honest Failure-Mode & Limitation Analysis |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Terminology & Capitalization** | Standard Held-Out | `1.00` | `1.00` | `1.00` | Exact lexicon and case-sensitivity checks achieve 100% precision on configured terms, but hyphenated or spaced obfuscations (`"u n h a c k a b l e"`) require explicit pattern additions. |
| **Terminology & Capitalization** | Adversarial Stress | `1.00` | `0.88` | `0.93` | Zero false positives, but novel slang not yet added to the Brand Vault is missed until a Brand Administrator adds it. |
| **Promotional Claims (TF-IDF + Numeric)** | Standard Held-Out | `1.00` | `1.00` | `1.00` | Detects digit-based mismatches (`95%` vs `64%`), unit conflicts (`38%` vs `38 basis points`), `Pending Verification` facts, and missing evidence. |
| **Promotional Claims (TF-IDF + Numeric)** | Adversarial Stress | `0.91` | `0.83` | `0.87` | Numbers written purely as English words (`"ninety-five percent faster"`) or qualitative claims without digits or superlatives rely on human review. TF-IDF cosine similarity measures lexical overlap, **not** probability of truth. |
| **Tone & Messaging** | Combined Held-Out | `0.90` | `0.85` | `0.87` | Detects configured alarmist patterns and missing human-oversight clauses, but subtle rhetorical irony requires human editorial review. |

---

## CYCLE 5 — UI, USABILITY, RESPONSIVE AND ACCESSIBILITY TESTING

* **Dashboard & Workspace:** Verified all 4 Overview cards query real SQLite counts; verified empty-state copy; verified Three-Panel workspace highlights and side-by-side diffs.
* **Brand Vault:** Verified search, add, edit, delete confirmation (`window.confirm`), field validation, and unsaved-change indicator across all 5 tabs.
* **Responsive Layouts & Accessibility:** Verified breakpoints at `1440px`, `1200px`, `1024px`, `768px`, and `390px`/`420px`, visible `:focus-visible` outlines, semantic landmarks (`<aside>`, `<nav>`, `<main>`), `aria-live="polite"`, and `@media (prefers-reduced-motion: reduce)`.
* **Result:** **PASSED** (`test_cycle5_ui_usability_responsive_and_accessibility_contracts`).

---

## CYCLE 6 — PRIVACY AND SECURITY TESTING

* **Test 1 & 2 (Zero-Key & Network Isolation):** Verified full audit, NLP fact retrieval, and persistence with zero API keys and zero external network requests.
* **Test 3 (Secret Exposure):** Scanned `index.html`, `app.js`, and `styles.css` — zero API keys or secrets present.
* **Test 4 (File Upload Security):** Verified `> 5 MB` upload rejection (`HTTP 400`) and path-traversal filename sanitization (`../../etc/passwd.txt` $\rightarrow$ `passwd.txt`).
* **Test 5 (HTML & SVG Safety):** Verified `<script>alert('xss')</script>` decomposition, `onerror=` flagging, and XML `<!ENTITY` (XXE) rejection in SVG uploads.
* **Test 6 (Database Integrity):** Verified `PRAGMA foreign_keys = ON` rejects invalid `brand_id` references.
* **Test 7 (Access Control):** Verified `Content Creator` role cannot mark an audit `Approved` (`HTTP 403`), and documented that the UI role switcher is a local single-user persona selector rather than multi-tenant production authentication.
* **Result:** **PASSED** (`test_cycle6_privacy_and_security_tests_1_to_7`).

---

## CYCLE 7 — PERFORMANCE AND RELIABILITY TESTING (MEASURED BENCHMARKS)

Measured across 15 repeated end-to-end API + SQLite runs per text size and 10 runs for raster PNG inspection on `Windows 10 AMD64 (Python 3.11.0)`.

> **Optimization Applied During Cycle 7:** Initial profiling on `25,000` characters identified an $O(N \times M)$ regex paragraph-splitting bottleneck (`2,659 ms`). Replacing it with $O(\log P)$ binary search (`bisect.bisect_right`), per-audit TF-IDF clause memoization, and batch `cur.executemany()` reduced `25,000`-character end-to-end latency by **78%** (down to `572.51 ms` median).

| Input Workload | Median Total Duration | 95th-Percentile (p95) Duration | Median Deterministic Engine | Median Local NLP Retrieval | Median SQLite Save | Failure Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **500 characters** | `84.04 ms` | `94.99 ms` | `4.39 ms` | `34.76 ms` | `41.01 ms` | `0 / 15 (0%)` |
| **5,000 characters** | `166.50 ms` | `205.88 ms` | `21.94 ms` | `62.18 ms` | `81.08 ms` | `0 / 15 (0%)` |
| **25,000 characters** | `572.51 ms` | `625.40 ms` | `99.09 ms` | `198.69 ms` | `271.90 ms` | `0 / 15 (0%)` |
| **600×400 RGBA PNG Image** | `12.46 ms` | `13.51 ms` | `12.46 ms` | `N/A` | `N/A` | `0 / 10 (0%)` |

* **Peak Traced Memory Usage (`tracemalloc`):** `10.44 MB` (well below the `150 MB` budget).

---

## CYCLE 8 & CYCLE 9 — REGRESSION & USER ACCEPTANCE TESTING + FINAL RELEASE GATE

All 8 representative UAT tasks and all 14 Final Release Gate criteria are verified:

- [x] **The core audit works without external API keys.**
- [x] **Brand rules persist in the database.**
- [x] **Findings cite valid Rule IDs or Fact IDs.**
- [x] **The system does not invent missing evidence.**
- [x] **Text highlights identify the correct source spans.**
- [x] **Accept, Modify and Dismiss work correctly.**
- [x] **Audit history survives application restarts.**
- [x] **Failed checks are not labelled Passed.**
- [x] **Core UI works at desktop and mobile widths.**
- [x] **Critical keyboard-accessibility issues are resolved.**
- [x] **Confidential mode has been tested for unexpected network calls.**
- [x] **No known critical security issue remains unresolved.**
- [x] **Accuracy results are measured and honestly documented.**
- [x] **The main workflow has been demonstrated end to end.**
