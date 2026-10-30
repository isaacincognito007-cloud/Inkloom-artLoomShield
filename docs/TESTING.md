# LOOMSHIELD — COMPREHENSIVE TESTING STRATEGY & TEST HARNESS

This document outlines the testing architecture, automated test suites, fixture verification harnesses, and verification procedures for LoomShield.

---

## 1. TESTING PHILOSOPHY & QUALITY GATES

LoomShield enforces strict engineering invariants across all development cycles:
1. **Never delete, skip, or weaken an existing test.** Every test assertion represents a permanent regression lock.
2. **Zero invented numbers.** All performance, precision, recall, and memory metrics must be empirically measured and documented.
3. **Database isolation:** Automated tests run against isolated ephemeral databases (`LOOMSHIELD_DB_PATH`) to prevent state corruption of the live workspace.
4. **Strict Traceability Guard:** Every backticked test name in `README.md` and all documentation files (`docs/*.md`) must exist in the collected pytest suite (`test_f10_readme_traceability_backticked_test_names_exist_in_pytest_collection`).
5. **Exact Suite Accounting:** The per-suite test table must sum exactly to the count reported by `pytest --collect-only -q` (`test_testing_md_table_total_matches_pytest_collected_count`).

---

## 2. AUTOMATED TEST SUITES OVERVIEW

The test harness comprises **195 automated test executions** across 10 specialized suites:

| Test Suite | Purpose & Coverage Areas | Test Count | Key Invariants Tested |
| :--- | :--- | :---: | :--- |
| `tests/test_loomshield_cycles_0_to_9.py` | Foundational Cycles 0 to 9: Lexicon matching, unit conflict, contrast math, Delta-E, UAT scenarios. | 43 | `test_cycle0_isolated_environment_and_baseline`, `test_cycle1_A1_correct_preferred_terminology`, `test_cycle2_integration_tests_1_to_5`, `test_cycle3_scenarios_A_to_E` |
| `tests/test_loomshield_api.py` | Core REST API contracts, audit creation, findings retrieval, workflow transitions, and error handling. | 10 | `test_overview_reads_real_database_metrics`, `test_correction_accept_modify_dismiss_and_workflow_approval`, `test_brand_vault_crud_and_ambiguity_radar`, `test_corrupted_docx_upload_marks_check_failed_never_passed` |
| `tests/test_loomshield_trust_safety.py` | Role-Based Access Control (RBAC), CAS concurrency locks, rate limiting, and input sanitization. | 40 | `test_content_creator_blocked_from_all_16_vault_writes`, `test_workflow_transitions_and_cas_concurrency`, `test_rate_limiting_429_on_audit_upload_and_reset` |
| `tests/test_certificates_and_identities.py` | Ed25519 signing, canonical JSON with sorted keys, v1/v2 compatibility, revocation, separation of duties, and proxy anti-spoofing. | 24 | `test_certificate_sign_and_verify_round_trip`, `test_certificate_flipping_any_payload_byte_invalid`, `test_self_approval_blocked_and_different_reviewer_succeeds`, `test_h8_get_client_ip_render_proxy_anti_spoofing`, `test_h3_certificate_v2_new_blocks_invariance_revocation_and_v1_compatibility` |
| `tests/test_clarity_rewriter.py` | Guideline ambiguity scoring, candidate generation, atomic version bumping, Before/After loop closure metrics, and doc traceability. | 13 | `test_b1_scorer_determinism_with_golden_fixtures`, `test_b3_property_no_candidate_contains_invented_number_and_placeholder_when_no_fact`, `test_h1_clarity_rewriter_before_after_loop_closure_metrics`, `test_f10_readme_traceability_backticked_test_names_exist_in_pytest_collection`, `test_testing_md_table_total_matches_pytest_collected_count` |
| `tests/test_heatmap_inspector.py` | Multi-scale NCC template matching, visual specs API, banner fixture suite verification, clear-space math, and scale/decoy validation. | 18 | `test_h2_heatmap_fixture_suite_against_expected_json`, `test_h2_vault_approved_logo_upload_delete_and_clear_space_api`, `test_h2_template_match_scale_and_decoy_fixtures`, `test_c5_on_palette_tile_all_cells_pass` |
| `tests/test_day3_final_hardening.py` | Image memory budgeting, 12 MP pixel cap boundary, demo/production consistency, tier mapping, Render 25 MB streaming limits, presets, typography, session isolation, and snapshot persistence. | 13 | `test_g2_image_cap_12mp_accepted_and_12mp_plus_1px_rejected`, `test_g3_about_page_does_not_list_shipped_features_under_roadmap`, `test_g4_demo_and_production_audit_counts_agree_across_views`, `test_g5_tier_labels_and_pre_migration_certificate_remains_valid`, `test_system_limits_and_render_free_profile`, `test_configurable_upload_size_env`, `test_brand_presets_catalog_and_apply`, `test_typography_rule_enforcement_in_engine`, `test_per_visitor_demo_isolation`, `test_database_snapshot_export_and_restore`, `test_production_user_authentication` |
| `tests/test_wizard.py` | Guided setup rule composition, isolated Brand Vault creation, and ReDoS catastrophic backtracking safety. | 16 | `test_fragments_loaded_and_validated`, `test_every_fragment_regex_redos_safe`, `test_wizard_profile_creation_atomic_and_never_modifies_existing_brands`, `test_vault_rule_creation_rejects_unsafe_regex` |
| `tests/test_loomshield_pdf.py` | PDF text extraction, multi-page span tracking, and invalid magic byte validation. | 15 | `test_pdf_normal_single_page_extraction`, `test_pdf_multipage_text_extraction_and_spans`, `test_pdf_magic_bytes_validation_non_pdf_renamed`, `test_pdf_corrupted_structure_handling` |
| `tests/e2e/test_ui_e2e.py` | End-to-end browser automation using Playwright: Soft Glass design tokens, responsive layouts, naive-user journey, and edge-case error journeys. | 3 | `test_loomshield_ui_viewports_soft_glass_and_e2e_flow`, `test_h5_naive_user_journey_playwright`, `test_h5_edge_case_journeys_playwright` |

---

## 3. HOW TO EXECUTE TESTS

### 3.1 Running the Full Test Suite
To execute the complete test suite:
```bash
python -m pytest -q
```

### 3.2 Running Playwright End-to-End Tests
Playwright tests launch an ephemeral live server and verify the browser UI:
```bash
python -m pytest tests/e2e/test_ui_e2e.py -q
```

### 3.3 Generating Empirical Benchmarks
Performance benchmarks are executed against 500, 5,000, and 25,000 character payloads:
```bash
python tests/generate_test_cycles_report.py
```
This updates `docs/TEST_CYCLES_REPORT.md` with measured latency distributions, sub-timers, and memory footprints.
