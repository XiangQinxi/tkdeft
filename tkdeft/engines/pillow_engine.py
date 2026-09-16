"""Pillow 绘制引擎（零额外依赖的进程内栅格化）。

Pillow 本来就是 tkdeft 的硬依赖，所以这个引擎**永远可用**——即使目标机器上
没有 skia-python / pycairo，也能享受"不落盘、不解析 SVG"的加速。

``ImageDraw`` 本身不做抗锯齿，因此这里采用**超采样**：按 ``scale`` 倍尺寸绘制，
再用 LANCZOS 缩回目标尺寸。缩放倍率随面积自适应，保证大尺寸圆角（如 FluFrame）
不会因为超采样而变慢。

渐变描边 / 渐变填充的实现方式：先画一张灰度遮罩，再用 numpy 生成一列竖直方向的
线性渐变色，最后用遮罩调制 alpha 合成。语义与既有的 svgwrite 实现保持一致。
"""

from __future__ import annotations

from .base import DrawEngine, RoundRectSpec, ThumbSpec, TrackSpec
from .colors import parse_color

__all__ = ["PillowEngine"]


def _supersample_for(width: int, height: int) -> int:
    """按面积选择超采样倍率：小控件追求画质，大控件追求速度。"""
    area = max(1, width * height)
    if area <= 64 * 64:
        return 4
    if area <= 220 * 220:
        return 3
    if area <= 520 * 520:
        return 2
    return 1


class PillowEngine(DrawEngine):
    """基于 Pillow + numpy 的进程内栅格引擎。"""

    name = "pillow"
    kind = "raster"
    requires = ("PIL", "numpy")
    description = "Pillow 超采样栅格化（无额外依赖，永远可用）"

    def __init__(self, supersample: "int | None" = None) -> None:
        #: 固定超采样倍率；``None`` 表示按面积自适应
        self.supersample = supersample

    # ------------------------------------------------------------------
    def _scale_for(self, width: int, height: int) -> int:
        if self.supersample is not None:
            return max(1, int(self.supersample))
        return _supersample_for(width, height)

    @staticmethod
    def _gradient_column(height, y0, y1, c1, c2, stop1, stop2):
        """生成 ``(height, 4)`` 的竖直渐变列，stop 之外按 SVG 语义外推。"""
        import numpy as np

        ys = np.arange(height, dtype=np.float64)
        span = (y1 - y0) or 1.0
        t = (ys - y0) / span
        stop_span = (stop2 - stop1) or 1.0
        u = np.clip((t - stop1) / stop_span, 0.0, 1.0)
        a = np.asarray(c1, dtype=np.float64)
        b = np.asarray(c2, dtype=np.float64)
        return a[None, :] + (b - a)[None, :] * u[:, None]

    def _paint_gradient(self, size, mask, column):
        """用渐变列 + 灰度遮罩生成一层 RGBA 图像。"""
        import numpy as np
        from PIL import Image

        width, height = size
        rgba = np.repeat(column[:, None, :], width, axis=1)
        alpha = rgba[:, :, 3] * (np.asarray(mask, dtype=np.float64) / 255.0)
        rgba[:, :, 3] = alpha
        return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")

    # ------------------------------------------------------------------
    # 圆角矩形
    # ------------------------------------------------------------------
    def render_roundrect(self, spec: RoundRectSpec):
        from PIL import Image, ImageDraw

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        s = self._scale_for(width, height)
        W, H = width * s, height * s

        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        stroke_width = float(spec.outline_width or 0.0)
        inset = stroke_width / 2.0 if stroke_width > 0 else 0.0
        rx = max(0.0, float(spec.rx) - inset)
        # 注意：Pillow 的 rounded_rectangle 只接受**一个**圆角半径，所以
        # spec.effective_ry（y 方向半径）在这里用不上——这是引擎能力差异，
        # 不是漏算；需要椭圆圆角请用 skia / cairo / SVG 引擎。
        box = (
            inset * s,
            inset * s,
            W - 1 - inset * s,
            H - 1 - inset * s,
        )
        if box[2] <= box[0]:
            box = (box[0], box[1], box[0] + 1, box[3])
        if box[3] <= box[1]:
            box = (box[0], box[1], box[2], box[1] + 1)
        radius = min(rx * s, (box[2] - box[0]) / 2.0, (box[3] - box[1]) / 2.0)

        # -- 填充 --
        fill = parse_color(spec.fill, spec.fill_opacity)
        if fill:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle(
                box, radius=radius, fill=fill
            )
            base = Image.alpha_composite(base, layer)

        # -- 描边 --
        if stroke_width > 0:
            outline = parse_color(spec.outline, spec.outline_opacity)
            outline2 = (
                parse_color(spec.outline2, spec.outline2_opacity)
                if spec.outline2
                else None
            )
            line_width = max(1, int(round(stroke_width * s)))
            if outline2 and outline2 != outline:
                mask = Image.new("L", (W, H), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    box, radius=radius, outline=255, width=line_width
                )
                column = self._gradient_column(
                    H, inset * s, H - inset * s, outline, outline2,
                    spec.gradient_stop1, spec.gradient_stop2,
                )
                base = Image.alpha_composite(
                    base, self._paint_gradient((W, H), mask, column)
                )
            elif outline:
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(layer).rounded_rectangle(
                    box, radius=radius, outline=outline, width=line_width
                )
                base = Image.alpha_composite(base, layer)

        if s != 1:
            base = base.resize((width, height), Image.LANCZOS)
        return base

    # ------------------------------------------------------------------
    # 滑块进度条槽
    # ------------------------------------------------------------------
    def render_track(self, spec: TrackSpec):
        from PIL import Image, ImageDraw

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        s = self._scale_for(width, height)
        W, H = width * s, height * s
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        left = max(0.0, min(float(spec.width2), float(width))) * s
        radius = max(0.0, float(spec.radius) * s)

        def _block(x0, x1, color):
            nonlocal base
            if x1 <= x0 or color is None:
                return
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            r = min(radius, (x1 - x0) / 2.0, H / 2.0)
            ImageDraw.Draw(layer).rounded_rectangle(
                (x0, 0, x1 - 1, H - 1), radius=r, fill=color
            )
            base = Image.alpha_composite(base, layer)

        _block(0.0, left, parse_color(spec.track_fill, spec.track_opacity))
        _block(left, float(W), parse_color(spec.rail_fill, spec.rail_opacity))

        if s != 1:
            base = base.resize((width, height), Image.LANCZOS)
        return base

    # ------------------------------------------------------------------
    # 滑块把手
    # ------------------------------------------------------------------
    def render_thumb(self, spec: ThumbSpec):
        from PIL import Image, ImageDraw

        width = max(1, int(round(spec.width)))
        height = max(1, int(round(spec.height)))
        s = self._scale_for(width, height)
        W, H = width * s, height * s
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r1 = float(spec.r1) * s
        r2 = float(spec.r2) * s
        cx, cy = W / 2.0, H / 2.0

        def _circle(radius, color):
            nonlocal base
            if color is None or radius <= 0:
                return
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse(
                (cx - radius, cy - radius, cx + radius, cy + radius), fill=color
            )
            base = Image.alpha_composite(base, layer)

        # 外圈伪阴影：竖直渐变
        outline = parse_color(spec.outline, spec.outline_opacity)
        outline2 = (
            parse_color(spec.outline2, spec.outline2_opacity)
            if spec.outline2
            else None
        )
        if outline:
            if outline2 and outline2 != outline:
                mask = Image.new("L", (W, H), 0)
                ImageDraw.Draw(mask).ellipse(
                    (cx - r1, cy - r1, cx + r1, cy + r1), fill=255
                )
                column = self._gradient_column(
                    H, 1.0 * s, (float(spec.r1) * 2.0 - 1.0) * s,
                    outline, outline2, 0.500208, 0.954545,
                )
                base = Image.alpha_composite(
                    base, self._paint_gradient((W, H), mask, column)
                )
            else:
                _circle(r1, outline)

        _circle(r1 - s, parse_color(spec.fill, spec.fill_opacity))
        _circle(r2, parse_color(spec.inner_fill, spec.inner_fill_opacity))

        if s != 1:
            base = base.resize((width, height), Image.LANCZOS)
        return base
