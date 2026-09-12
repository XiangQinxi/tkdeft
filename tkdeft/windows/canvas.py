"""带绘制能力的 Canvas。

本模块提供两条并存的绘制路径：

* **栅格快速路径**（:meth:`DCanvas.create_roundrect_raster`）：当当前引擎是
  skia / pillow / cairo 时，直接拿进程内渲染出的位图建 canvas item，
  不写临时文件、不解析 SVG，并且结果按 spec 缓存、可被多个控件共享。
* **SVG 兼容路径**（:meth:`DCanvas.create_round_rectangle`）：保持原样，
  供 tksvg / wand 引擎和自定义绘制代码使用。

另外修掉了一个经典陷阱：``PhotoImage`` 必须由 Python 侧持有引用，
否则一旦被垃圾回收，**画布上对应的 item 会变成空白**。旧代码只用
``self._tkimg`` 保存"最后一张"，同一画布上有多张图片时其余都会变空白。
"""

from __future__ import annotations

from tkinter import Canvas
from typing import Optional

from ..engines import (
    RoundRectSpec,
    ThumbSpec,
    TrackSpec,
    get_engine,
    parse_opacity,
    render_roundrect,
    render_thumb,
    render_track,
)

#: 超出该数量时清理已失效 item 的图片引用
_PHOTO_PRUNE_THRESHOLD = 256


class DCanvas(Canvas):
    from .draw import DSvgDraw

    draw = DSvgDraw

    def __init__(self, *args, border=0, highlightthickness=0, **kwargs):
        super().__init__(*args, border=border, highlightthickness=0, **kwargs)

        self.svgdraw = self.draw()
        # 把本画布作为 master 交给绘图后端，避免图片挂到别的 Tk 解释器上
        if hasattr(self.svgdraw, "master"):
            self.svgdraw.master = self
        #: canvas item id -> PhotoImage，防止图片被 GC 后画面变空白
        self._photo_refs = {}

        self.bind("<Destroy>", self._event_destroy_draw, add="+")

    # ------------------------------------------------------------------
    # 图片引用管理
    # ------------------------------------------------------------------
    def _keep_photo(self, item, photo):
        """持有 ``PhotoImage`` 引用，并在必要时清理已删除 item 的引用。"""
        self._photo_refs[item] = photo
        if len(self._photo_refs) > _PHOTO_PRUNE_THRESHOLD:
            self._prune_photo_refs()
        return item

    def _prune_photo_refs(self):
        stale = []
        for item in self._photo_refs:
            try:
                self.type(item)
            except Exception:
                stale.append(item)
        for item in stale:
            self._photo_refs.pop(item, None)

    def _event_destroy_draw(self, event=None):
        if event is not None and getattr(event, "widget", None) is not self:
            return
        self._photo_refs.clear()
        cleanup = getattr(self.svgdraw, "cleanup", None)
        if callable(cleanup):
            cleanup()

    # ------------------------------------------------------------------
    # 栅格快速路径
    # ------------------------------------------------------------------
    def create_roundrect_raster(
        self,
        x1,
        y1,
        x2,
        y2,
        r1,
        r2=None,
        *args,
        fill="transparent",
        fill_opacity=1,
        outline="black",
        outline2=None,
        outline_opacity=1,
        outline2_opacity=1,
        width=1,
        gradient_stop1=0.9,
        gradient_stop2=1.0,
        **image_kwargs,
    ) -> Optional[int]:
        """尝试用当前栅格引擎直接绘制圆角矩形。

        :returns: 成功时返回 canvas item id；当前引擎是 SVG 系、尺寸非法或
            渲染失败时返回 ``None``，调用方应回退到原有的 SVG 路径。
        """
        if not get_engine().is_raster:
            return None

        w = int(round(x2 - x1))
        h = int(round(y2 - y1))
        if w <= 0 or h <= 0:
            return None

        spec = RoundRectSpec(
            width=w,
            height=h,
            rx=float(r1 or 0),
            ry=None if r2 is None else float(r2),
            fill=fill,
            fill_opacity=parse_opacity(fill_opacity),
            outline=outline,
            outline_opacity=parse_opacity(outline_opacity),
            outline2=outline2,
            outline2_opacity=parse_opacity(outline2_opacity),
            outline_width=float(width or 0),
            gradient_stop1=float(gradient_stop1),
            gradient_stop2=float(gradient_stop2),
        )
        photo = render_roundrect(spec, self)
        if photo is None:
            return None

        item = self.create_image(x1, y1, anchor="nw", image=photo, *args, **image_kwargs)
        return self._keep_photo(item, photo)

    # ------------------------------------------------------------------
    # 滑块专用图元的栅格快速路径
    # ------------------------------------------------------------------
    def create_track_raster(
        self,
        x1,
        y1,
        width,
        height,
        width2,
        radius=3,
        track_fill="transparent",
        track_opacity=1,
        rail_fill="transparent",
        rail_opacity=1,
        **image_kwargs,
    ):
        """滑块的进度条槽；不支持时返回 ``None``。"""
        if not get_engine().is_raster:
            return None

        w = int(round(width))
        h = int(round(height))
        if w <= 0 or h <= 0:
            return None

        spec = TrackSpec(
            width=w,
            height=h,
            width2=float(width2),
            radius=float(radius or 0),
            track_fill=track_fill,
            track_opacity=parse_opacity(track_opacity),
            rail_fill=rail_fill,
            rail_opacity=parse_opacity(rail_opacity),
        )
        photo = render_track(spec, self)
        if photo is None:
            return None
        item = self.create_image(x1, y1, anchor="nw", image=photo, **image_kwargs)
        return self._keep_photo(item, photo)

    def create_thumb_raster(
        self,
        x1,
        y1,
        width,
        height,
        r1,
        r2,
        fill="transparent",
        fill_opacity=1,
        outline="transparent",
        outline_opacity=1,
        outline2="transparent",
        outline2_opacity=1,
        inner_fill="transparent",
        inner_fill_opacity=1,
        **image_kwargs,
    ):
        """滑块的圆形把手；不支持时返回 ``None``。"""
        if not get_engine().is_raster:
            return None

        w = int(round(width))
        h = int(round(height))
        if w <= 0 or h <= 0:
            return None

        spec = ThumbSpec(
            width=w,
            height=h,
            r1=float(r1),
            r2=float(r2),
            fill=fill,
            fill_opacity=parse_opacity(fill_opacity),
            outline=outline,
            outline_opacity=parse_opacity(outline_opacity),
            outline2=outline2,
            outline2_opacity=parse_opacity(outline2_opacity),
            inner_fill=inner_fill,
            inner_fill_opacity=parse_opacity(inner_fill_opacity),
        )
        photo = render_thumb(spec, self)
        if photo is None:
            return None
        item = self.create_image(x1, y1, anchor="nw", image=photo, **image_kwargs)
        return self._keep_photo(item, photo)

    # ------------------------------------------------------------------
    # SVG 兼容路径
    # ------------------------------------------------------------------
    def create_round_rectangle(
        self, x1, y1, x2, y2, r1, r2=None, fill="transparent",
        outline="black", width=1,
    ):
        self._img = self.svgdraw.create_roundrect(
            x1, y1, x2, y2, r1, r2, fill=fill, outline=outline, width=width
        )
        self._tkimg = self.svgdraw.create_svg_image(self._img)
        item = self.create_image(x1, y1, anchor="nw", image=self._tkimg)
        return self._keep_photo(item, self._tkimg)

    create_roundrect = create_round_rectangle
