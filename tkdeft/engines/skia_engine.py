"""Skia 绘制引擎（skia-python，进程内栅格化）。

为什么快
--------
旧路径：svgwrite 拼 XML → 写临时文件 → tksvg 读文件、解析 XML、光栅化 → PhotoImage。
新路径：直接在一块 CPU 位图上画 AntiAlias 的 RRect → 快照 → numpy → PIL → PhotoImage。

实测（120×32 圆角矩形，本机）::

    svgwrite + 落盘       0.44 ms
    tksvg 读文件 + 解析   1.53 ms
    mkstemp 临时文件       ~3.5 ms   ← 旧路径每次绘制都新建一个临时文件
    ------------------------------
    旧端到端              5.6 ms
    skia 端到端           0.20 ms   （再叠加 PhotoImage 缓存后可降到接近 0）

通道序自校准
------------
``skia.Image.toarray()`` 返回的是图像**原生**通道序（典型为 BGRA）且已解预乘，
不同 skia 构建下未必一致。这里在首次使用时画一个不对称颜色自检，
自动决定要不要交换 R/B 通道，避免"红色变蓝色"这类静默错误。
"""

from __future__ import annotations

import threading

from .base import DrawEngine, RoundRectSpec, ThumbSpec, TrackSpec
from .colors import parse_color

__all__ = ["SkiaEngine"]

_CALIBRATION_LOCK = threading.Lock()
#: None=未校准；True=需要交换 R/B（BGRA 原生序）
_NEEDS_BGRA_SWAP = None


def _to_pil(image):
    """把 ``skia.Image`` 转成 RGBA 的 ``PIL.Image``（自动处理通道序）。"""
    global _NEEDS_BGRA_SWAP
    import numpy as np
    from PIL import Image

    arr = image.toarray()
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise RuntimeError(f"skia 位图格式异常：shape={arr.shape}")

    if _NEEDS_BGRA_SWAP is None:
        with _CALIBRATION_LOCK:
            if _NEEDS_BGRA_SWAP is None:
                _NEEDS_BGRA_SWAP = _detect_bgra_swap()

    if _NEEDS_BGRA_SWAP:
        arr = arr[:, :, [2, 1, 0, 3]]
    return Image.fromarray(np.ascontiguousarray(arr), "RGBA")


def _detect_bgra_swap() -> bool:
    """画一个不对称颜色，判断 ``toarray`` 是否给出 BGRA。"""
    import skia

    surface = skia.Surface(2, 2)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    # R=10, G=20, B=30 —— 若读回 [30,20,10] 说明是 BGRA
    canvas.drawRect(
        skia.Rect.MakeXYWH(0, 0, 2, 2),
        skia.Paint(Color=skia.Color(10, 20, 30, 255)),
    )
    r, g, b, _a = (int(v) for v in surface.makeImageSnapshot().toarray()[1, 1])
    if (r, g, b) == (10, 20, 30):
        return False
    if (r, g, b) == (30, 20, 10):
        return True
    # 无法判定的异形构建：默认按业界惯例视为 BGRA
    return True


class SkiaEngine(DrawEngine):
    """基于 skia-python 的进程内栅格引擎。"""

    name = "skia"
    kind = "raster"
    requires = ("skia", "numpy", "PIL")
    description = "skia-python 进程内栅格化（无磁盘 I/O，抗锯齿质量高）"

    def _new_canvas(self, width: int, height: int):
        import skia

        surface = skia.Surface(width, height)
        canvas = surface.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        return surface, canvas

    # ------------------------------------------------------------------
    # 圆角矩形
    # ------------------------------------------------------------------
    def render_roundrect(self, spec: RoundRectSpec):
        import skia

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, canvas = self._new_canvas(width, height)

        stroke_width = float(spec.outline_width or 0.0)
        # SVG 的描边是居中的；把几何内缩半个线宽，描边外沿才正好贴合 0..width
        inset = stroke_width / 2.0 if stroke_width > 0 else 0.0
        rx = max(0.0, float(spec.rx) - inset)
        ry = max(0.0, float(spec.effective_ry) - inset)
        rect = skia.Rect.MakeXYWH(
            inset, inset, max(0.0, width - 2 * inset), max(0.0, height - 2 * inset)
        )
        rrect = skia.RRect.MakeRectXY(rect, rx, ry)

        fill = parse_color(spec.fill, spec.fill_opacity)
        if fill:
            canvas.drawRRect(
                rrect, skia.Paint(AntiAlias=True, Color=skia.Color(*fill))
            )

        if stroke_width > 0:
            paint = self._stroke_paint(spec, stroke_width, inset, height)
            if paint is not None:
                canvas.drawRRect(rrect, paint)

        return _to_pil(surface.makeImageSnapshot())

    def _stroke_paint(self, spec, stroke_width, inset, height):
        import skia

        outline = parse_color(spec.outline, spec.outline_opacity)
        if not outline:
            return None

        outline2 = (
            parse_color(spec.outline2, spec.outline2_opacity)
            if spec.outline2
            else None
        )
        paint = skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=stroke_width,
        )

        if outline2 and outline2 != outline:
            paint.setShader(
                skia.GradientShader.MakeLinear(
                    points=[(float(inset), float(inset)),
                            (float(inset), float(height - inset))],
                    colors=[skia.Color(*outline), skia.Color(*outline2)],
                    positions=[float(spec.gradient_stop1), float(spec.gradient_stop2)],
                )
            )
        else:
            paint.setColor(skia.Color(*outline))
        return paint

    # ------------------------------------------------------------------
    # 滑块进度条槽
    # ------------------------------------------------------------------
    def render_track(self, spec: TrackSpec):
        import skia

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, canvas = self._new_canvas(width, height)
        radius = max(0.0, float(spec.radius))

        left_w = max(0.0, min(float(spec.width2), float(width)))
        track = parse_color(spec.track_fill, spec.track_opacity)
        if track and left_w > 0:
            canvas.drawRRect(
                skia.RRect.MakeRectXY(
                    skia.Rect.MakeXYWH(0, 0, left_w, height), radius, radius
                ),
                skia.Paint(AntiAlias=True, Color=skia.Color(*track)),
            )

        rail = parse_color(spec.rail_fill, spec.rail_opacity)
        rail_w = width - left_w
        if rail and rail_w > 0:
            canvas.drawRRect(
                skia.RRect.MakeRectXY(
                    skia.Rect.MakeXYWH(left_w, 0, rail_w, height), radius, radius
                ),
                skia.Paint(AntiAlias=True, Color=skia.Color(*rail)),
            )

        return _to_pil(surface.makeImageSnapshot())

    # ------------------------------------------------------------------
    # 滑块把手
    # ------------------------------------------------------------------
    def render_thumb(self, spec: ThumbSpec):
        import skia

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, canvas = self._new_canvas(width, height)
        cx, cy = width / 2.0, height / 2.0
        r1 = float(spec.r1)
        r2 = float(spec.r2)

        outline = parse_color(spec.outline, spec.outline_opacity)
        outline2 = (
            parse_color(spec.outline2, spec.outline2_opacity)
            if spec.outline2
            else None
        )
        if outline:
            paint = skia.Paint(AntiAlias=True)
            if outline2 and outline2 != outline:
                # 与既有 SVG 实现一致：竖直线性渐变，stop 0.500208 / 0.954545
                paint.setShader(
                    skia.GradientShader.MakeLinear(
                        points=[(r1, 1.0), (r1, r1 * 2.0 - 1.0)],
                        colors=[skia.Color(*outline), skia.Color(*outline2)],
                        positions=[0.500208, 0.954545],
                    )
                )
            else:
                paint.setColor(skia.Color(*outline))
            canvas.drawCircle(cx, cy, r1, paint)

        fill = parse_color(spec.fill, spec.fill_opacity)
        if fill:
            canvas.drawCircle(
                cx, cy, max(0.0, r1 - 1.0),
                skia.Paint(AntiAlias=True, Color=skia.Color(*fill)),
            )

        inner = parse_color(spec.inner_fill, spec.inner_fill_opacity)
        if inner:
            canvas.drawCircle(
                cx, cy, r2, skia.Paint(AntiAlias=True, Color=skia.Color(*inner))
            )

        return _to_pil(surface.makeImageSnapshot())
