"""tkdeft 的绘制后端：把矢量素材变成 ``PhotoImage``。

本模块同时承担两件事：

1. **SVG 后端**（:class:`DSvgDraw`）：用 svgwrite 生成 SVG，再用 tksvg / Wand
   栅格化。这条路径是历史默认路径，也是栅格引擎不可用时的兜底。它在
   tkdeft 里提供了三种图元的**通用实现**（圆角矩形 / 进度条槽 / 圆形把手），
   因此不依赖任何具体组件库也能画出一个控件。

   同时修掉了两个真实缺陷：

   * ``temppath()`` 旧实现每次都 ``mkstemp()`` 一个新文件且 **从不关闭返回的 fd**，
     于是每绘制一帧就泄漏一个文件描述符、并在系统临时目录里留下一个残留文件。
     现在改为"每个绘制对象复用一个 scratch 文件"，并支持 :meth:`DDraw.cleanup` 回收。
   * tksvg 现在优先用 ``data=`` 直接吃 SVG 源码，避免"写盘再读回来"。

2. **栅格引擎入口**：真正的加速在 :mod:`tkdeft.engines`，本模块只负责把
   ``PIL.Image`` 转成 ``PhotoImage``（:meth:`DDraw.create_tk_image`）。

选哪条路？
----------
::

    from tkdeft.windows.draw import DSvgDraw

    draw = DSvgDraw()
    path = draw.create_roundrect(0, 0, 120, 32, 6, fill="#ffffff")   # 生成 SVG
    photo = draw.create_svg_image(path)                             # 栅格化

``create_svg_image(..., way=None)`` 会按**当前引擎**自动选择后端：
``wand`` 引擎走 Wand，其余走 tksvg。想手动指定就传 ``way=1``（Wand）
或 ``way="tksvg"``。
"""

from __future__ import annotations

from os import close as _close_fd
from typing import Any

__all__ = ["DDraw", "DSvgDraw", "WAND_WAY", "TKSVG_WAY"]

#: :meth:`DDraw.create_svg_image` 的 ``way`` 取值（沿用历史语义）
TKSVG_WAY = 0
WAND_WAY = 1


class DDraw(object):
    """最基础的绘制后端：把 SVG/其它矢量素材变成 tkinter 可用的图片。

    它只关心"怎么把东西显示出来"，不关心画什么。子类（比如
    :class:`DSvgDraw`）负责生成矢量内容。

    :cvar master: 创建图片时使用的 Tk 主控件，由
        :class:`~tkdeft.windows.canvas.DCanvas` 注入。旧实现不传 master，
        多 Tk 解释器场景下图片会挂到错误的解释器上。
    """

    master = None

    # ------------------------------------------------------------------
    # 引擎选择
    # ------------------------------------------------------------------
    @staticmethod
    def current_engine_name() -> str:
        """当前绘制引擎的名字（``"tksvg"`` / ``"skia"`` …）。"""
        from ..engines import get_engine_name

        return get_engine_name()

    def auto_way(self) -> int:
        """按当前引擎挑选 SVG 栅格化后端。

        :returns: :data:`WAND_WAY`（当前是 ``wand`` 引擎）或
            :data:`TKSVG_WAY`（其余情况）
        """
        return WAND_WAY if self.current_engine_name() == "wand" else TKSVG_WAY

    @staticmethod
    def resolve_way(way: Any) -> int:
        """把 ``way`` 参数统一成 ``0`` / ``1``。

        :param way: ``None``（自动） / ``0`` / ``1`` / ``"tksvg"`` / ``"wand"``
            / ``"2"`` 这类编号字符串
        """
        if way is None:
            return TKSVG_WAY
        if isinstance(way, str):
            text = way.strip().lower()
            if text in ("wand", "1"):
                return WAND_WAY
            if text in ("tksvg", "svg", "0"):
                return TKSVG_WAY
            try:
                return int(text)
            except ValueError:
                return TKSVG_WAY
        try:
            return int(way)
        except (TypeError, ValueError):
            return TKSVG_WAY

    # ------------------------------------------------------------------
    # 图片创建
    # ------------------------------------------------------------------
    def create_svg_image(self, path, path2=None, way=None):
        """把 SVG（路径或源码）栅格化成 ``PhotoImage``。

        :param path: SVG 文件路径，或直接是 SVG 源码字符串（以 ``<`` 开头）
        :param path2: Wand 后端的 PNG 输出路径；为空时自动申请一个 scratch 文件
        :param way: ``None`` 表示按当前引擎自动选择（推荐）；
            ``1`` / ``"wand"`` 走 Wand，其余任何取值都表示 tksvg
        :returns: ``tkinter.PhotoImage``（Wand 失败时可能返回 ``None``）

        这里刻意不做严格校验：调用方普遍写作
        ``create_svg_image(img, tmp, way=get_renderer())``，而当启用
        skia / pillow / cairo 等栅格引擎时 ``get_renderer()`` 会返回 2/3/4。
        这条回退路径只在栅格引擎婉拒绘制时才会走到（例如控件尺寸尚未确定），
        此时用一个可用的后端把事情做完，远好过抛异常让整个控件构造失败。
        """
        if self.resolve_way(way) == WAND_WAY:
            return self.create_wand_image(path, path2)
        return self.create_tksvg_image(path)

    def create_tksvg_image(self, path):
        """用 tksvg 把 SVG 变成 ``PhotoImage``。

        :param path: SVG 文件路径，或 SVG 源码字符串（以 ``<`` 开头）
            ——后者走 tksvg 的 ``data=`` 通道，**完全不碰磁盘**
        """
        from tksvg import SvgImage

        if isinstance(path, str) and path.lstrip().startswith("<"):
            if self.master is not None:
                return SvgImage(data=path, master=self.master)
            return SvgImage(data=path)
        if self.master is not None:
            return SvgImage(file=path, master=self.master)
        return SvgImage(file=path)

    def create_tk_image(self, path):
        """把磁盘上的图片文件（PNG/JPG…）读成 ``PhotoImage``。

        这是 :mod:`tkdeft.engines` 渲染结果的落地方式：栅格引擎产生
        ``PIL.Image``，转成 ``PhotoImage`` 才能交给画布。
        """
        from PIL.Image import open as pil_open
        from PIL.ImageTk import PhotoImage

        image = pil_open(path)
        self.tkimage = PhotoImage(image=image, master=self.master)
        return self.tkimage

    def create_wand_image(self, input_path, output_path=None):
        """用 Wand(ImageMagick) 把 SVG 转成 PNG，再读成 ``PhotoImage``。

        :param input_path: 输入 SVG 路径
        :param output_path: 输出 PNG 路径；为空时自动申请一个 scratch 文件
        :returns: ``PhotoImage``；ImageMagick 处理失败时返回 ``None``
        """
        from tkinter import PhotoImage

        from wand.exceptions import ImageError
        from wand.image import Image

        # 历史上 wand 路径要求调用方必须传 temppath2（输出 PNG 路径），
        # 漏传时会在 img.save(filename=None) 抛出难以理解的
        # "TypeError: expected an argument"。这里补一个自管的临时输出路径。
        if not output_path:
            scratch = getattr(self, "scratch_path", None)
            if callable(scratch):
                output_path = scratch(".png")
            else:  # pragma: no cover - 极简子类兜底
                from os import close
                from tempfile import mkstemp

                fd, output_path = mkstemp(suffix=".png", prefix="tkdeft.wand.")
                close(fd)

        try:
            with Image(filename=input_path, background="transparent") as img:
                img.format = "png"
                img.save(filename=output_path)

            if self.master is not None:
                photoimg = PhotoImage(file=output_path, master=self.master)
            else:
                photoimg = PhotoImage(file=output_path)
        except ImageError:
            return None
        else:
            return photoimg


class DSvgDraw(DDraw):
    """svgwrite 绘图后端：拼 SVG → 栅格化。

    除了 :meth:`create_drawing` 这些基础能力，它还提供三种图元的**通用 SVG 实现**，
    供 :class:`~tkdeft.windows.canvas.DCanvas` 在没有栅格引擎时兜底：

    ========================== ==========================================
    方法                       图元
    ========================== ==========================================
    :meth:`create_roundrect`   圆角矩形（可带渐变描边）
    :meth:`create_track`       进度条槽（选中段 + 底轨）
    :meth:`create_thumb`       圆形把手（渐变伪阴影 + 两层填充）
    ========================== ==========================================

    三个方法都返回**生成好的 SVG 文件路径**；把它交给
    :meth:`DDraw.create_svg_image` 就能得到 ``PhotoImage``。
    """

    #: 复用的临时文件：``{后缀: 路径}``
    _scratch_paths: "dict[str, str]"

    # ------------------------------------------------------------------
    # 临时文件
    # ------------------------------------------------------------------
    def temppath(self, path=None, suffix=".svg"):
        """取得一个可用于写 SVG 的路径。

        :param path: 给定时原样返回（调用方自己管理这个路径）
        :param suffix: 需要新建时使用的后缀

        .. note::
           未传入 ``path`` 时 **复用** 本对象自己的 scratch 文件，而不是每次
           ``mkstemp()``。旧行为每帧都会新建文件并泄漏 fd，是长期运行程序的
           稳定性隐患；所有调用方都会整文件覆盖写，因此复用同一个路径是安全的。
        """
        if path:
            return path
        return self.scratch_path(suffix)

    def scratch_path(self, suffix=".svg", slot=0):
        """取（必要时创建）一个可复用的临时文件路径。

        :param suffix: 文件后缀，例如 ``".svg"`` / ``".png"``
        :param slot: 槽位编号，让同一个绘制对象持有多个互不干扰的 scratch 文件
            （对应旧 API 里的 ``temppath`` / ``temppath2`` / ``temppath3`` /
            ``temppath4``）
        """
        paths = self.__dict__.setdefault("_scratch_paths", {})
        key = (suffix, slot)
        cached = paths.get(key)
        if cached is None:
            from tempfile import mkstemp

            fd, cached = mkstemp(suffix=suffix, prefix="tkdeft.temp.")
            _close_fd(fd)  # mkstemp 返回的 fd 必须显式关闭，否则泄漏
            paths[key] = cached
        return cached

    def cleanup(self):
        """删除本对象创建的 scratch 临时文件。

        :returns: 实际删掉的文件数。控件销毁时由
            :class:`~tkdeft.windows.canvas.DCanvas` 自动调用。
        """
        from os import remove
        from os.path import exists

        removed = 0
        for suffix_path in self.__dict__.get("_scratch_paths", {}).values():
            try:
                if exists(suffix_path):
                    remove(suffix_path)
                    removed += 1
            except OSError:
                pass
        self.__dict__.pop("_scratch_paths", None)
        return removed

    # ------------------------------------------------------------------
    # 画布
    # ------------------------------------------------------------------
    def create_drawing(self, width, height, temppath=None, **kwargs):
        """新建一个 svgwrite 画布。

        :param width: 画布宽度（像素）
        :param height: 画布高度（像素）
        :param temppath: 输出的 SVG 路径；为空时复用本对象的 scratch 文件
        :param kwargs: 其余关键字透传给 :class:`svgwrite.Drawing`
            （例如 ``fill_opacity=0``）
        :returns: ``(svg 路径, svgwrite.Drawing)``

        ::

            path, dwg = draw.create_drawing(120, 32)
            dwg[1].add(dwg[1].rect((0, 0), (10, 10)))
            dwg[1].save()
        """
        path = self.temppath(temppath)
        import svgwrite

        dwg = svgwrite.Drawing(path, width=width, height=height, **kwargs)

        return path, dwg

    # ------------------------------------------------------------------
    # 通用图元（栅格引擎不可用时的兜底实现）
    # ------------------------------------------------------------------
    def create_roundrect(
        self,
        x1,
        y1,
        x2,
        y2,
        radius,
        radiusy=None,
        temppath=None,
        fill="transparent",
        fill_opacity=1,
        outline="black",
        outline2=None,
        outline_opacity=1,
        outline2_opacity=1,
        width=1,
        gradient_id="DButton.Border",
        **extra,
    ) -> str:
        """生成一个四边描边都完整的圆角矩形 SVG。

        :param x1: 左上角 x
        :param y1: 左上角 y
        :param x2: 右下角 x
        :param y2: 右下角 y
        :param radius: 圆角半径（x 方向）
        :param radiusy: 圆角半径（y 方向）；为空时取 ``radius``
        :param temppath: 输出的 SVG 路径；为空时复用 scratch 文件
        :param fill: 填充色，``"transparent"`` 表示不填充
        :param fill_opacity: 填充透明度
        :param outline: 描边色
        :param outline2: 渐变描边的第二个颜色；为空则用纯色描边
        :param outline_opacity: 描边透明度
        :param outline2_opacity: 渐变描边第二个颜色的透明度
        :param width: 描边宽度（描边居中，几何会自动内缩半个线宽）
        :param gradient_id: 渐变定义的 id（同一个 SVG 里不要重复）
        :param extra: 其余关键字透传给 svgwrite 的 ``rect()``（例如 ``id=".Badge"``）
        :returns: 生成好的 SVG 文件路径
        """
        from ..svg import add_roundrect

        _rx, _ry = (radius, radius) if not radiusy else (radius, radiusy)
        path, drawing = self.create_drawing(x2 - x1, y2 - y1, temppath=temppath)
        add_roundrect(
            drawing,
            x1,
            y1,
            x2,
            y2,
            _rx,
            _ry,
            fill=fill,
            fill_opacity=fill_opacity,
            outline=outline,
            outline2=outline2,
            outline_opacity=outline_opacity,
            outline2_opacity=outline2_opacity,
            width=width,
            gradient_id=gradient_id,
            **extra,
        )
        drawing.save()
        return path

    def create_track(
        self,
        width,
        height,
        width2,
        temppath=None,
        radius=3,
        track_fill="transparent",
        track_opacity=1,
        rail_fill="transparent",
        rail_opacity=1,
    ) -> str:
        """生成滑块/滚动条"进度条槽"的 SVG。

        :param width: 位图宽度
        :param height: 位图高度
        :param width2: 左半段（已选中部分）的宽度
        :param temppath: 输出的 SVG 路径；为空时复用 scratch 文件
        :param radius: 圆角半径
        :param track_fill: 已选中部分的颜色
        :param track_opacity: 已选中部分的透明度
        :param rail_fill: 未选中底轨的颜色
        :param rail_opacity: 未选中底轨的透明度
        :returns: 生成好的 SVG 文件路径
        """
        path, drawing = self.create_drawing(
            width, height, temppath=temppath, fill_opacity=0
        )
        drawing.add(
            drawing.rect(
                (0, 0),
                (width2, height),
                rx=radius,
                fill=track_fill,
                fill_opacity=track_opacity,
                fill_rule="evenodd",
            )
        )  # 滑块进度左边的选中区域（只左部分）
        drawing.add(
            drawing.rect(
                (width2, 0),
                (width - width2, height),
                rx=radius,
                fill=rail_fill,
                fill_opacity=rail_opacity,
            )
        )  # 滑块进度未选中区域（占全部）
        drawing.save()
        return path

    def create_thumb(
        self,
        width,
        height,
        r1,
        r2,
        temppath=None,
        fill="transparent",
        fill_opacity=1,
        outline="transparent",
        outline_opacity=1,
        outline2="transparent",
        outline2_opacity=1,
        inner_fill="transparent",
        inner_fill_opacity=1,
    ) -> str:
        """生成滑块"圆形把手"的 SVG（外圈渐变伪阴影 + 外填充 + 内填充）。

        :param width: 位图宽度
        :param height: 位图高度
        :param r1: 外圆半径（伪阴影那一圈）
        :param r2: 内圆半径
        :param temppath: 输出的 SVG 路径；为空时复用 scratch 文件
        :param fill: 外填充色
        :param fill_opacity: 外填充透明度
        :param outline: 伪阴影渐变的第一个颜色
        :param outline_opacity: 伪阴影第一个颜色的透明度
        :param outline2: 伪阴影渐变的第二个颜色
        :param outline2_opacity: 伪阴影第二个颜色的透明度
        :param inner_fill: 内圆填充色
        :param inner_fill_opacity: 内圆填充透明度
        :returns: 生成好的 SVG 文件路径
        """
        path, drawing = self.create_drawing(
            width, height, temppath=temppath, fill_opacity=0
        )
        border = drawing.linearGradient(
            start=(r1, 1),
            end=(r1, r1 * 2 - 1),
            id="DButton.Border",
            gradientUnits="userSpaceOnUse",
        )
        border.add_stop_color(0.500208, outline, outline_opacity)
        border.add_stop_color(0.954545, outline2, outline2_opacity)
        drawing.defs.add(border)
        stroke = f"url(#{border.get_id()})"

        drawing.add(
            drawing.circle(
                (width / 2, height / 2),
                r1,
                fill=stroke,
                fill_opacity=1,
                fill_rule="evenodd",
            )
        )  # 圆形滑块的伪阴影边框
        drawing.add(
            drawing.circle(
                (width / 2, height / 2),
                r1 - 1,
                fill=fill,
                fill_opacity=fill_opacity,
                fill_rule="nonzero",
            )
        )  # 圆形滑块的外填充
        drawing.add(
            drawing.circle(
                (width / 2, height / 2),
                r2,
                fill=inner_fill,
                fill_opacity=inner_fill_opacity,
                fill_rule="nonzero",
            )
        )  # 圆形滑块的内填充
        drawing.save()
        return path
