"""tkdeft 绘制引擎层。

对外主要接口
------------
::

    from tkdeft.engines import set_engine, get_engine, render_roundrect, cache_stats

    set_engine("skia")          # 或 set_engine(2)
    photo = render_roundrect(spec, master=canvas)   # -> PhotoImage | None

``render_*`` 返回 ``None`` 表示"当前引擎不参与这条路径"，调用方应回退到
既有的 svgwrite + tksvg 实现。这样 SVG 引擎与栅格引擎可以共存于同一套组件代码。

内置引擎
--------
====== ========== ==================================================
名字    类型        说明
====== ========== ==================================================
tksvg  SVG（文件） 默认，保持既有行为完全不变
wand   SVG（文件） 经 Wand 转 PNG，兼容旧 ``renderer=1``
skia   栅格        skia-python，质量与速度最好
pillow 栅格        Pillow 超采样，零额外依赖，永远可用
cairo  栅格        pycairo
====== ========== ==================================================
"""

from __future__ import annotations

import warnings
from typing import Optional

from .base import (
    DrawEngine,
    RoundRectSpec,
    SvgEngine,
    ThumbSpec,
    TrackSpec,
    get_engine,
    get_engine_name,
    list_engines,
    register_engine,
    set_engine,
)
from .cache import (
    cache_stats,
    clear_cache,
    get_cache,
    set_cache_budget,
)
from .cairo_engine import CairoEngine
from .colors import parse_color, parse_opacity
from .pillow_engine import PillowEngine
from .skia_engine import SkiaEngine

__all__ = [
    "DrawEngine",
    "RoundRectSpec",
    "TrackSpec",
    "ThumbSpec",
    "SvgEngine",
    "register_engine",
    "get_engine",
    "get_engine_name",
    "set_engine",
    "list_engines",
    "render_roundrect",
    "render_track",
    "render_thumb",
    "to_photoimage",
    "clear_cache",
    "cache_stats",
    "set_cache_budget",
    "parse_color",
    "parse_opacity",
    "engine_error",
]

# --------------------------------------------------------------------------
# 引擎注册
# --------------------------------------------------------------------------
class TksvgEngine(SvgEngine):
    name = "tksvg"
    requires = ("tksvg",)
    description = "svgwrite + tksvg（默认，保持既有行为）"


class WandEngine(SvgEngine):
    name = "wand"
    requires = ("wand",)
    description = "svgwrite + Wand（ImageMagick）"


#: 与历史 ``set_renderer(int)`` API 的对应关系
RENDERER_INDEX = {0: "tksvg", 1: "wand", 2: "skia", 3: "pillow", 4: "cairo"}

register_engine(TksvgEngine(), aliases=("0", "svg", "default"), default=True)
register_engine(WandEngine(), aliases=("1", "1.0"))
register_engine(SkiaEngine(), aliases=("2",))
register_engine(PillowEngine(), aliases=("3", "pil"))
register_engine(CairoEngine(), aliases=("4", "pycairo"))

#: 最近一次栅格化失败的原因，便于诊断（``None`` 表示正常）
engine_error: Optional[str] = None

_WARNED: "set[str]" = set()


def _warn_once(engine_name: str, exc: BaseException) -> None:
    global engine_error
    engine_error = f"{engine_name}: {type(exc).__name__}: {exc}"
    if engine_name in _WARNED:
        return
    _WARNED.add(engine_name)
    warnings.warn(
        f"绘制引擎 {engine_name!r} 渲染失败，已回退到 SVG 路径。"
        f"原始错误：{engine_error}",
        RuntimeWarning,
        stacklevel=3,
    )


def to_photoimage(image, master):
    """``PIL.Image`` → ``tkinter`` 的 ``PhotoImage``。"""
    from PIL import ImageTk

    return ImageTk.PhotoImage(image, master=master)


def _render(kind: str, spec, master):
    """三种图元共用的"查缓存 → 渲染 → 转 PhotoImage → 回填缓存"流程。"""
    engine = get_engine()
    if not engine.is_raster:
        return None

    key = (engine.name, kind, spec)
    cache = get_cache(master)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        image = getattr(engine, f"render_{kind}")(spec)
    except Exception as exc:  # 单个引擎出错不应让整个界面挂掉
        _warn_once(engine.name, exc)
        return None

    if image is None:
        return None

    photo = to_photoimage(image, master)
    cache.put(key, photo, max(1, int(spec.width) * int(spec.height)))
    return photo


def render_roundrect(spec: RoundRectSpec, master):
    """渲染圆角矩形；当前引擎不支持时返回 ``None``。"""
    return _render("roundrect", spec, master)


def render_track(spec: TrackSpec, master):
    """渲染滑块进度条槽；当前引擎不支持时返回 ``None``。"""
    return _render("track", spec, master)


def render_thumb(spec: ThumbSpec, master):
    """渲染滑块把手；当前引擎不支持时返回 ``None``。"""
    return _render("thumb", spec, master)
