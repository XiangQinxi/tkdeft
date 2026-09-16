"""tkdeft 的"窗口/画布"层：把矢量图变成 Tkinter 控件。

本子包提供三个零件：

============================ ================================================
:class:`~tkdeft.windows.canvas.DCanvas`      可以画矢量图的 ``tkinter.Canvas``
:class:`~tkdeft.windows.draw.DDraw`          绘制后端基类（矢量 → 图片）
:class:`~tkdeft.windows.draw.DSvgDraw`       svgwrite + tksvg / Wand 后端
:class:`~tkdeft.windows.drawwidget.DDrawWidget` 带 hover/按压/焦点状态的控件骨架
============================ ================================================

快速上手
--------
::

    import tkinter
    from tkdeft.windows.canvas import DCanvas

    root = tkinter.Tk()
    canvas = DCanvas(root, width=200, height=100)
    canvas.pack()

    # 一行画一个圆角矩形：栅格引擎走位图快速路径，否则自动回退 SVG
    canvas.draw_roundrect(0, 0, 120, 32, 6, fill="#ffffff", outline="#000000")
    root.mainloop()
"""

from .canvas import DCanvas
from .draw import DSvgDraw, DDraw
from .drawwidget import DDrawWidget, DDrawWidgetCanvas, DDrawWidgetDraw

__all__ = [
    "DCanvas",
    "DDraw",
    "DSvgDraw",
    "DDrawWidget",
    "DDrawWidgetCanvas",
    "DDrawWidgetDraw",
]
