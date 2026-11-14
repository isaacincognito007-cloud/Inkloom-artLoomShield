import json

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"

steps_after_8375 = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            entry = json.loads(line)
            idx = entry.get("step_index", 0)
            if idx >= 8375:
                steps_after_8375.append({
                    "step_index": idx,
                    "type": entry.get("type"),
                    "content": entry.get("content", "")[:300] if entry.get("content") else "",
                    "thinking": entry.get("thinking", "")[:200] if entry.get("thinking") else ""
                })
        except:
            pass

print(f"Total steps from 8375 onwards: {len(steps_after_8375)}")
for s in steps_after_8375[:20]:
    print(f"Step {s['step_index']} ({s['type']}): {s['content'][:150]}")
if len(steps_after_8375) > 20:
    print("...")
    for s in steps_after_8375[-10:]:
        print(f"Step {s['step_index']} ({s['type']}): {s['content'][:150]}")
