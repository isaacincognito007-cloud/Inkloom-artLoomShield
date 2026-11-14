import json

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"

lines = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        lines.append(line)

print(f"Total lines in transcript: {len(lines)}")
for l in lines[-30:]:
    entry = json.loads(l)
    print(f"Step {entry.get('step_index')}, Type: {entry.get('type')}, ToolCalls: {[tc.get('name') if isinstance(tc, dict) else tc for tc in entry.get('tool_calls', [])]}")
    if entry.get("content"):
        print(f"  Content: {entry.get('content')[:150]}")
