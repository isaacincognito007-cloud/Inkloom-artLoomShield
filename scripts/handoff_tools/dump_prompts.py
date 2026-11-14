import json

user_messages_path = r"C:\Users\acer\.gemini\antigravity\brain\18cdc601-4187-4ab0-b064-2dcb66303286\scratch\user_messages.json"
with open(user_messages_path, "r", encoding="utf-8") as f:
    messages = json.load(f)

for i, m in enumerate(messages):
    print(f"=== [{i}] Step {m['step_index']} ({m['created_at']}) ===")
    print(m['content'][:600])
    print("\n" + "="*50 + "\n")
