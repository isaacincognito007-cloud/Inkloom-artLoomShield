from pathlib import Path

p = Path(r"D:\LoomShield\docs\TEST_CYCLES_REPORT.md")
text = p.read_text(encoding="utf-8")

# Replace file:/// links with relative paths
text = text.replace(
    "[test_loomshield_cycles_0_to_9.py](file:///D:/LoomShield/tests/test_loomshield_cycles_0_to_9.py)",
    "[test_loomshield_cycles_0_to_9.py](../tests/test_loomshield_cycles_0_to_9.py)",
)
text = text.replace(
    "[test_loomshield_api.py](file:///D:/LoomShield/tests/test_loomshield_api.py)",
    "[test_loomshield_api.py](../tests/test_loomshield_api.py)",
)
text = text.replace(
    "[generate_test_cycles_report.py](file:///D:/LoomShield/tests/generate_test_cycles_report.py)",
    "[generate_test_cycles_report.py](../tests/generate_test_cycles_report.py)",
)
text = text.replace(
    "[database.py](file:///D:/LoomShield/backend/database.py#L6-L15)",
    "[database.py](../backend/database.py)",
)

# Remove stale role-switcher text
old_test7 = "* **Test 7 (Access Control):** Verified `Content Creator` role cannot mark an audit `Approved` (`HTTP 403`), and documented that the UI role switcher is a local single-user persona selector rather than multi-tenant production authentication."
new_test7 = "* **Test 7 (Access Control):** Verified `Content Creator` role cannot mark an audit `Approved` (`HTTP 403`), and verified that demo-mode separation of duties blocks submitter self-approval (`HTTP 403`), while production deployments enforce server-configured role and bearer tokens."
assert old_test7 in text, "old_test7 not found"
text = text.replace(old_test7, new_test7, 1)

# Update Cycle 7 measured numbers
old_cycle7_table = """| Input Workload | Median Total Duration | 95th-Percentile (p95) Duration | Median Deterministic Engine | Median Local NLP Retrieval | Median SQLite Save | Failure Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **500 characters** | `84.04 ms` | `94.99 ms` | `4.39 ms` | `34.76 ms` | `41.01 ms` | `0 / 15 (0%)` |
| **5,000 characters** | `166.50 ms` | `205.88 ms` | `21.94 ms` | `62.18 ms` | `81.08 ms` | `0 / 15 (0%)` |
| **25,000 characters** | `572.51 ms` | `625.40 ms` | `99.09 ms` | `198.69 ms` | `271.90 ms` | `0 / 15 (0%)` |
| **600×400 RGBA PNG Image** | `12.46 ms` | `13.51 ms` | `12.46 ms` | `N/A` | `N/A` | `0 / 10 (0%)` |

* **Peak Traced Memory Usage (`tracemalloc`):** `10.44 MB` (well below the `150 MB` budget)."""

new_cycle7_table = """| Input Workload | Median Total Duration | 95th-Percentile (p95) Duration | Median Deterministic Engine | Median Local NLP Retrieval | Median SQLite Save | Failure Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **500 characters** | `192.42 ms` | `530.02 ms` | `9.42 ms` | `90.35 ms` | `87.35 ms` | `0 / 15 (0%)` |
| **5,000 characters** | `414.25 ms` | `455.21 ms` | `46.70 ms` | `191.50 ms` | `165.20 ms` | `0 / 15 (0%)` |
| **25,000 characters** | `2287.89 ms` | `2487.79 ms` | `203.85 ms` | `1493.93 ms` | `658.36 ms` | `0 / 15 (0%)` |
| **600×400 RGBA PNG Image** | `24.86 ms` | `44.26 ms` | `24.86 ms` | `N/A` | `N/A` | `0 / 10 (0%)` |

* **Peak Traced Memory Usage (`tracemalloc`):** `10.12 MB` (well below the `150 MB` budget)."""

assert old_cycle7_table in text, "old_cycle7_table not found"
text = text.replace(old_cycle7_table, new_cycle7_table, 1)

p.write_text(text, encoding="utf-8")
print("Updated docs/TEST_CYCLES_REPORT.md successfully")
