"""字体工具：把随包分发的 Segoe UI 字体加载进来。

tkdeft 自带一份 ``segoe_font.ttf``（见 :data:`SEGOE_FONT_FILE`），
:func:`SegoeFont` 会按"能用哪一个就用哪一个"的顺序挑选实现：

1. ``tkextrafont``（Tk 扩展）——可以直接加载 ttf 文件，效果最好；
2. ``tkinter.font.Font``——只能按字体名走系统已安装的字体；
3. ``nametofont("TkDefaultFont")``——最后兜底，保证一定能拿到一个字体对象。

因此 :func:`SegoeFont` 在没装 ``tkextrafont`` 的机器上也不会抛异常。
"""

from __future__ import annotations

from os.path import abspath, dirname, join

__all__ = ["SEGOE_FONT_FILE", "SegoeFont", "segue_font_file"]

#: 本模块所在目录（字体文件所在的位置）
path = abspath(dirname(__file__))

#: 随包分发的 Segoe UI 字体文件路径
segoe_font = join(path, "segoe_font.ttf")


def segue_font_file() -> str:
    """返回随包分发的字体文件路径（等价于 :data:`segoe_font`）。

    :returns: ``.../tkdeft/utility/segoe_font.ttf``
    """
    return segoe_font


#: :func:`segue_font_file` 的常量形式，供外部直接引用
SEGOE_FONT_FILE = segoe_font


def SegoeFont():
    """取得一个 "Segoe UI, 10pt, bold" 的字体对象。

    :returns: ``tkextrafont.Font`` / ``tkinter.font.Font`` 之一
        （具体是哪一个取决于当前环境装了哪些依赖）

    .. note::
       需要在已创建 Tk 根窗口之后调用——字体对象依赖默认 Tk 解释器。
    """
    from _tkinter import TclError
    try:
        from tkextrafont import Font
        font = Font(file=segoe_font, size=10, family="Segoe UI", weight="bold")
    except TclError:
        try:
            from tkinter.font import Font
            font = Font(size=10, family="Segoe UI", weight="bold")
        except TclError:
            from tkinter.font import nametofont
            font = nametofont("TkDefaultFont").configure(size=10, weight="bold")
    return font
