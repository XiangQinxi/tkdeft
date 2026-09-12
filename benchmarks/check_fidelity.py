"""保真度对比：同一 spec 分别用 tksvg（现状）与各栅格引擎渲染，逐像素比对。

关注两件事：
1. 视觉上是否一致（输出拼图 PNG 供目视）；
2. 平均/最大像素差是否在合理范围（抗锯齿实现不同，允许边缘有差异）。
"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import tkinter  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from tkdeft.engines import RoundRectSpec, get_engine, set_engine  # noqa: E402

OUT = os.path.join(_HERE, "_out")
os.makedirs(OUT, exist_ok=True)

root = tkinter.Tk()
root.withdraw()

# --- 用现有 svgwrite + tksvg 路径渲染作为参照 ---
from svgwrite import Drawing  # noqa: E402
from tksvg import SvgImage  # noqa: E402

from tkdeft.svg import add_roundrect  # noqa: E402


def render_svg_reference(spec: RoundRectSpec) -> Image.Image:
    """用 tkdeft 的 SVG 形状助手生成参考图（与 tkfluent 实际走的路径一致）。"""
    w, h = spec.width, spec.height
    dwg = Drawing(size=(w, h))
    add_roundrect(
        dwg,
        0, 0, w, h,
        spec.rx,
        spec.effective_ry,
        fill=spec.fill or "transparent",
        fill_opacity=spec.fill_opacity,
        outline=spec.outline or "none",
        outline2=spec.outline2,
        outline_opacity=spec.outline_opacity,
        width=spec.outline_width,
    )
    svg = dwg.tostring()
    img = SvgImage(data=svg, master=root)
    tmp = os.path.join(OUT, "_ref_tmp.png")
    img.write(tmp, format="png")
    return Image.open(tmp).convert("RGBA")


SPEC = RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff",
                     outline="#000000", outline_opacity=0.2, outline_width=1)
SPEC2 = RoundRectSpec(width=64, height=32, rx=16, fill="#005fb8",
                      outline="#FFFFFF", outline_opacity=0.08, outline_width=1)

SCALE = 6


def upscale(img: Image.Image) -> Image.Image:
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


for tag, spec in (("white", SPEC), ("pill", SPEC2)):
    ref = render_svg_reference(spec)
    panels = [("tksvg(现状)", ref)]
    for name in ("skia", "pillow", "cairo"):
        set_engine(name)
        panels.append((name, get_engine().render_roundrect(spec)))

    # 逐像素差异
    print(f"\n=== {tag} {spec.width}x{spec.height} rx={spec.rx} ===")
    ref_arr = np.asarray(ref, dtype=np.int16)
    for name, img in panels[1:]:
        arr = np.asarray(img, dtype=np.int16)
        if arr.shape != ref_arr.shape:
            print(f"  {name:7s} 尺寸不一致 {arr.shape} vs {ref_arr.shape}")
            continue
        diff = np.abs(arr - ref_arr)
        print(f"  {name:7s} 平均差={diff.mean():6.2f}  最大差={diff.max():3d}  "
              f"差异像素占比={(diff.max(axis=2) > 8).mean() * 100:5.2f}%")

    # 拼图（放大后用最近邻，便于看清边缘）
    gap = 8
    ups = [upscale(img) for _, img in panels]
    total_w = sum(u.width for u in ups) + gap * (len(ups) + 1)
    total_h = max(u.height for u in ups) + gap * 2 + 16
    sheet = Image.new("RGBA", (total_w, total_h), (240, 240, 240, 255))
    x = gap
    draw = ImageDraw.Draw(sheet)
    for (label, _), u in zip(panels, ups):
        sheet.alpha_composite(u, (x, gap + 16))
        draw.text((x, gap), label, fill=(0, 0, 0, 255))
        x += u.width + gap
    path = os.path.join(OUT, f"compare_{tag}.png")
    sheet.convert("RGB").save(path)
    print(f"  拼图: {path}")

root.destroy()
print("\n完成")
