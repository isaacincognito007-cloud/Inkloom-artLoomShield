import os

files_to_read = [
    r"D:\LoomShield\README.md",
    r"D:\LoomShield\docs\ARCHITECTURE.md",
    r"D:\LoomShield\docs\DEVIATIONS.md",
    r"D:\LoomShield\docs\IMPROVEMENTS.md",
    r"D:\LoomShield\docs\ROADMAP.md",
    r"D:\LoomShield\docs\TESTING.md",
    r"D:\LoomShield\docs\TEST_CYCLES_REPORT.md",
    r"D:\LoomShield\docs\FIXTURE_REPORT.md",
]

for p in files_to_read:
    print(f"================ {os.path.basename(p)} ================")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"Total lines: {len(lines)}")
            # print first 50 lines
            print("".join(lines[:60]))
            print("...")
    else:
        print("FILE NOT FOUND")
