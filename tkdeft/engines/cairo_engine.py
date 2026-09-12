"""Cairo 绘制引擎（pycairo，进程内栅格化）。

第三个栅格后端，用于验证引擎层的可插拔性：换成 pycairo 时上层组件代码
一行都不用改。cairo 的 ``ImageSurface(FORMAT_ARGB32)`` 在小端机器上内存布局
是 **预乘的 BGRA**，因此这里需要还原预乘再交给 Pillow。

cairo 没有原生的圆角矩形，这里用四段三次贝塞尔构造椭圆圆角
（``kappa = 0.5522847498``），与 SVG 的 ``rx`` / ``ry`` 语义一致。
"""

from __future__ import annotations

import math

from .base import DrawEngine, RoundRectSpec, ThumbSpec, TrackSpec
from .colors import parse_color

__all__ = ["CairoEngine"]

_KAPPA = 0.5522847498307936


def _rounded_rect_path(ctx, x, y, w, h, rx, ry):
    """往 cairo 上下文里追加一条椭圆圆角矩形路径。"""
    rx = max(0.0, min(rx, w / 2.0))
    ry = max(0.0, min(ry, h / 2.0))
    ctx.new_sub_path()
    if rx <= 0 and ry <= 0:
        ctx.rectangle(x, y, w, h)
        return
    kx, ky = _KAPPA * rx, _KAPPA * ry
    ctx.move_to(x + rx, y)
    ctx.line_to(x + w - rx, y)
    ctx.curve_to(x + w - rx + kx, y, x + w, y + ry - ky, x + w, y + ry)
    ctx.line_to(x + w, y + h - ry)
    ctx.curve_to(x + w, y + h - ry + ky, x + w - rx + kx, y + h, x + w - rx, y + h)
    ctx.line_to(x + rx, y + h)
    ctx.curve_to(x + rx - kx, y + h, x, y + h - ry + ky, x, y + h - ry)
    ctx.line_to(x, y + ry)
    ctx.curve_to(x, y + ry - ky, x + rx - kx, y, x + rx, y)
    ctx.close_path()


class CairoEngine(DrawEngine):
    """基于 pycairo 的进程内栅格引擎。"""

    name = "cairo"
    kind = "raster"
    requires = ("cairo", "numpy", "PIL")
    description = "pycairo 进程内栅格化（原生抗锯齿）"

    # ------------------------------------------------------------------
    @staticmethod
    def _new_surface(width: int, height: int):
        import cairo

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.set_antialias(cairo.ANTIALIAS_DEFAULT)
        return surface, ctx

    @staticmethod
    def _to_pil(surface, width: int, height: int):
        """ARGB32（预乘 BGRA）→ 非预乘 RGBA 的 ``PIL.Image``。"""
        import numpy as np
        from PIL import Image

        surface.flush()
        stride = surface.get_stride()
        raw = np.frombuffer(
            surface.get_data(), dtype=np.uint8, count=stride * height
        ).reshape(height, stride)
        arr = raw[:, : width * 4].reshape(height, width, 4)

        alpha = arr[:, :, 3].astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.where(alpha > 0, 255.0 / np.maximum(alpha, 1.0), 0.0)
        # 三个通道都必须乘上 scale 才能还原预乘；漏掉任何一个都会让半透明彩色
        # 像素偏色（曾经漏掉 G，导致黑色 20% 描边渲染成洋红色）。
        out = np.empty((height, width, 4), dtype=np.uint8)
        out[:, :, 0] = np.clip(arr[:, :, 2] * scale, 0, 255)  # R ← B
        out[:, :, 1] = np.clip(arr[:, :, 1] * scale, 0, 255)  # G
        out[:, :, 2] = np.clip(arr[:, :, 0] * scale, 0, 255)  # B ← R
        out[:, :, 3] = arr[:, :, 3]
        return Image.fromarray(out, "RGBA")

    @staticmethod
    def _set_color(ctx, rgba):
        ctx.set_source_rgba(
            rgba[0] / 255.0, rgba[1] / 255.0, rgba[2] / 255.0, rgba[3] / 255.0
        )

    # ------------------------------------------------------------------
    def render_roundrect(self, spec: RoundRectSpec):
        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, ctx = self._new_surface(width, height)

        stroke_width = float(spec.outline_width or 0.0)
        inset = stroke_width / 2.0 if stroke_width > 0 else 0.0
        rx = max(0.0, float(spec.rx) - inset)
        ry = max(0.0, float(spec.effective_ry) - inset)
        x0, y0 = inset, inset
        w = max(1.0, width - 2 * inset)
        h = max(1.0, height - 2 * inset)

        fill = parse_color(spec.fill, spec.fill_opacity)
        if fill:
            _rounded_rect_path(ctx, x0, y0, w, h, rx, ry)
            self._set_color(ctx, fill)
            ctx.fill()

        if stroke_width > 0:
            outline = parse_color(spec.outline, spec.outline_opacity)
            outline2 = (
                parse_color(spec.outline2, spec.outline2_opacity)
                if spec.outline2
                else None
            )
            if outline:
                if outline2 and outline2 != outline:
                    import cairo

                    gradient = cairo.LinearGradient(x0, y0, x0, y0 + h)
                    gradient.add_color_stop_rgba(
                        float(spec.gradient_stop1),
                        outline[0] / 255.0, outline[1] / 255.0,
                        outline[2] / 255.0, outline[3] / 255.0,
                    )
                    gradient.add_color_stop_rgba(
                        float(spec.gradient_stop2),
                        outline2[0] / 255.0, outline2[1] / 255.0,
                        outline2[2] / 255.0, outline2[3] / 255.0,
                    )
                    ctx.set_source(gradient)
                else:
                    self._set_color(ctx, outline)
                _rounded_rect_path(ctx, x0, y0, w, h, rx, ry)
                ctx.set_line_width(stroke_width)
                ctx.stroke()

        return self._to_pil(surface, width, height)

    # ------------------------------------------------------------------
    def render_track(self, spec: TrackSpec):
        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, ctx = self._new_surface(width, height)
        radius = max(0.0, float(spec.radius))
        left = max(0.0, min(float(spec.width2), float(width)))

        track = parse_color(spec.track_fill, spec.track_opacity)
        if track and left > 0:
            _rounded_rect_path(ctx, 0, 0, left, height, radius, radius)
            self._set_color(ctx, track)
            ctx.fill()

        rail = parse_color(spec.rail_fill, spec.rail_opacity)
        if rail and width - left > 0:
            _rounded_rect_path(ctx, left, 0, width - left, height, radius, radius)
            self._set_color(ctx, rail)
            ctx.fill()

        return self._to_pil(surface, width, height)

    # ------------------------------------------------------------------
    def render_thumb(self, spec: ThumbSpec):
        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        surface, ctx = self._new_surface(width, height)
        cx, cy = width / 2.0, height / 2.0
        r1, r2 = float(spec.r1), float(spec.r2)

        outline = parse_color(spec.outline, spec.outline_opacity)
        outline2 = (
            parse_color(spec.outline2, spec.outline2_opacity)
            if spec.outline2
            else None
        )
        if outline:
            import cairo

            if outline2 and outline2 != outline:
                gradient = cairo.LinearGradient(
                    r1, 1.0, r1, max(1.0, r1 * 2.0 - 1.0)
                )
                gradient.add_color_stop_rgba(
                    0.500208,
                    outline[0] / 255.0, outline[1] / 255.0,
                    outline[2] / 255.0, outline[3] / 255.0,
                )
                gradient.add_color_stop_rgba(
                    0.954545,
                    outline2[0] / 255.0, outline2[1] / 255.0,
                    outline2[2] / 255.0, outline2[3] / 255.0,
                )
                ctx.set_source(gradient)
            else:
                self._set_color(ctx, outline)
            ctx.arc(cx, cy, r1, 0, 2 * math.pi)
            ctx.fill()

        fill = parse_color(spec.fill, spec.fill_opacity)
        if fill:
            self._set_color(ctx, fill)
            ctx.arc(cx, cy, max(0.0, r1 - 1.0), 0, 2 * math.pi)
            ctx.fill()

        inner = parse_color(spec.inner_fill, spec.inner_fill_opacity)
        if inner:
            self._set_color(ctx, inner)
            ctx.arc(cx, cy, r2, 0, 2 * math.pi)
            ctx.fill()

        return self._to_pil(surface, width, height)
