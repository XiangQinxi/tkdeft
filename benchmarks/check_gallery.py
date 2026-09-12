"""设计稿画廊：用 tkfluent 真实的 design 配色，把各引擎的渲染结果并排出来。

这是最贴近"用户实际看到什么"的验证——配色、透明度、圆角、渐变故边全部取自
``tkflu.designs.button`` 的返回值，而不是手写的测试数据。

用法::

    python benchmarks/check_gallery.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import tkinter  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

from tkdeft.engines import RoundRectSpec, get_engine, set_engine  # noqa: E402
from tkflu.designs.badge import badge as badge_design  # noqa: E402
from tkflu.designs.button import button as button_design  # noqa: E402

OUT = os.path.join(_HERE, "_out")
os.makedirs(OUT, exist_ok=True)

root = tkinter.Tk()
root.withdraw()

ENGINES = ["tksvg", "skia", "pillow", "cairo"]
BW, BH = 132, 34
SCALE = 3

# 与 FluButton._draw 一致的背景（浅色主题窗口底色）
BG = (243, 243, 243)


def spec_from_design(d, w=BW, h=BH):
    """把 design 字典转成引擎的 RoundRectSpec。"""
    def op(v, default=1.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return RoundRectSpec(
        width=w,
        height=h,
        rx=float(d.get("radius") or 0),
        fill=d.get("back_color"),
        fill_opacity=op(d.get("back_opacity")),
        outline=d.get("border_color"),
        outline_opacity=op(d.get("border_color_opacity")),
        outline2=d.get("border_color2"),
        outline2_opacity=op(d.get("border_color2_opacity")),
        outline_width=float(d.get("border_width") or 0),
    )


def render_engine(name, spec):
    """渲染一个 spec；``tksvg`` 是 SVG 引擎，走 svgwrite + tksvg 的实际路径。"""
    if name == "tksvg":
        return render_svg_reference(spec)
    set_engine(name)
    return get_engine().render_roundrect(spec)


def render_svg_reference(spec):
    """用库自身的 SVG 生成路径 + tksvg 出图，作为参照基准。"""
    from svgwrite import Drawing
    from tksvg import SvgImage

    from tkdeft.svg import add_roundrect

    dwg = Drawing(size=(spec.width, spec.height))
    add_roundrect(
        dwg, 0, 0, spec.width, spec.height, spec.rx, spec.effective_ry,
        fill=spec.fill or "transparent",
        fill_opacity=spec.fill_opacity,
        outline=spec.outline or "none",
        outline2=spec.outline2,
        outline_opacity=spec.outline_opacity,
        outline2_opacity=spec.outline2_opacity,
        width=spec.outline_width,
    )
    img = SvgImage(data=dwg.tostring(), master=root)
    tmp = os.path.join(OUT, "_gallery_ref.png")
    img.write(tmp, format="png")
    return Image.open(tmp).convert("RGBA")


def main() -> int:
    states = ("rest", "hover", "pressed", "disabled")
    cases = []
    for mode in ("light", "dark"):
        for style in ("standard", "accent", "menu"):
            for state in states:
                d = button_design(mode, style, state)
                cases.append((f"{mode[:1].upper()}-{style[:3]}-{state[:4]}", d, mode))

    # 每个引擎一张大图：行 = case，列 = 引擎
    cell_w, cell_h = BW * SCALE + 10, BH * SCALE + 10
    label_w = 132
    sheet = Image.new("RGB", (label_w + cell_w * len(ENGINES), 30 + cell_h * len(cases)), BG)
    draw = ImageDraw.Draw(sheet)

    for col, engine in enumerate(ENGINES):
        draw.text((label_w + col * cell_w + 6, 8), engine, fill=(0, 0, 0))

    for row, (label, design, mode) in enumerate(cases):
        y0 = 30 + row * cell_h
        draw.text((6, y0 + cell_h // 2 - 6), label, fill=(0, 0, 0))
        # 深色主题用深色底，否则看不出半透明白色描边
        backdrop = (32, 32, 32) if mode == "dark" else BG
        spec = spec_from_design(design)
        for col, engine in enumerate(ENGINES):
            x0 = label_w + col * cell_w + 5
            tile = Image.new("RGB", (BW * SCALE, BH * SCALE), backdrop)
            try:
                img = render_engine(engine, spec)
                tile.paste(img.resize((BW * SCALE, BH * SCALE), Image.NEAREST),
                           (0, 0), img.resize((BW * SCALE, BH * SCALE), Image.NEAREST))
            except Exception as exc:
                draw.text((x0 + 4, y0 + 8), f"ERR {type(exc).__name__}", fill=(255, 0, 0))
            sheet.paste(tile, (x0, y0 + 5))

    path = os.path.join(OUT, "gallery_buttons.png")
    sheet.save(path)
    print(f"按钮状态画廊（{len(cases)} 个状态 × {len(ENGINES)} 个引擎）-> {path}")

    # 逐引擎两两对比：与 tksvg 参考的差异
    print("\n各引擎相对 tksvg 的平均像素差（越小越一致）：")
    ref_engine = "tksvg"
    header = f"{'状态':14s}" + "".join(f"{e:>10s}" for e in ENGINES if e != ref_engine)
    print(header)
    worst = []
    for label, design, mode in cases:
        spec = spec_from_design(design)
        base = render_engine(ref_engine, spec)
        row = f"{label:14s}"
        for engine in ENGINES:
            if engine == ref_engine:
                continue
            img = render_engine(engine, spec)
            import numpy as np

            diff = float(np.abs(
                np.asarray(img, dtype=np.int16) - np.asarray(base, dtype=np.int16)
            ).mean())
            row += f"{diff:10.2f}"
            if diff > 12:
                worst.append((label, engine, diff))
        print(row)

    print()
    if worst:
        print("差异较大的项（>12）：")
        for label, engine, diff in worst:
            print(f"  - {label} / {engine}: {diff:.2f}")
    else:
        print("所有引擎与 tksvg 参考的平均像素差都 <= 12（差异来自抗锯齿实现不同）")

    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
