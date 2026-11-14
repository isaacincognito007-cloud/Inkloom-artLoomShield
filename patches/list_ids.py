import re

with open(r'D:\LoomShield\frontend\index.html', encoding='utf-8') as f:
    text = f.read()

ids = re.findall(r'id=["\']([^"\']+)["\']', text)
print(f'Total element IDs in index.html: {len(ids)}')
for element_id in ids:
    print(element_id)
