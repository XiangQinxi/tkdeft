"""带绘制能力的 Canvas。

本模块提供三条并存的绘制路径：

* **统一入口**（:meth:`DCanvas.draw_roundrect` / :meth:`DCanvas.draw_track` /
  :meth:`DCanvas.draw_thumb`）——**推荐使用**：有栅格引擎时走位图快速路径，
  否则自动回退到 SVG，调用方只需要写一行，不用再关心"这个引擎支不支持"。
* **栅格快速路径**（:meth:`DCanvas.create_roundrect_raster` 等）：当当前引擎是
  skia / pillow / cairo 时，直接拿进程内渲染出的位图建 canvas item，
  不写临时文件、不解析 SVG，并且结果按 spec 缓存、可被多个控件共享。
* **SVG 后备路径**（:meth:`DCanvas.draw_roundrect_svg` 等）：用 svgwrite 生成
  SVG 再栅格化。它是 :class:`~tkdeft.windows.draw.DSvgDraw` 之上的薄封装，
  子类可以覆盖它来换一套图元实现。

历史方法 :meth:`DCanvas.create_round_rectangle` 等价于 :meth:`DCanvas.draw_roundrect`
（多一个 ``raster=False`` 开关可强制走 SVG）。

用法速览
--------
::

    canvas = DCanvas(root, width=200, height=100)

    # 一行画一个圆角矩形：引擎是栅格就直接出图，是 SVG 就自动回退
    canvas.draw_roundrect(0, 0, 120, 32, 6, fill="#ffffff", outline="#000000",
                          outline_opacity=0.2)

    # 想固定走某条路：
    canvas.draw_roundrect(..., raster=False)   # 强制 SVG
    canvas.raster_enabled = False              # 整个画布都强制 SVG

另外修掉了一个经典陷阱：``PhotoImage`` 必须由 Python 侧持有引用，
否则一旦被垃圾回收，**画布上对应的 item 会变成空白**。旧代码只用
``self._tkimg`` 保存"最后一张"，同一画布上有多张图片时其余都会变空白。
"""

from __future__ import annotations

from tkinter import Canvas
from typing import Any, Dict, Optional

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

__all__ = ["DCanvas"]

#: 超出该数量时清理已失效 item 的图片引用
_PHOTO_PRUNE_THRESHOLD = 256


class DCanvas(Canvas):
    """可以"画矢量图"的 ``tkinter.Canvas``。

    :cvar draw: 生成矢量内容的绘制后端，默认 :class:`~tkdeft.windows.draw.DSvgDraw`；
        子类换成自己的 ``Flu*Draw`` 即可换一套图元实现。
    :cvar raster_enabled: 是否允许栅格快速路径（置 ``False`` 可强制走 SVG）
    """

    from .draw import DSvgDraw

    draw = DSvgDraw

    #: 是否允许栅格快速路径；置 ``False`` 后所有 ``draw_*`` 都走 SVG
    raster_enabled = True

    def __init__(self, *args, border=0, highlightthickness=0, **kwargs):
        super().__init__(*args, border=border, highlightthickness=0, **kwargs)

        self.svgdraw = self.draw()
        # 把本画布作为 master 交给绘图后端，避免图片挂到别的 Tk 解释器上
        if hasattr(self.svgdraw, "master"):
            self.svgdraw.master = self
        #: canvas item id -> PhotoImage，防止图片被 GC 后画面变空白
        self._photo_refs: Dict[Any, Any] = {}

        self.bind("<Destroy>", self._event_destroy_draw, add="+")

    # ------------------------------------------------------------------
    # 图片引用管理
    # ------------------------------------------------------------------
    def _keep_photo(self, item, photo):
        """持有 ``PhotoImage`` 引用，并在必要时清理已删除 item 的引用。

        :param item: ``create_image`` 返回的 item id
        :param photo: 需要保活的 ``PhotoImage``
        :returns: 原样返回 ``item``，方便写成 ``return self._keep_photo(...)``
        """
        self._photo_refs[item] = photo
        if len(self._photo_refs) > _PHOTO_PRUNE_THRESHOLD:
            self._prune_photo_refs()
        return item

    def _prune_photo_refs(self):
        """丢掉已经不在画布上的 item 所对应的图片引用。"""
        stale = []
        for item in self._photo_refs:
            try:
                self.type(item)
            except Exception:
                stale.append(item)
        for item in stale:
            self._photo_refs.pop(item, None)

    def _event_destroy_draw(self, event=None):
        """控件销毁时释放图片引用与临时文件。"""
        if event is not None and getattr(event, "widget", None) is not self:
            return
        self._photo_refs.clear()
        cleanup = getattr(self.svgdraw, "cleanup", None)
        if callable(cleanup):
            cleanup()

    # ------------------------------------------------------------------
    # 统一绘制入口（推荐）
    # ------------------------------------------------------------------
    def draw_roundrect(
        self,
        x1,
        y1,
        x2,
        y2,
        radius,
        radiusy=None,
        *,
        temppath=None,
        temppath2=None,
        raster=True,
        gradient_stop1=None,
        gradient_stop2=None,
        stop1=None,
        stop2=None,
        **kwargs,
    ) -> int:
        """画一个圆角矩形——**优先栅格引擎，不支持时自动回退 SVG**。

        :param x1: 左上角 x
        :param y1: 左上角 y
        :param x2: 右下角 x
        :param y2: 右下角 y
        :param radius: 圆角半径（x 方向）
        :param radiusy: 圆角半径（y 方向）；为空时取 ``radius``
        :param temppath: SVG 兜底路径使用的临时文件（一般不用传）
        :param temppath2: Wand 引擎的 PNG 输出路径（一般不用传）
        :param raster: 置 ``False`` 可跳过栅格快速路径，强制走 SVG
        :param gradient_stop1: 渐变描边第一个 stop 的位置；``None`` 表示用引擎默认值
        :param gradient_stop2: 渐变描边第二个 stop 的位置；``None`` 同上
        :param stop1: ``gradient_stop1`` 的别名（照顾历史写法）
        :param stop2: ``gradient_stop2`` 的别名
        :param kwargs: 其余绘制参数（``fill`` / ``fill_opacity`` / ``outline`` /
            ``outline2`` / ``outline_opacity`` / ``outline2_opacity`` / ``width``）
        :returns: canvas item id（无论走哪条路径都一定有值，不需要再判断 ``None``）

        想换一种图元实现，覆盖 :meth:`draw_roundrect_svg` 即可——
        快速路径的判定与回退都发生在这一层，子类不必重复写一遍。
        """
        if stop1 is not None:
            gradient_stop1 = stop1
        if stop2 is not None:
            gradient_stop2 = stop2
        # 只在调用方显式指定时才塞进 kwargs，免得给不支持渐变参数的图元添乱
        if gradient_stop1 is not None:
            kwargs["gradient_stop1"] = float(gradient_stop1)
        if gradient_stop2 is not None:
            kwargs["gradient_stop2"] = float(gradient_stop2)

        if raster and self.raster_enabled:
            item = self.create_roundrect_raster(
                x1, y1, x2, y2, radius, radiusy, **kwargs
            )
            if item is not None:
                return item

        return self.draw_roundrect_svg(
            x1,
            y1,
            x2,
            y2,
            radius,
            radiusy,
            temppath=temppath,
            temppath2=temppath2,
            **kwargs,
        )

    def draw_track(
        self,
        x1,
        y1,
        width,
        height,
        width2,
        *,
        temppath=None,
        temppath2=None,
        raster=True,
        **kwargs,
    ) -> int:
        """画滑块/滚动条的进度条槽（左边选中段 + 右边底轨）。

        :param x1: 左上角 x
        :param y1: 左上角 y
        :param width: 位图宽度
        :param height: 位图高度
        :param width2: 左半段（已选中部分）的宽度
        :param raster: 置 ``False`` 可强制走 SVG
        :param kwargs: ``radius`` / ``track_fill`` / ``track_opacity`` /
            ``rail_fill`` / ``rail_opacity``
        :returns: canvas item id
        """
        if raster and self.raster_enabled:
            item = self.create_track_raster(
                x1, y1, width, height, width2, **kwargs
            )
            if item is not None:
                return item
        return self.draw_track_svg(
            x1, y1, width, height, width2,
            temppath=temppath, temppath2=temppath2, **kwargs
        )

    def draw_thumb(
        self,
        x1,
        y1,
        width,
        height,
        r1,
        r2,
        *,
        temppath=None,
        temppath2=None,
        raster=True,
        **kwargs,
    ) -> int:
        """画滑块/滚动条的圆形把手（渐变伪阴影 + 外填充 + 内填充）。

        :param x1: 左上角 x
        :param y1: 左上角 y
        :param width: 位图宽度
        :param height: 位图高度
        :param r1: 外圆半径
        :param r2: 内圆半径
        :param raster: 置 ``False`` 可强制走 SVG
        :param kwargs: ``fill`` / ``fill_opacity`` / ``outline`` /
            ``outline_opacity`` / ``outline2`` / ``outline2_opacity`` /
            ``inner_fill`` / ``inner_fill_opacity``
        :returns: canvas item id
        """
        if raster and self.raster_enabled:
            item = self.create_thumb_raster(
                x1, y1, width, height, r1, r2, **kwargs
            )
            if item is not None:
                return item
        return self.draw_thumb_svg(
            x1, y1, width, height, r1, r2,
            temppath=temppath, temppath2=temppath2, **kwargs
        )

    # ------------------------------------------------------------------
    # SVG 兜底路径（子类按需覆盖）
    # ------------------------------------------------------------------
    def draw_svg_item(
        self, svg_path, temppath2=None, x=0, y=0, **image_kwargs
    ) -> int:
        """把 SVG 文件变成画布上的图片 item——SVG 路径的最后一步。

        :param svg_path: SVG 文件路径（或 SVG 源码字符串）
        :param temppath2: Wand 引擎的 PNG 输出路径
        :param x: 摆放位置的 x
        :param y: 摆放位置的 y
        :returns: canvas item id

        这里会按**当前引擎**自动选后端（``wand`` 走 Wand，其余走 tksvg），
        并且用 :meth:`_keep_photo` 保住 ``PhotoImage`` 引用，避免被 GC 后变空白。
        """
        photo = self.svgdraw.create_svg_image(svg_path, temppath2)
        item = self.create_image(x, y, anchor="nw", image=photo, **image_kwargs)
        return self._keep_photo(item, photo)

    def draw_roundrect_svg(
        self,
        x1,
        y1,
        x2,
        y2,
        radius,
        radiusy=None,
        *,
        temppath=None,
        temppath2=None,
        **kwargs,
    ) -> int:
        """圆角矩形的 SVG 兜底实现。

        子类想换自己的图元（例如固定圆角、额外滤镜）时覆盖本方法即可，
        不需要再写一遍"先试栅格、失败再回退"的样板代码。
        """
        self._img = self.svgdraw.create_roundrect(
            x1, y1, x2, y2, radius, radiusy, temppath=temppath, **kwargs
        )
        photo = self.svgdraw.create_svg_image(self._img, temppath2)
        self._tkimg = photo
        item = self.create_image(x1, y1, anchor="nw", image=photo)
        return self._keep_photo(item, photo)

    def draw_track_svg(
        self,
        x1,
        y1,
        width,
        height,
        width2,
        *,
        temppath=None,
        temppath2=None,
        **kwargs,
    ) -> int:
        """进度条槽的 SVG 兜底实现。"""
        self._img2 = self.svgdraw.create_track(
            width, height, width2, temppath=temppath, **kwargs
        )
        photo = self.svgdraw.create_svg_image(self._img2, temppath2)
        self._tkimg2 = photo
        item = self.create_image(x1, y1, anchor="nw", image=photo)
        return self._keep_photo(item, photo)

    def draw_thumb_svg(
        self,
        x1,
        y1,
        width,
        height,
        r1,
        r2,
        *,
        temppath=None,
        temppath2=None,
        **kwargs,
    ) -> int:
        """圆形把手的 SVG 兜底实现。"""
        self._img = self.svgdraw.create_thumb(
            width, height, r1, r2, temppath=temppath, **kwargs
        )
        photo = self.svgdraw.create_svg_image(self._img, temppath2)
        self._tkimg = photo
        item = self.create_image(x1, y1, anchor="nw", image=photo)
        return self._keep_photo(item, photo)

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

        :param args: 额外参数透传给 ``create_image``
        :param image_kwargs: 其余关键字透传给 ``create_image``（例如 ``tags``）
        :returns: 成功时返回 canvas item id；当前引擎是 SVG 系、尺寸非法或
            渲染失败时返回 ``None``，调用方应回退到 :meth:`draw_roundrect_svg`
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
    ) -> Optional[int]:
        """用当前栅格引擎绘制进度条槽；不支持时返回 ``None``。"""
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
    ) -> Optional[int]:
        """用当前栅格引擎绘制圆形把手；不支持时返回 ``None``。"""
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
    # 历史 API
    # ------------------------------------------------------------------
    def create_round_rectangle(
        self,
        x1,
        y1,
        x2,
        y2,
        r1,
        r2=None,
        fill="transparent",
        outline="black",
        width=1,
        *,
        temppath=None,
        temppath2=None,
        raster=True,
        **kwargs,
    ) -> int:
        """画一个圆角矩形（历史方法名，等价于 :meth:`draw_roundrect`）。

        :param r1: 圆角半径（x 方向）
        :param r2: 圆角半径（y 方向）；为空时取 ``r1``
        :param fill: 填充色
        :param outline: 描边色
        :param width: 描边宽度
        :param kwargs: 其余参数透传给 :meth:`draw_roundrect`
            （例如 ``outline2`` / ``outline_opacity`` / ``fill_opacity``）
        :returns: canvas item id

        只走 SVG 的旧行为仍然保留在 :meth:`draw_roundrect_svg` 里；
        想临时关掉快速路径就传 ``raster=False``。
        """
        return self.draw_roundrect(
            x1,
            y1,
            x2,
            y2,
            r1,
            r2,
            temppath=temppath,
            temppath2=temppath2,
            raster=raster,
            fill=fill,
            outline=outline,
            width=width,
            **kwargs,
        )

    #: ``create_round_rectangle`` 的缩写，与各组件里的历史写法保持一致
    create_roundrect = create_round_rectangle
