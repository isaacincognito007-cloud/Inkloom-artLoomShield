import json

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"

steps = {}
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        idx = e.get("step_index")
        if idx and idx >= 8650:
            steps[idx] = e

print(f"Loaded {len(steps)} steps from 8650 onwards")
for idx in sorted(steps.keys()):
    e = steps[idx]
    tc = e.get("tool_calls")
    content = e.get("content", "")
    thinking = e.get("thinking", "")
    print(f"--- Step {idx} ({e.get('type')}) ---")
    if tc:
        for t in tc:
            if isinstance(t, dict):
                print(f"Tool call: {t.get('name')}, args: {str(t.get('args'))[:150]}")
    if content:
        print(f"Content: {content[:250]}")
    if thinking:
        print(f"Thinking: {thinking[:150]}")
