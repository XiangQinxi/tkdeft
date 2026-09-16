"""tkdeft 绘制引擎层入口。

本包把"**画什么**"（声明式规格）与"**用什么画**"（引擎）分开：

* 规格与引擎基类在 :mod:`tkdeft.engines.base`；
* 图片缓存在 :mod:`tkdeft.engines.cache`；
* 颜色解析在 :mod:`tkdeft.engines.colors`；
* 三个进程内栅格引擎分别在 :mod:`tkdeft.engines.skia_engine` /
  :mod:`tkdeft.engines.pillow_engine` / :mod:`tkdeft.engines.cairo_engine`。

这个模块只做一件事：**把常用接口汇总到一个命名空间里**。

内置引擎
--------
====== ====== ========== ==============================================
编号   名字   类型       说明
====== ====== ========== ==============================================
0      tksvg  SVG（文件） 默认，保持既有行为完全不变
1      wand   SVG（文件） 经 Wand(ImageMagick) 转 PNG，兼容旧 ``renderer=1``
2      skia   栅格       skia-python，质量与速度最好
3      pillow 栅格       Pillow 超采样，零额外依赖，永远可用
4      cairo  栅格       pycairo
====== ====== ========== ==============================================

快速上手
--------
::

    from tkdeft.engines import RoundRectSpec, render_roundrect, set_engine

    set_engine("skia")                              # 或 set_engine(2)
    photo = render_roundrect(spec, master=canvas)   # -> PhotoImage | None

``render_*`` 返回 ``None`` 表示"当前引擎不参与这条路径"（SVG 引擎就是如此），
调用方应回退到既有的 svgwrite + tksvg 实现。这样 SVG 引擎与栅格引擎可以共存于
同一套组件代码。

注册表与诊断
------------
::

    from tkdeft.engines import list_engines, describe_engines, available_engines

    list_engines()        # {'tksvg': True, 'wand': True, 'skia': True, ...}
    available_engines()   # ['tksvg', 'wand', 'skia', 'pillow', 'cairo']
    describe_engines()    # 带编号/依赖/描述的完整表格，适合打印或喂给 CLI

缓存
----
::

    from tkdeft.engines import cache_stats, set_cache_budget, clear_cache

    cache_stats()                 # {'entries': .., 'hits': .., 'hit_rate': ..}
    set_cache_budget(16_000_000)  # 调大像素预算（默认 8M 像素）
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import (
    DEFAULT_ENGINE_NAME,
    RENDERER_INDEX,
    DrawEngine,
    RoundRectSpec,
    Spec,
    SvgEngine,
    ThumbSpec,
    TrackSpec,
    UnknownEngineError,
    available_engines,
    describe_engines,
    engine_from_index,
    engine_index,
    engine_names,
    get_engine,
    get_engine_name,
    list_engines,
    register_engine,
    reset_engine,
    set_engine,
    unregister_engine,
)
from .cache import (
    DEFAULT_PIXEL_BUDGET,
    ImageCache,
    cache_stats,
    clear_cache,
    get_cache,
    set_cache_budget,
)
from .cairo_engine import CairoEngine
from .colors import RGBA, lerp_rgba, normalize_hex, parse_color, parse_opacity
from .pillow_engine import PillowEngine
from .skia_engine import SkiaEngine

__all__ = [
    # 规格
    "Spec",
    "RoundRectSpec",
    "TrackSpec",
    "ThumbSpec",
    # 引擎与注册表
    "DrawEngine",
    "SvgEngine",
    "UnknownEngineError",
    "register_engine",
    "unregister_engine",
    "get_engine",
    "get_engine_name",
    "set_engine",
    "reset_engine",
    "list_engines",
    "available_engines",
    "engine_names",
    "engine_index",
    "engine_from_index",
    "describe_engines",
    "RENDERER_INDEX",
    "DEFAULT_ENGINE_NAME",
    # 渲染入口
    "render",
    "RENDERERS",
    "render_roundrect",
    "render_track",
    "render_thumb",
    "to_photoimage",
    "last_engine_error",
    "clear_engine_error",
    # 缓存
    "ImageCache",
    "DEFAULT_PIXEL_BUDGET",
    "get_cache",
    "clear_cache",
    "cache_stats",
    "set_cache_budget",
    # 颜色
    "RGBA",
    "parse_color",
    "parse_opacity",
    "normalize_hex",
    "lerp_rgba",
]


# --------------------------------------------------------------------------
# 内置引擎的注册
# --------------------------------------------------------------------------
class TksvgEngine(SvgEngine):
    """``svgwrite`` 生成 SVG → tksvg 栅格化（默认引擎，保持历史行为）。"""

    name = "tksvg"
    requires = ("tksvg",)
    description = "svgwrite + tksvg（默认，保持既有行为）"


class WandEngine(SvgEngine):
    """``svgwrite`` 生成 SVG → Wand(ImageMagick) 转 PNG（历史 ``renderer=1``）。"""

    name = "wand"
    requires = ("wand",)
    description = "svgwrite + Wand（ImageMagick）"


# 别名让 ``set_engine(0)`` / ``set_engine("svg")`` / ``set_engine("pil")`` 之类的
# 写法都能命中；编号别名与 :data:`RENDERER_INDEX` 保持一致。
register_engine(TksvgEngine(), aliases=("0", "svg", "default"), default=True)
register_engine(WandEngine(), aliases=("1", "1.0"))
register_engine(SkiaEngine(), aliases=("2",))
register_engine(PillowEngine(), aliases=("3", "pil"))
register_engine(CairoEngine(), aliases=("4", "pycairo"))


# --------------------------------------------------------------------------
# 渲染失败的诊断信息
# --------------------------------------------------------------------------
#: 最近一次栅格化失败的原因（``None`` 表示正常）。渲染失败不会中断界面，
#: 只会回退到 SVG 路径并在这里记一笔，便于排查。
engine_error: Optional[str] = None

_WARNED: "set[str]" = set()


def last_engine_error() -> Optional[str]:
    """最近一次渲染失败的原因；一切正常时返回 ``None``。

    比直接读 :data:`engine_error` 更明确，也不会让静态检查器以为你在读、
    写一个普通全局变量。
    """
    return engine_error


def clear_engine_error() -> None:
    """清掉失败记录，并允许下次失败时重新发出一次警告。"""
    global engine_error
    engine_error = None
    _WARNED.clear()


def _warn_once(engine_name: str, exc: BaseException) -> None:
    """记录失败原因；同一个引擎只警告一次，避免刷屏。"""
    global engine_error
    engine_error = f"{engine_name}: {type(exc).__name__}: {exc}"
    if engine_name in _WARNED:
        return
    _WARNED.add(engine_name)
    import warnings

    warnings.warn(
        f"绘制引擎 {engine_name!r} 渲染失败，已回退到 SVG 路径。"
        f"原始错误：{engine_error}",
        RuntimeWarning,
        stacklevel=3,
    )


# --------------------------------------------------------------------------
# 渲染入口
# --------------------------------------------------------------------------
def to_photoimage(image, master) -> Any:
    """``PIL.Image`` → ``tkinter`` 的 ``PhotoImage``。

    :param image: ``PIL.Image.Image``（RGBA）
    :param master: 目标 Tk 控件；**必须传**，否则图片会挂到默认根窗口，
        多 Tk 解释器场景下会出问题
    :returns: :class:`tkinter.PhotoImage`
    """
    from PIL import ImageTk

    if master is None:
        return ImageTk.PhotoImage(image)
    return ImageTk.PhotoImage(image, master=master)


def _render(kind: str, spec: Spec, master) -> Optional[Any]:
    """三种图元共用的"查缓存 → 渲染 → 转 PhotoImage → 回填缓存"流程。

    :returns: ``PhotoImage``；当前引擎是 SVG 系、渲染失败或图片为空时返回
        ``None``（调用方应回退到 SVG 路径）
    """
    engine = get_engine()
    if not engine.is_raster:
        return None

    key = (engine.name, kind, spec)
    cache = get_cache(master)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        image = engine.render(spec)
    except Exception as exc:  # 单个引擎出错不应让整个界面挂掉
        _warn_once(engine.name, exc)
        return None

    if image is None:
        return None

    photo = to_photoimage(image, master)
    cache.put(key, photo, spec.pixels)
    return photo


def render(spec: Spec, master) -> Optional[Any]:
    """渲染任意一种绘制规格，按规格类型自动分发。

    :param spec: :class:`~tkdeft.engines.base.RoundRectSpec` /
        :class:`~tkdeft.engines.base.TrackSpec` /
        :class:`~tkdeft.engines.base.ThumbSpec`
    :param master: 目标 Tk 控件
    :returns: ``PhotoImage``；当前引擎不支持时返回 ``None``

    ::

        photo = render(RoundRectSpec(width=120, height=32, rx=6), master=canvas)
    """
    return _render(spec.kind, spec, master)


def render_roundrect(spec: RoundRectSpec, master) -> Optional[Any]:
    """渲染圆角矩形；当前引擎不支持时返回 ``None``。"""
    return _render("roundrect", spec, master)


def render_track(spec: TrackSpec, master) -> Optional[Any]:
    """渲染滑块进度条槽；当前引擎不支持时返回 ``None``。"""
    return _render("track", spec, master)


def render_thumb(spec: ThumbSpec, master) -> Optional[Any]:
    """渲染滑块把手；当前引擎不支持时返回 ``None``。"""
    return _render("thumb", spec, master)


#: ``render`` 的别名表：图元类型 → 渲染函数，方便按类型分发或做成菜单
RENDERERS: Dict[str, Any] = {
    "roundrect": render_roundrect,
    "track": render_track,
    "thumb": render_thumb,
}
