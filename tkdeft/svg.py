"""svgwrite 形状助手。

为什么需要它
------------
tkfluent 里原先每个组件都手写一遍圆角矩形的 SVG 拼装，几何写法各不相同，
并且普遍踩了同一个坑：

.. code-block:: python

    dwg.rect((x1, y1), (x2 - x1, y2 - y1), rx, ry,
             stroke="#000", stroke_width=1,
             transform="translate(0.500000 0.500000)")

SVG 的描边是**以路径为中心线**向两侧各画半个线宽。上面这种写法把矩形放到
``(0.5, 0.5)``、尺寸仍然是整宽整高，于是矩形右边界正好落在 ``x = w + 0.5``：
右边和下边的描边被整个推到画布之外，**完全不可见**——按钮看起来只有上边框和
左边框。frame / listbox 用的是不加 translate 的版本，四边各被削掉一半厚度。

正确做法是把几何**向内收缩半个线宽**，让描边的外沿正好贴合画布边缘。
栅格引擎（skia / pillow / cairo）本来就是这么算的，本模块让 SVG 引擎与之对齐。
"""

from __future__ import annotations

from typing import Tuple

__all__ = ["Geometry", "roundrect_geometry", "add_roundrect", "svg_paint", "gradient_stop"]

#: ``(insert, size, rx, ry)`` —— 可直接喂给 ``svgwrite`` 的 ``rect()``
Geometry = Tuple[Tuple[float, float], Tuple[float, float], float, float]

#: 表示"不绘制"的各种写法。栅格引擎（skia / pillow / cairo）把这几个值都当成
#: "这一层不画"，但 **svgwrite 的属性校验器只认 ``"none"``**：
#: ``None`` 会抛 ``TypeError: 'None' is not a valid value for attribute 'stroke'``，
#: 设计稿里常见的 ``"transparent"`` 同样被拒。
_NO_PAINT = frozenset({"", "none", "transparent", "null", "nil"})


def svg_paint(value, default: str = "none"):
    """把"没有颜色"的写法统一成 svgwrite 认识的 ``"none"``。

    :param value: 颜色，可能是 ``None`` / ``"transparent"`` / ``"none"`` / 真颜色
    :param default: 不绘制时返回什么（默认 ``"none"``）
    :returns: 可直接交给 svgwrite 的取值

    没有这一步时，同一份规格在两条路径上的行为并不一致——
    ``RoundRectSpec(outline=None)`` 用 skia 渲染正常，换到 tksvg 就抛
    ``TypeError``；``"transparent"`` 也一样。这里统一之后，
    "描边 / 填充留空"的写法在五个引擎上都能跑。
    """
    if value is None:
        return default
    return default if str(value).strip().lower() in _NO_PAINT else value


def gradient_stop(color, opacity):
    """把渐变 stop 归一成 ``(颜色, 透明度)``。

    SVG 里没有 ``transparent`` 这个关键字，渐变要"淡出到透明"只能写成
    「某个颜色 + ``stop-opacity="0"``」，所以这里把"不绘制"翻译成
    ``("#000000", 0.0)``；其余颜色原样返回。

    :returns: ``(颜色, 透明度)``
    """
    if color is None or str(color).strip().lower() in _NO_PAINT:
        return "#000000", 0.0
    return color, opacity



def roundrect_geometry(
    x1, y1, x2, y2, radius, radiusy=None, stroke_width=1
) -> Geometry:
    """按"描边居中"规则把圆角矩形几何内缩。

    对退化尺寸做了保护：控件在布局完成之前宽高可能是 0、1 甚至负数
    （``FluSlider`` 构造时 ``winfo_width()`` 就是 1）。SVG 里
    ``width`` / ``height`` 一旦 ``<= 0``，tksvg 会直接抛
    ``couldn't recognize image data``，所以这里把边长和内缩量都夹到安全范围。

    Returns:
        ``(insert, size, rx, ry)``，可直接喂给 ``svgwrite`` 的 ``rect()``。
    """
    # 边长下限 0.5：既能被 tksvg 接受，视觉上也不可见
    w = max(0.5, float(x2) - float(x1))
    h = max(0.5, float(y2) - float(y1))

    inset = (float(stroke_width) / 2.0) if stroke_width else 0.0
    # 内缩量最多用掉一半可用空间，否则同样会退化成非正尺寸
    inset = min(inset, max(0.0, (w - 0.5) / 2.0), max(0.0, (h - 0.5) / 2.0))

    rx = max(0.0, float(radius or 0) - inset)
    ry = max(0.0, float(radiusy if radiusy else radius or 0) - inset)
    insert = (x1 + inset, y1 + inset)
    size = (w - 2 * inset, h - 2 * inset)
    return insert, size, rx, ry


def add_roundrect(
    dwg,
    x1,
    y1,
    x2,
    y2,
    radius,
    radiusy=None,
    *,
    fill="transparent",
    fill_opacity=1,
    outline="black",
    outline2=None,
    outline_opacity=1,
    outline2_opacity=1,
    width=1,
    gradient=True,
    gradient_id="DButton.Border",
    gradient_stop1=0.9,
    gradient_stop2=1.0,
    **extra,
) -> Geometry:
    """往 svgwrite 的 ``Drawing`` 里加一个四边描边都完整的圆角矩形。

    :param dwg: ``svgwrite.Drawing`` 对象（:meth:`tkdeft.windows.draw.DSvgDraw.create_drawing`
        返回的第二个元素；各组件的历史写法是 ``drawing[1]``）
    :param fill: 填充色，``"transparent"`` 表示不填充
    :param fill_opacity: 填充透明度
    :param outline: 描边色
    :param outline2: 渐变描边的第二个颜色；为空则用纯色描边
    :param outline_opacity: 描边透明度
    :param outline2_opacity: 渐变描边第二个颜色的透明度
    :param width: 描边宽度（描边以路径为中心线，几何会自动内缩半个线宽）
    :param gradient: 允许使用渐变描边；置 ``False`` 可强制纯色
    :param gradient_id: 渐变定义的 id
    :param gradient_stop1: 第一个 stop 的位置（0-1）
    :param gradient_stop2: 第二个 stop 的位置（0-1）
    :param extra: 其余关键字直接透传给 ``rect()``（例如 ``id=".Badge"``）

    :returns: ``(insert, size, rx, ry)``
    """
    insert, size, rx, ry = roundrect_geometry(
        x1, y1, x2, y2, radius, radiusy, width
    )

    if gradient and outline2:
        border = dwg.linearGradient(
            start=(insert[0], insert[1]),
            end=(insert[0], insert[1] + size[1]),
            id=gradient_id,
            gradientUnits="userSpaceOnUse",
        )
        stop1_color, stop1_opacity = gradient_stop(outline, outline_opacity)
        stop2_color, stop2_opacity = gradient_stop(outline2, outline2_opacity)
        border.add_stop_color(gradient_stop1, stop1_color, stop1_opacity)
        border.add_stop_color(gradient_stop2, stop2_color, stop2_opacity)
        dwg.defs.add(border)
        stroke = f"url(#{border.get_id()})"
        stroke_opacity = 1
    else:
        stroke = svg_paint(outline)
        stroke_opacity = outline_opacity

    dwg.add(
        dwg.rect(
            insert,
            size,
            rx,
            ry,
            fill=svg_paint(fill),
            fill_opacity=fill_opacity,
            stroke=stroke,
            stroke_width=width,
            stroke_opacity=stroke_opacity,
            **extra,
        )
    )
    return insert, size, rx, ry
