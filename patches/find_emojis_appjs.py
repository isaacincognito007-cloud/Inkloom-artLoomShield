import re

with open(r'D:\LoomShield\frontend\app.js', encoding='utf-8') as f:
    text = f.read()

emojis = set(re.findall(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]', text))
print('Unique emojis found in app.js:', len(emojis))
for i, line in enumerate(text.splitlines(), start=1):
    matched = [e for e in emojis if e in line]
    if matched:
        safe_line = line.strip().encode('ascii', 'replace').decode()
        print(f'Line {i}: {[ascii(m) for m in matched]} -> {safe_line[:90]}')
