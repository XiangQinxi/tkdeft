"""汇总基准结果并打印对比表格。"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {0: "tksvg(现状)", 2: "skia", 3: "pillow", 4: "cairo"}

rows = {}
for r in NAMES:
    path = os.path.join(HERE, f"result_r{r}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            rows[r] = json.load(fh)

keys = [k for k in rows[0] if k not in ("label", "renderer", "python", "tk")]

head = f"{'path':18s}" + "".join(f"{NAMES[r]:>16s}" for r in NAMES if r in rows)
print(head)
print("-" * len(head))
for k in keys:
    line = f"{k:18s}"
    for r in NAMES:
        if r not in rows:
            continue
        v = rows[r].get(k, {})
        if isinstance(v, dict) and "mean_ms" in v:
            line += f"{v['mean_ms']:16.4f}"
        else:
            line += f"{'n/a':>16s}"
    print(line)

print()
print("相对现状的加速比：")
for k in keys:
    base = rows[0].get(k, {})
    if not isinstance(base, dict) or "mean_ms" not in base or base["mean_ms"] <= 0:
        continue
    parts = []
    for r in NAMES:
        if r == 0 or r not in rows:
            continue
        v = rows[r].get(k, {})
        if isinstance(v, dict) and "mean_ms" in v:
            parts.append(f"{NAMES[r]}={base['mean_ms'] / v['mean_ms']:6.1f}x")
    print(f"  {k:18s} " + "  ".join(parts))

errs = []
for r, data in rows.items():
    for k, v in data.items():
        if isinstance(v, dict) and "error" in v:
            errs.append(f"r{r} {k}: {v['error']}")
if errs:
    print("\n错误项：")
    for e in errs:
        print("  -", e)
