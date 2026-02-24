import re
from collections import Counter

with open("src/visualize/components.py", encoding="utf-8") as f:
    content = f.read()

start = content.find("def create_ide_layout(")
block = content[start:]
ids = re.findall(r'id="([^"]+)"', block)
dupes = {k: v for k, v in Counter(ids).items() if v > 1}
if dupes:
    print("Duplicate IDs:", dupes)
else:
    print("No duplicate IDs")
print(f"Total: {len(ids)} IDs")
