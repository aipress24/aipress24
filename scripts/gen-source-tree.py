import sys
from pathlib import Path

root = sys.argv[1]

for path in Path(root).rglob("*.py"):
    stem = path.stem
    print(78 * "#")
    print(f"# file: {path}")
    print(78 * "#")
    print()
    src = path.read_text()
    lines = src.split("\n")
    for i, line in enumerate(lines):
        print(line)
        if i > 30:
            print("# ...")
            break
    print()
