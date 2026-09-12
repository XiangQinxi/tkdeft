"""优化前后对比表。

``result_before.json`` 是在 site-packages 上跑出来的——那里的 tkdeft / tkfluent
与仓库原始代码**逐字节相同**（已用文件哈希核对过），因此它代表真正的"优化前"。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


COLS = [
    ("before", "优化前(tksvg)", "result_before.json"),
    ("after_tksvg", "优化后·tksvg", "result_after_tksvg.json"),
    ("after_skia", "优化后·skia", "result_after_skia.json"),
]
data = {key: load(fn) for key, _, fn in COLS}

LABELS = {
    "svg_gen": "SVG 生成+落盘",
    "svg_raster": "tksvg 栅格化",
    "roundrect_vary": "圆角矩形(尺寸各异)",
    "roundrect_same": "圆角矩形(参数相同)",
    "button_draw": "FluButton 重绘",
    "button_hover": "按钮 hover 往返",
    "batch_20": "20 个按钮批量重绘",
}

rows = [k for k in (data["before"] or {}) if k in LABELS]

head = f"{'测试项':24s}" + "".join(f"{title:>18s}" for _, title, _ in COLS) + f"{'skia 提升':>14s}"
print(head)
print("-" * len(head))
for key in rows:
    line = f"{LABELS[key]:24s}"
    values = {}
    for col, _, _ in COLS:
        d = data.get(col) or {}
        v = d.get(key, {})
        if isinstance(v, dict) and "mean_ms" in v:
            values[col] = v["mean_ms"]
            line += f"{v['mean_ms']:18.4f}"
        else:
            line += f"{'n/a':>18s}"
    if "before" in values and "after_skia" in values and values["after_skia"] > 0:
        line += f"{values['before'] / values['after_skia']:13.1f}x"
    print(line)

print()
print("单位：毫秒/次（越小越好）。提升倍数 = 优化前 ÷ 优化后(skia)。")
