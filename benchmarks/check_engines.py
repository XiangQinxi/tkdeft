"""引擎层自检：逐个引擎渲染同一组图元，输出 PNG 供目视比对，并做自洽断言。"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tkdeft.engines import (  # noqa: E402
    RoundRectSpec, ThumbSpec, TrackSpec, get_engine, list_engines, set_engine,
)
from tkdeft.engines import skia_engine, pillow_engine, cairo_engine  # noqa: E402

OUT = os.path.join(_HERE, "_out")
os.makedirs(OUT, exist_ok=True)

SPECS = {
    "white": RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff",
                           outline="#000000", outline_opacity=0.2, outline_width=1),
    "alpha_fill": RoundRectSpec(width=120, height=32, rx=6, fill="#000000",
                                fill_opacity=0.22, outline="#FFFFFF",
                                outline_opacity=0.08, outline_width=1),
    "gradient_border": RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff",
                                     outline="#000000", outline_opacity=0.3,
                                     outline2="#ff0000", outline2_opacity=1.0,
                                     outline_width=1),
    "no_border": RoundRectSpec(width=120, height=32, rx=6, fill="#eaeaea",
                               outline_width=0),
    "pill": RoundRectSpec(width=64, height=32, rx=16, fill="#005fb8",
                          outline="#FFFFFF", outline_opacity=0.08, outline_width=1),
    "big": RoundRectSpec(width=300, height=200, rx=8, fill="#ffffff",
                         outline="#000000", outline_opacity=0.2, outline_width=1),
}

THUMB = ThumbSpec(width=28, height=28, r1=8, r2=3, fill="#ffffff",
                  fill_opacity=1, outline="#000000", outline_opacity=0.5,
                  outline2="#000000", outline2_opacity=0.05,
                  inner_fill="#005fb8", inner_fill_opacity=1)
TRACK = TrackSpec(width=70, height=4, width2=35, radius=2,
                  track_fill="#005fb8", track_opacity=1,
                  rail_fill="#000000", rail_opacity=0.2)

print("已注册引擎:", list_engines())

failures = []
for name in ("skia", "pillow", "cairo"):
    try:
        set_engine(name)
    except ValueError as exc:
        print(f"[跳过] {name}: {exc}")
        continue

    engine = get_engine()
    print(f"\n=== {engine.name} ({engine.description}) ===")
    for label, spec in list(SPECS.items()) + [("thumb", THUMB), ("track", TRACK)]:
        render = getattr(engine, f"render_{'roundrect' if isinstance(spec, RoundRectSpec) else 'thumb' if isinstance(spec, ThumbSpec) else 'track'}")
        try:
            img = render(spec)
        except Exception as exc:
            failures.append(f"{name}/{label}: {type(exc).__name__}: {exc}")
            print(f"  {label:18s} 失败 {type(exc).__name__}: {exc}")
            continue
        path = os.path.join(OUT, f"{name}_{label}.png")
        img.save(path)
        px = img.convert("RGBA").load()
        center = px[img.width // 2, img.height // 2]
        corner = px[0, 0]
        print(f"  {label:18s} {img.size} center={center} corner={corner} -> {os.path.basename(path)}")

# 通道序正确性：纯红填充必须是 (255, 0, 0, 255)
print("\n=== 颜色通道序校验（红/蓝不对称）===")
red = RoundRectSpec(width=8, height=8, rx=0, fill="#ff0000", outline_width=0)
blue = RoundRectSpec(width=8, height=8, rx=0, fill="#0000ff", outline_width=0)
for name in ("skia", "pillow", "cairo"):
    try:
        set_engine(name)
    except ValueError:
        continue
    engine = get_engine()
    r = engine.render_roundrect(red).convert("RGBA").getpixel((4, 4))
    b = engine.render_roundrect(blue).convert("RGBA").getpixel((4, 4))
    ok = r == (255, 0, 0, 255) and b == (0, 0, 255, 255)
    print(f"  {name:7s} red={r} blue={b} {'OK' if ok else '!!! 通道序错误'}")
    if not ok:
        failures.append(f"{name}: 颜色通道序错误 red={r} blue={b}")

# 半透明 alpha 是否被正确保留（非预乘）
print("\n=== alpha 保留校验（50% 黑）===")
half = RoundRectSpec(width=8, height=8, rx=0, fill="#000000", fill_opacity=0.5,
                     outline_width=0)
for name in ("skia", "pillow", "cairo"):
    try:
        set_engine(name)
    except ValueError:
        continue
    px = get_engine().render_roundrect(half).convert("RGBA").getpixel((4, 4))
    ok = abs(px[3] - 128) <= 2
    print(f"  {name:7s} pixel={px} {'OK' if ok else '!!! alpha 异常'}")
    if not ok:
        failures.append(f"{name}: alpha 期望 ~128，实际 {px}")

# 半透明彩色是否被正确解预乘（cairo 曾在此处把黑色描边渲染成洋红）
print("\n=== 解预乘校验（50% #3366cc，期望 ≈(51,102,204,128)）===")
tinted = RoundRectSpec(width=8, height=8, rx=0, fill="#3366cc", fill_opacity=0.5,
                       outline_width=0)
for name in ("skia", "pillow", "cairo"):
    try:
        set_engine(name)
    except ValueError:
        continue
    px = get_engine().render_roundrect(tinted).convert("RGBA").getpixel((4, 4))
    ok = all(abs(px[i] - v) <= 3 for i, v in enumerate((51, 102, 204))) and abs(px[3] - 128) <= 2
    print(f"  {name:7s} pixel={px} {'OK' if ok else '!!! 解预乘错误'}")
    if not ok:
        failures.append(f"{name}: 解预乘错误，期望 (51,102,204,~128)，实际 {px}")

# 描边是否画全四条边（tksvg 的旧实现会把下/右边框裁掉）
print("\n=== 四边描边完整性校验 ===")
framed = RoundRectSpec(width=40, height=24, rx=4, fill="#ffffff",
                       outline="#000000", outline_opacity=1.0, outline_width=1)
for name in ("skia", "pillow", "cairo"):
    try:
        set_engine(name)
    except ValueError:
        continue
    img = get_engine().render_roundrect(framed).convert("RGBA")
    px = img.load()
    edges = {
        "top": px[20, 0][0], "bottom": px[20, 23][0],
        "left": px[0, 12][0], "right": px[39, 12][0],
    }
    ok = all(v < 128 for v in edges.values())
    print(f"  {name:7s} {edges} {'OK' if ok else '!!! 有边缺失'}")
    if not ok:
        failures.append(f"{name}: 描边缺失 {edges}")

print()
if failures:
    print("失败项:")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("全部引擎自检通过 ✅")

