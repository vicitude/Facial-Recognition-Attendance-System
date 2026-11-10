"""Check table_name settings in models and save results."""
import os

search_dirs = [
    r"d:\yol\yolov8_facenet\attendance",
    r"d:\yol\yolov8_facenet\specs",
    r"d:\yol\yolov8_facenet\decisions",
]

results = []
for d in search_dirs:
    if not os.path.isdir(d):
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
            except Exception:
                pass

with open(r"d:\yol\yolov8_facenet\table_name_search.txt", "w", encoding="utf-8") as f:
    if results:
        f.write("\n".join(results))
    else:
        f.write("NO table_name references found\n")
print("Done. Saved to table_name_search.txt")
print(f"Found {len(results)} references")
for r in results[:20]:
    print(r)
