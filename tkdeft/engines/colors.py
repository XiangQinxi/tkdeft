"""颜色解析工具：把设计稿里的各种颜色写法统一成 RGBA 整数元组。

设计稿里出现的写法五花八门，必须全部吃下：

* ``"#ffffff"`` / ``"#FFF"`` / ``"#RRGGBBAA"``
* ``"transparent"`` / ``"none"`` / ``None`` / ``""``  → 视为不绘制
* CSS 命名色 ``"black"`` / ``"white"`` / ``"red"`` …（借 Pillow 的 ImageColor 表）
* ``(r, g, b)`` / ``(r, g, b, a)`` 元组
* 透明度既可能是 ``0.7`` 这样的 float，也可能是 ``"0.7"`` 这样的 str，
  还出现过 ``0``（int，表示全透明）、``"1.000000"``

对外接口
--------
::

    from tkdeft.engines import parse_color, parse_opacity

    parse_color("#ffffff", 0.2)     # -> (255, 255, 255, 51)
    parse_color("transparent")      # -> None   （调用方据此跳过这一层绘制）
    parse_opacity("0.7")            # -> 0.7

三个栅格引擎共用这一套解析规则，因此"同一个颜色在不同引擎下画出不同结果"
这类问题只会出现在通道序/预乘上，而不会出现在颜色写法上。
"""

from __future__ import annotations

from typing import Optional, Tuple

__all__ = [
    "RGBA",
    "parse_color",
    "parse_opacity",
    "normalize_hex",
    "lerp_rgba",
    "to_hex",
]

#: ``(r, g, b, a)``，每个分量都是 0–255 的整数
RGBA = Tuple[int, int, int, int]

_TRANSPARENT_WORDS = frozenset({"", "none", "transparent", "null", "nil"})


def normalize_hex(value: str) -> str:
    """把 ``#FFF`` / ``#FFFFFF`` 统一成小写 6 位形式（不含 alpha）。

    :param value: 形如 ``"#fff"`` / ``"FFF"`` / ``"#F0F0F0"`` 的字符串
    :returns: ``"#rrggbb"``；超过 6 位的部分（alpha）会被截掉
    """
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#" + h[:6].lower()


def to_hex(rgba: RGBA, *, with_alpha: bool = False) -> str:
    """把 ``(r, g, b, a)`` 转回十六进制字符串。

    :param rgba: :func:`parse_color` 的返回值
    :param with_alpha: 是否把 alpha 也拼进去（``"#rrggbbaa"``）
    :returns: 形如 ``"#ffffff"`` 的小写字符串
    """
    r, g, b, a = (max(0, min(255, int(channel))) for channel in rgba)
    if with_alpha:
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_opacity(value, default: float = 1.0) -> float:
    """把透明度统一成 ``[0, 1]`` 的 float。

    :param value: ``float`` / ``int`` / 数字字符串；``None`` 表示用 ``default``
    :param default: 解析失败（或 ``None``）时的回退值
    :returns: 夹到 ``[0, 1]`` 的浮点数；``NaN`` 与非法值都回退到 ``default``
    """
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:  # NaN
        return default
    if result < 0.0:
        return 0.0
    if result > 1.0:
        return 1.0
    return result


def _named_to_rgb(name: str) -> Optional[Tuple[int, int, int]]:
    try:
        from PIL import ImageColor
    except Exception:  # pragma: no cover - Pillow 是 tkdeft 的硬依赖
        return None
    try:
        rgb = ImageColor.getrgb(name)
    except Exception:
        return None
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def parse_color(value, opacity=1.0) -> Optional[RGBA]:
    """解析颜色 + 透明度。

    :param value: 颜色写法（见模块文档）；``None`` / ``"transparent"`` 表示不绘制
    :param opacity: 外层透明度，会与颜色自带的 alpha **相乘**（元组色与
        ``#RRGGBBAA`` 都适用）
    :returns: ``(r, g, b, a)``；当颜色表示"不绘制"、解析失败或最终 alpha 为 0 时
        返回 ``None``，调用方据此完全跳过这一层的绘制

    ::

        parse_color("#ffffff", 0.2)   # (255, 255, 255, 51)
        parse_color((0, 0, 0, 128))   # (0, 0, 0, 128)
        parse_color("transparent")    # None
    """
    alpha = parse_opacity(opacity)

    if value is None:
        return None

    if isinstance(value, (tuple, list)):
        parts = list(value)
        if len(parts) == 3:
            r, g, b = (int(max(0, min(255, p))) for p in parts)
            a = int(round(alpha * 255))
        elif len(parts) >= 4:
            r, g, b = (int(max(0, min(255, p))) for p in parts[:3])
            a = int(max(0, min(255, parts[3])))
            # 元组自带 alpha 时，外层 opacity 视为额外调制
            a = int(round(a * alpha))
        else:
            return None
        return (r, g, b, a) if a > 0 else None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if text.lower() in _TRANSPARENT_WORDS:
        return None

    rgb: Optional[Tuple[int, int, int]] = None
    embedded_alpha: Optional[int] = None

    if text.startswith("#"):
        h = text[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 4:  # #RGBA
            h = "".join(ch * 2 for ch in h)
        if len(h) == 8:  # #RRGGBBAA
            try:
                embedded_alpha = int(h[6:8], 16)
            except ValueError:
                return None
            h = h[:6]
        if len(h) != 6:
            return None
        try:
            rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except ValueError:
            return None
    else:
        rgb = _named_to_rgb(text)

    if rgb is None:
        return None

    a = alpha if embedded_alpha is None else (embedded_alpha / 255.0) * alpha
    a_int = int(round(a * 255))
    if a_int <= 0:
        return None
    return (rgb[0], rgb[1], rgb[2], a_int)


def lerp_rgba(c1: RGBA, c2: RGBA, t: float) -> RGBA:
    """在两个 RGBA 之间线性插值（``t`` 会被裁剪到 ``[0, 1]``）。

    :param c1: 起点颜色（``t <= 0`` 时原样返回）
    :param c2: 终点颜色（``t >= 1`` 时原样返回）
    :param t: 插值位置
    """
    if t <= 0.0:
        return c1
    if t >= 1.0:
        return c2
    return tuple(  # type: ignore[return-value]
        int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(4)
    )
