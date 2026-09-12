"""专项验证：PhotoImage 保活（画面空白问题）与 FluImage。

Tkinter 的 canvas item 不会替 Python 侧持有 ``PhotoImage`` 引用。旧代码只用
``self._img`` / ``self._tkimg`` 保存"最后一张"，因此同一画布上有多张图片时，
除最后一张外都会被垃圾回收，对应 item 变成空白。

这里通过"建多张 → 强制 GC → 逐张校验"来证明它确实修好了。
"""

from __future__ import annotations

import gc
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

failures = []


def check_multiple_images(engine):
    """同一画布上多张图片，GC 后都应存活。"""
    import tkinter as tk

    import tkflu
    from tkflu.designs.renderer import set_renderer
    from tkflu.button import FluButtonCanvas

    set_renderer(engine)
    root = tkflu.FluWindow()
    root.withdraw()

    cnv = FluButtonCanvas(root, width=400, height=120)
    cnv.pack()
    root.update()

    items = []
    for i in range(5):
        items.append(
            cnv.create_round_rectangle(
                0, 0, 60 + i * 10, 30,
                r1=6, fill="#ffffff", fill_opacity=1,
                outline="#000000", outline2=None,
                outline_opacity=0.2, outline2_opacity=1, width=1,
            )
        )
    root.update()

    # 反复 GC，逼出任何"只靠局部变量活着"的图片
    for _ in range(4):
        gc.collect()

    blank = []
    for idx, item in enumerate(items):
        try:
            img_name = cnv.itemcget(item, "image")
        except tk.TclError as exc:
            blank.append(f"#{idx} item 已失效: {exc}")
            continue
        if not img_name:
            blank.append(f"#{idx} item 没有绑定图片")
            continue
        try:
            w = int(cnv.tk.call("image", "width", img_name))
        except tk.TclError:
            blank.append(f"#{idx} 图片 {img_name} 已被回收")
            continue
        if w <= 1:
            blank.append(f"#{idx} 图片宽度异常: {w}")

    alive = len(items) - len(blank)
    print(f"  [{engine:7s}] 5 张图片 GC 后存活 {alive}/5")
    for line in blank:
        print(f"      !! {line}")
        failures.append(f"{engine}: {line}")

    try:
        root.destroy()
    except Exception:
        pass


def check_fluimage():
    """FluImage 之前是语法错误的空类，现在应可正常构造。"""
    from PIL import Image

    import tkflu
    from tkflu.image import FluImage

    root = tkflu.FluWindow()
    root.withdraw()

    path = os.path.join(_HERE, "_out", "_fluimage_src.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (48, 48), (0, 95, 184)).save(path)

    for engine in ("tksvg", "skia"):
        tkflu.set_renderer(engine) if hasattr(tkflu, "set_renderer") else None
        from tkflu.designs.renderer import set_renderer

        set_renderer(engine)
        try:
            widget = FluImage(root, image=path)
            widget.pack()
            root.update()
            got = widget.image()
            w, h = got.width(), got.height()
            ok = (w, h) == (48, 48)
            print(f"  [{engine:7s}] FluImage 构造成功，图片 {w}x{h} {'OK' if ok else '!! 尺寸不对'}")
            if not ok:
                failures.append(f"FluImage@{engine}: 尺寸 {w}x{h}")
        except Exception as exc:
            print(f"  [{engine:7s}] FluImage 失败: {type(exc).__name__}: {exc}")
            failures.append(f"FluImage@{engine}: {type(exc).__name__}: {exc}")

    try:
        root.destroy()
    except Exception:
        pass


import tkdeft.engines as eng  # noqa: E402

available = [name for name, ok in eng.list_engines().items() if ok]

print("=== 多图片保活（GC 后不空白）===")
for name in available:
    check_multiple_images(name)

print("\n=== FluImage ===")
check_fluimage()

print()
if failures:
    print(f"失败 {len(failures)} 项：")
    for line in failures:
        print("  -", line)
    raise SystemExit(1)
print("专项验证通过")
