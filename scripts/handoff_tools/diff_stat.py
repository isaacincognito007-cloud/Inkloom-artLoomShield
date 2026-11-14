import subprocess

res = subprocess.run(["git", "-C", r"D:\LoomShield", "diff", "--stat"], capture_output=True, text=True)
print(res.stdout)

for f in ["backend/engine.py", "backend/heatmap.py"]:
    print(f"=== Diff for {f} ===")
    res_f = subprocess.run(["git", "-C", r"D:\LoomShield", "diff", f], capture_output=True, text=True)
    print(res_f.stdout[:1500])
