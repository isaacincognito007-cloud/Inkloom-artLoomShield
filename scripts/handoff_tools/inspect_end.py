import json

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"

total_lines = 0
last_lines = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        total_lines += 1
        last_lines.append(line)
        if len(last_lines) > 40:
            last_lines.pop(0)

print(f"Total lines: {total_lines}")
for l in last_lines[-20:]:
    e = json.loads(l)
    print(f"Step {e.get('step_index')}, Type: {e.get('type')}")
    if e.get("content"):
        print(f"  Content: {e.get('content')[:120]}")
