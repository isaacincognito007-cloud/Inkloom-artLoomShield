import json
import os

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"
output_path = r"C:\Users\acer\.gemini\antigravity\brain\18cdc601-4187-4ab0-b064-2dcb66303286\scratch\user_messages.json"

user_messages = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line_idx, line in enumerate(f):
        try:
            entry = json.loads(line)
            if entry.get("type") == "USER_INPUT":
                user_messages.append({
                    "line_idx": line_idx,
                    "step_index": entry.get("step_index"),
                    "created_at": entry.get("created_at"),
                    "content": entry.get("content")
                })
        except Exception as e:
            pass

print(f"Total USER_INPUT steps: {len(user_messages)}")
with open(output_path, "w", encoding="utf-8") as out:
    json.dump(user_messages, out, indent=2)

for i, m in enumerate(user_messages):
    c = m["content"].replace("\n", " ") if m["content"] else ""
    print(f"[{i}] Step {m['step_index']}: {c[:120]}")
