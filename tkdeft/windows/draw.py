"""tkdeft 的绘制后端。

本模块同时承担两件事：

1. **SVG 后端**（``DSvgDraw``）：沿用 svgwrite 生成 SVG、再用 tksvg / Wand 栅格化。
   这条路径保持向后兼容，但修掉了两个真实缺陷：

   * ``temppath()`` 旧实现每次都 ``mkstemp()`` 一个新文件且 **从不关闭返回的 fd**，
     于是每绘制一帧就泄漏一个文件描述符、并在系统临时目录里留下一个残留文件。
     现在改为"每个绘制对象复用一个 scratch 文件"，并支持 :meth:`DDraw.cleanup` 回收。
   * tksvg 现在优先用 ``data=`` 直接吃 SVG 源码，避免"写盘再读回来"。

2. **栅格引擎入口**：真正的加速在 :mod:`tkdeft.engines`。
"""

from __future__ import annotations

from os import close as _close_fd


class DDraw(object):
    """最基础的绘制后端：把 SVG/其它矢量素材变成 tkinter 可用的图片。"""

    #: 创建图片时使用的 Tk 主控件（由 :class:`~tkdeft.windows.canvas.DCanvas` 注入）。
    #: 旧实现不传 master，多 Tk 解释器场景下图片会挂到错误的解释器上。
    master = None

    def create_svg_image(self, path, path2=None, way=0):
        """把 SVG（路径或源码）栅格化成 ``PhotoImage``。

        ``way`` 沿用历史语义：``1`` 走 Wand，**其余任何取值都表示 tksvg**。

        这里刻意不做严格校验：调用方普遍写作
        ``create_svg_image(img, tmp, way=get_renderer())``，而当启用
        skia / pillow / cairo 等栅格引擎时 ``get_renderer()`` 会返回 2/3/4。
        这条回退路径只在栅格引擎婉拒绘制时才会走到（例如控件尺寸尚未确定），
        此时用一个可用的后端把事情做完，远好过抛异常让整个控件构造失败。
        """
        if way == 1:
            return self.create_wand_image(path, path2)
        return self.create_tksvg_image(path)

    def create_tksvg_image(self, path):
        """把 SVG 变成 ``PhotoImage``。

        ``path`` 既可以是 SVG 文件路径，也可以直接是 SVG 源码字符串
        （以 ``<`` 开头）——后者走 tksvg 的 ``data=`` 通道，**完全不碰磁盘**。
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
        from PIL.Image import open as pil_open
        from PIL.ImageTk import PhotoImage

        image = pil_open(path)
        self.tkimage = PhotoImage(image=image, master=self.master)
        return self.tkimage

    def create_wand_image(self, input_path, output_path=None):
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
    """svgwrite 绘图后端。"""

    #: 复用的临时文件：``{后缀: 路径}``
    _scratch_paths: "dict[str, str]"

    def temppath(self, path=None, suffix=".svg"):
        """取得一个可用于写 SVG 的路径。

        .. note::
           传入 ``path`` 时原样返回。未传入时 **复用** 本对象自己的 scratch 文件，
           而不是每次 ``mkstemp()``。旧行为每帧都会新建文件并泄漏 fd，
           是长期运行程序的稳定性隐患；所有调用方都会整文件覆盖写，
           因此复用同一个路径是安全的。
        """
        if path:
            return path
        return self.scratch_path(suffix)

    def scratch_path(self, suffix=".svg", slot=0):
        """取（必要时创建）一个可复用的临时文件路径。

        ``slot`` 用于让同一个绘制对象持有多个互不干扰的 scratch 文件
        （对应旧 API 里的 ``temppath`` / ``temppath2`` / ``temppath3`` / ``temppath4``）。
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
        """删除本对象创建的 scratch 临时文件。"""
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

    def create_drawing(self, width, height, temppath=None, **kwargs):
        path = self.temppath(temppath)
        import svgwrite

        dwg = svgwrite.Drawing(path, width=width, height=height, **kwargs)

        return path, dwg
