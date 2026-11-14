import json
import os

transcript_path = r"C:\Users\acer\.gemini\antigravity\brain\11c432f7-803a-4a12-96cc-48dbee128d57\.system_generated\logs\transcript.jsonl"
output_dir = r"C:\Users\acer\.gemini\antigravity\brain\18cdc601-4187-4ab0-b064-2dcb66303286\scratch"

# Let's inspect the key documents already in D:\LoomShield\docs
docs_dir = r"D:\LoomShield\docs"
doc_files = [f for f in os.listdir(docs_dir) if f.endswith(".md") or f.endswith(".txt") or f.endswith(".json")]

summary_docs = {}
for df in doc_files:
    p = os.path.join(docs_dir, df)
    try:
        with open(p, "r", encoding="utf-8") as f:
            summary_docs[df] = f.read()[:2000] # preview first 2000 chars
    except Exception as e:
        summary_docs[df] = str(e)

with open(os.path.join(output_dir, "docs_preview.json"), "w", encoding="utf-8") as out:
    json.dump(summary_docs, out, indent=2)

print(f"Captured previews of {len(summary_docs)} docs")
