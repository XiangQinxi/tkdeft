"""真实界面目视验收：把各种组件摆出来截图，逐个引擎对比。

用法::

    python benchmarks/visual_demo.py --engine skia
    python benchmarks/visual_demo.py --all
"""

from __future__ import annotations

import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

OUT = os.path.join(_HERE, "_out")
os.makedirs(OUT, exist_ok=True)


def build(engine: str):
    import tkinter as tk  # noqa: F401

    import tkflu
    from tkflu.listbox import FluListBox

    tkflu.set_renderer(engine) if hasattr(tkflu, "set_renderer") else None

    win = tkflu.FluWindow()
    win.title(f"tkfluent · {engine}")
    win.geometry("560x420+80+80")
    win.configure(background="#f3f3f3")

    pad = dict(padx=16, pady=6)

    tkflu.FluLabel(win, text=f"渲染引擎：{engine}").pack(anchor="w", **pad)

    row = tkflu.FluFrame(win, width=520, height=90)
    row.pack(**pad)
    inner = tkflu.FluFrame(row, width=480, height=60)
    tkflu.FluButton(inner, text="标准按钮", width=110).pack(side="left", padx=6, pady=10)
    tkflu.FluButton(inner, text="强调", style="accent", width=90).pack(side="left", padx=6, pady=10)
    tkflu.FluButton(inner, text="菜单", style="menu", width=80).pack(side="left", padx=6, pady=10)
    tkflu.FluButton(inner, text="禁用", state="disabled", width=80).pack(side="left", padx=6, pady=10)
    inner.pack()

    line = tkflu.FluFrame(win, width=520, height=64)
    line.pack(**pad)
    strip = tkflu.FluFrame(line, width=480, height=40)
    tkflu.FluBadge(strip, text="徽标").pack(side="left", padx=8, pady=6)
    tkflu.FluToggleButton(strip, text="开关", width=90).pack(side="left", padx=8, pady=6)
    tkflu.FluSlider(strip, width=140).pack(side="left", padx=8, pady=6)
    tkflu.FluScrollBar(strip, width=120).pack(side="left", padx=8, pady=6)
    strip.pack()

    tkflu.FluEntry(win, width=300).pack(anchor="w", **pad)
    tkflu.FluText(win, width=300, height=70).pack(anchor="w", **pad)
    FluListBox(win, width=300, height=60).pack(anchor="w", **pad)

    return win


def grab(win, path):
    """把窗口抬到最前并等它画完，再截屏。"""
    import time

    win.deiconify()
    win.lift()
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    # 让 Tk 走完布局与首帧绘制（FluFrame 的内容是异步铺上去的）
    for _ in range(40):
        win.update()
        time.sleep(0.02)

    target = None
    try:
        from PIL import ImageGrab

        x = win.winfo_rootx()
        y = win.winfo_rooty()
        w = win.winfo_width()
        h = win.winfo_height()
        # 多抓几次，避免抓到还没绘制的黑帧
        best = None
        for _ in range(6):
            win.update()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            colors = img.convert("RGB").getcolors(maxcolors=1 << 20)
            score = len(colors) if colors else 0
            if best is None or score > best[0]:
                best = (score, img)
            time.sleep(0.05)
        img = best[1]
        img.save(path)
        target = f"{img.width}x{img.height} 色彩数={best[0]} -> {os.path.basename(path)}"
    except Exception as exc:
        target = f"截图失败：{type(exc).__name__}: {exc}"
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="skia")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    import tkdeft.engines as eng

    engines = ([n for n, ok in eng.list_engines().items() if ok]
               if args.all else [args.engine])

    for name in engines:
        win = build(name)
        info = grab(win, os.path.join(OUT, f"ui_{name}.png"))
        print(f"[{name:7s}] {info}")
        try:
            win.destroy()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
