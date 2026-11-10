"""Direct Python search, no shell."""
import os
import sys

search_dirs = [
    r"d:\yol\yolov8_facenet\attendance",
    r"d:\yol\yolov8_facenet\specs",
    r"d:\yol\yolov8_facenet\decisions",
]

results = []
for d in search_dirs:
    if not os.path.isdir(d):
        results.append(f"[missing] {d}")
        continue
    for root, dirs, files in os.walk(d):
        for f in files:
            if not f.endswith(('.py', '.md')):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                for i, line in enumerate(content.splitlines(), 1):
                    if 'table_name' in line.lower() or 'tablename' in line.lower():
                        results.append(f"{path}:{i}: {line.rstrip()[:120]}")
            except Exception as e:
                results.append(f"[err] {path}: {e}")

# Write to file (in case stdout doesn't reach user)
out_path = r"d:\yol\yolov8_facenet\table_name_search.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"Found {len(results)} references\n")
    f.write("\n".join(results))

# Also print (might work in some configs)
for r in results[:30]:
    print(r)
sys.exit(0)
