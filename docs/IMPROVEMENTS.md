# LOOMSHIELD — ROUND 3 IMPROVEMENTS SPECIFICATION & EVALUATION REPORT

This document specifies the three major improvements implemented for LoomShield in Round 3, their milestones, empirical acceptance criteria, and a 5-step evaluator demonstration script.

---

## 1. EXECUTIVE SUMMARY & IMPROVEMENT STATUS

| Improvement | Focus Area | Round 2 "Done When" Criterion | Acceptance Status | Key Automated Test |
| :--- | :--- | :--- | :---: | :--- |
| **1. Clarity Rewriter** | Guideline Ambiguity Reduction | An administrator can approve a rewrite, a new Vault version appears, and the app reports violations and overrides for that rule before and after the change. | **PASSED** | `test_h1_clarity_rewriter_before_after_loop_closure_metrics` |
| **2. Heatmap Inspector** | Visual & Clear-Space Verification | Every labelled fixture produces its expected outcome, and any misses are reported openly. | **Met with 3 reported misses (25 of 28)** | `test_h2_heatmap_fixture_suite_against_expected_json` |
| **3. Signed Certificate** | Tamper-Evident Governance | A certificate verifies against the public key, and changing any field makes verification fail. | **PASSED** | `test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility` |

*Full fixture evaluation telemetry and miss breakdowns are documented in [FIXTURE_REPORT.md](file:///D:/LoomShield/docs/FIXTURE_REPORT.md).*

---

## 2. IMPROVEMENT 1: GUIDELINE CLARITY REWRITER

### 2.1 Specification
Vague guideline wording causes inconsistent human review decisions and repeated overrides. The Clarity Rewriter provides an explainable, data-driven closed loop for guideline optimization:
1. **Explainable Ambiguity Scoring:** Evaluates rule descriptions on documented vagueness indicators, missing measurable criteria, override and dismissal rates above the code's minimum sample threshold (default: 5 audits, configurable via `LOOMSHIELD_MIN_AUDIT_SAMPLE`), and accepted human corrections.
2. **Fact-Grounded Candidate Rewrites:** Generates candidate text by consuming preceding articles ("a" / "an"), fixing grammatical agreement, and grounding substitutions in Brand Vault verified facts (topical TF-IDF cosine similarity $\ge 0.35$). If no verified fact qualifies, explicit placeholders (`[SET THRESHOLD: unit]`) prevent hallucination.
3. **Atomic Brand Vault Versioning:** Approving a proposed revision atomically updates the active rule description (`UPDATE ... WHERE id=? AND status='proposed'`), creates an immutable revision log row, increments the brand version by one ($V \rightarrow V+1$), and records an audit event. If the rule description changed concurrently, `HTTP 409 Conflict` is returned.
4. **Before vs After Loop Closure Metrics:** Side-by-side comparison of rule violations, overrides, dismissals, and override rates before and after revision approval, with explicit minimum-sample caveats.

### 2.2 Milestones
- **M1.1 (Scoring Engine):** Pure-function ambiguity scorer with golden fixture determinism.
- **M1.2 (Candidate Generator):** Zero-hallucination fact retrieval and grammar-preserving substitution.
- **M1.3 (Approval API & Versioning):** Atomic revision approval, `409` conflict detection, and brand version increment.
- **M1.4 (Closed-Loop Analytics & UI):** Side-by-side metrics table with minimum-sample caveat in Guideline Insights.

### 2.3 Acceptance Criteria & Verification Matrix
- [x] **Scorer determinism across golden fixtures:** `test_b1_scorer_determinism_with_golden_fixtures` (**PASSED**)
- [x] **Minimum sample threshold (5 audits) and override priority correlation:** `test_b2_minimum_sample_rule_and_priority_correlation` (**PASSED**)
- [x] **Zero invented numbers and explicit placeholder when facts are absent:** `test_b3_property_no_candidate_contains_invented_number_and_placeholder_when_no_fact` (**PASSED**)
- [x] **Optimal rules report no improvement needed:** `test_b3_no_improvement_found_when_already_optimal` (**PASSED**)
- [x] **Approval permissions, version bump, and rejection vault invariance:** `test_b4_b5_permissions_approve_bumps_version_logs_event_and_reject_leaves_vault_unchanged` (**PASSED**)
- [x] **Grammar agreement and unrelated numeric token isolation:** `test_f4_rule_tone_02_never_receives_fact_101_article_agreement_and_nonzero_ambiguity_after` (**PASSED**)
- [x] **Atomic revision approval and concurrent change conflict (409):** `test_f5_approve_revision_409_when_rule_changed_and_atomic_status_transition` (**PASSED**)
- [x] **Before vs After loop closure metrics with minimum-sample disclosure:** `test_h1_clarity_rewriter_before_after_loop_closure_metrics` (**PASSED**)

---

## 3. IMPROVEMENT 2: VISUAL HEATMAP AND CLEAR-SPACE INSPECTOR

### 3.1 Specification
Automates visual brand governance across raster images and SVG assets:
1. **Approved Brand Logo Management:** Brand Administrators can upload, preview, and delete an approved brand logo (PNG or SVG, max 300 KB) in the Brand Vault.
2. **Multi-Scale Normalized Cross-Correlation (NCC):** Template matching runs across scales $0.5\times$ to $2.0\times$ using integral images and fast FFT convolution (`scipy.signal.fftconvolve`) in grayscale (measured ~71 ms on 400x240 image across 6 scales). Scores $\ge 0.80$ resolve logo bounding coordinates; scores $< 0.80$ report `"Not Checked: approved logo not found"`.
3. **Four-Tier Logo Resolution Precedence:** (1) User-drawn box $\rightarrow$ (2) Explicit SVG marker (`data-loomshield-logo="true"`) $\rightarrow$ (3) Multi-scale NCC template match $\rightarrow$ (4) Logo-only PNG alpha bounding box. The UI displays the locating method pill.
4. **Configurable Clear Space:** Clear space threshold editable in the Brand Vault as a multiple of logo height (ratio) or absolute pixels.
5. **Palette Inspection & Honest Contrast Reporting:** CIE Delta-E cell classification ($2\times2$ or $4\times4$ grid) and WCAG 2.1 AA luminance contrast measured for genuine SVG text elements only. Raster text inside flattened pixels is transparently reported as unsupported.
6. **Fixture Suite & Honest Report:** 12 labelled SVG and PNG fixtures in `tests/fixtures/banners/` verified against `expected.json` and documented in `docs/FIXTURE_REPORT.md` (25 of 28 assertions met, 89.3% pass rate; 3 misses honestly documented without fixture gaming).

### 3.2 Milestones
- **M2.1 (Vault Logo Asset & Specs):** Logo upload route (chunked max 300 KB), deletion, and clear space ratio/px configuration.
- **M2.2 (Multi-Scale NCC Matcher):** Classical image analysis template matching with scale invariance ($0.5\times$ to $2.0\times$) and 0.80 threshold cutoff.
- **M2.3 (Heatmap & Grid Analyzer):** Grid-based palette clustering, nearest-neighbor clear space calculation, and SVG text contrast.
- **M2.4 (Fixtures & Automated Fixture Report):** Committed fixture generator, automated regression test, and honest telemetry report.

### 3.3 Acceptance Criteria & Verification Matrix
- [x] **Logo asset upload/delete and clear-space specification API:** `test_h2_vault_approved_logo_upload_delete_and_clear_space_api` (**PASSED**)
- [x] **Full 12-banner fixture suite against expected.json (25 of 28 checks met; 3 reported misses):** `test_h2_heatmap_fixture_suite_against_expected_json` (**Met with 3 reported misses (25 of 28)**)
- [x] **Extended scale and decoy fixtures (0.7x, 1.5x, and near-miss decoy logo):** `test_h2_template_match_scale_and_decoy_fixtures` (**PASSED**)
- [x] **On-palette tile passes all grid cells:** `test_c5_on_palette_tile_all_cells_pass` (**PASSED**)
- [x] **Off-palette quadrant flags exact grid coordinate:** `test_c5_one_off_palette_quadrant_flags_exact_cell_and_cites_coordinates` (**PASSED**)
- [x] **Low-contrast SVG text flagged with measured ratio:** `test_c5_svg_with_low_contrast_text_flagged_with_measured_ratio` (**PASSED**)
- [x] **Logo edge violation fails with measured distance:** `test_c5_svg_logo_too_close_to_edge_fails_with_measured_px_and_no_logo_not_checked` (**PASSED**)
- [x] **Overlay canvas dimensions match raster input exactly:** `test_c5_oversized_image_downscaled_and_svg_script_sanitised_and_shape_stable` (**PASSED**)
- [x] **Inherited SVG fill resolves contrast or marks Not Checked:** `test_g6b_all_unresolvable_svg_text_contrast_state_not_checked_never_passed` (**PASSED**)

### 3.4 Extended Scale & Decoy Fixture Results (Honest Reporting)
In addition to the 12 core banner fixtures, three extended fixtures were evaluated:
1. **0.7x Scaled Template Match (`13_template_match_0_7x.png`):** Matched at scale 0.75 with an NCC score of 0.91 (exceeding the 0.80 threshold). Clear space passed.
2. **1.5x Scaled Template Match (`14_template_match_1_5x.png`):** Matched at scale 1.5 with an NCC score of 1.00 (exceeding the 0.80 threshold). Clear space passed.
3. **Near-Miss Decoy Logo (`15_template_match_decoy.png`):** Features a modified chevron/triangle emblem in brand slate. The NCC score remained below 0.80 across all scales; correctly reported as `"Not Checked: approved logo not found"` without false positive localization.

---

## 4. IMPROVEMENT 3: CRYPTOGRAPHICALLY SIGNED COMPLIANCE CERTIFICATES

### 4.1 Specification
Provides portable, tamper-evident proof that content was verified against an immutable Brand Vault version:
1. **Certificate Version 2 Payload:** Contains `certificate_version: 2`, `audit_id`, `brand_id`, `brand_version`, `document_name`, `content_sha256`, `original_content_sha256`, `submitted_by` {user_id, name, role}, `approval` {approver_user_id, role, name, comment, override_acknowledged, approved_at}, `findings_summary`, `verification_url`, and `revocation` {status_url}.
2. **Canonical JSON & Ed25519 Signing:** Payloads are serialized using canonical JSON with sorted keys, compact separators and UTF-8 (compatible with RFC 8785 for strings, integers and booleans) and signed with Ed25519 (RFC 8032) to establish tamper evidence and issuer authenticity.
3. **Sub-Payload Invariance & Tamper Evidence:** Modifying, deleting, or inserting any byte in the envelope or payload breaks cryptographic signature verification.
4. **Administrative Revocation:** Brand Administrators can revoke certificates via `POST /api/certificates/{id}/revoke` with a mandatory non-empty reason. Public `GET /api/certificates/{id}/status` returns revocation status without leaking content hashes. Revoked certificates fail verification with reason `"certificate_revoked"` while preserving mathematical signature validity.
5. **Backward Compatibility:** `/api/certificates/verify` verifies both v1 and v2 certificates. A v1 certificate with injected v2 fields fails signature verification.

### 4.2 Milestones
- **M3.1 (Ed25519 Signing Pipeline):** Cryptographic signing key management, canonical JSON serializer, and signature verification.
- **M3.2 (Separation of Duties & Submitter Tracking):** Enforcement that audit submitters cannot approve audits, and persistent submitter identity tracking.
- **M3.3 (Certificate v2 & Revocation Engine):** Schema migration for revocations, revocation endpoint, public status check, and verifier integration.
- **M3.4 (Verifier UI & Backward Compatibility):** Public certificate verification page (`#/verify`) with status badges and v1 backward compatibility.

### 4.3 Acceptance Criteria & Verification Matrix
- [x] **Round-trip signing and verification via API and offline CLI:** `test_certificate_sign_and_verify_round_trip` (**PASSED**)
- [x] **Byte-level tamper detection (flipping any payload byte invalidates signature):** `test_certificate_flipping_any_payload_byte_invalid` (**PASSED**)
- [x] **Signature fails under mismatched public key:** `test_certificate_wrong_key_invalid` (**PASSED**)
- [x] **Issuance rejected on unapproved audits (409):** `test_certificate_unapproved_audit_returns_409` (**PASSED**)
- [x] **Deterministic canonicalization across calls:** `test_certificate_canonicalization_deterministic_key_order_and_unicode` (**PASSED**)
- [x] **Content SHA-256 matches approval record SHA-256:** `test_certificate_content_sha256_equals_approval_sha256` (**PASSED**)
- [x] **v2 envelope fields, v1 backward compatibility, and revocation verification:** `test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility` (**PASSED**)
- [x] **Submitter self-approval blocked by separation of duties:** `test_self_approval_blocked_and_different_reviewer_succeeds` (**PASSED**)

---

## 5. FIVE-STEP EVALUATOR DEMO SCRIPT

This walkthrough guides an evaluator through the complete compliance governance lifecycle in under 3 minutes using the seeded demo workspace:

### Step 1: Guided Audit & Rule Violation Discovery
1. Navigate to `#/overview` and click **"New audit"** (or use keyboard shortcut `Ctrl+K` $\rightarrow$ "New audit").
2. In the Guided Setup wizard, select **"Use my existing brand guidelines"** to open the audit workspace.
3. Enter document name `"Q4 Enterprise Liquidity Launch"` and paste the following marketing copy:
   ```html
   <h2>Global Treasury Infrastructure</h2>
   <p>NovaWallet delivers up to 95% faster cross-border settlement with zero human oversight.</p>
   ```
4. Click **"Run audit"**. Observe that LoomShield highlights three distinct findings across three pillars:
   - *Terminology violation:* Prohibited legacy product name `"NovaWallet"` (should be `"NovaPay Core"`).
   - *Promotional claim conflict:* Claim of `"95% faster"` conflicts with approved `FACT-101` (`"up to 64% faster"`).
   - *Tone & messaging violation:* Prohibited phrase `"zero human oversight"`.

### Step 2: Accept Correction & Inspect Finding Resolution
1. Click on the `"NovaWallet"` finding in the right-hand findings rail.
2. Review the suggested correction (`"NovaPay Core"`) and press **`A`** on the keyboard (or click the green checkmark button).
3. Observe that the working document automatically updates from `"NovaWallet"` to `"NovaPay Core"`, the finding state transitions from `open` to `accepted`, and the word-level diff updates.

### Step 3: Separation of Duties & Reviewer Approval
1. Click the profile avatar button in the top-right corner to open the Demo Sign-In menu.
2. Sign in as **Marcus Lee (Reviewer / Submitter)**.
3. In the workflow section, click **"Submit for review"**. The audit transitions to `In Review`.
4. Note that the **"Approve for publication"** button is **disabled** with an explanatory safeguard banner: *"Separation of duties: You submitted this audit for review. A different reviewer must approve it."*
5. Open the Demo Sign-In menu again and switch to **Ava Chen (Brand Administrator)**.
6. Check **"I acknowledge uncorrected findings"**, enter approval justification `"Approved for Q4 launch with documented promotional claim override"`, and click **"Approve for publication"**. The audit is now permanently locked and `Approved`.

### Step 4: Issue Signed Compliance Certificate & Verify
1. Click **"View Certificate"** on the approved audit.
2. Review the Ed25519 signed compliance certificate modal. Note the canonical JSON payload, signing key ID (`kid`), immutable content SHA-256, and submitter / approver identity blocks.
3. Click **"Verify Certificate in Verifier"** to navigate to `#/verify`.
4. Click **"Verify Certificate"**. The system mathematically verifies the Ed25519 signature against the active public key, cross-checks the revocation ledger (`not revoked`), and verifies that the live server content hash matches `content_sha256`.

### Step 5: Guideline Clarity Rewriter & Visual Heatmap Inspection
1. Navigate to **Guideline insights** (`#/insights`).
2. Locate the ambiguity card for `"RULE-TONE-02"`. Observe the explainable ambiguity score, vagueness indicators, and the fact-grounded candidate rewrite.
3. Click **"Approve revision"**. Notice the version increases by one and the side-by-side **Before vs After** loop closure metrics table renders the rule's historical performance alongside the minimum-sample disclosure caveat (default: 5 audits).
4. Open the **Heatmap Inspector** in the workspace on any banner asset to observe multi-scale NCC logo localization, clear space margin rings, and the grid cell palette overlay.
