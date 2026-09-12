"""tkdeft 绘制引擎抽象层。

设计目标
--------
把"**画什么**"（声明式 spec）与"**用什么画**"（引擎）彻底解耦：

* 过去：每个组件在 ``Flu*Draw`` 里各自拼 svgwrite 对象 → 落盘 → tksvg 解析文件，
  导致每次 hover/按压都要走一遍磁盘 I/O + XML 解析，单帧 ~5ms。
* 现在：组件构造一个不可变的 :class:`RoundRectSpec`，交给当前引擎。
  栅格引擎（skia / pillow / cairo）进程内直接出位图，不碰磁盘；
  SVG 引擎（tksvg / wand）保持原有行为，向后兼容。

对外只暴露三个渲染函数：:func:`render_roundrect`、:func:`render_track`、
:func:`render_thumb`，它们统一返回 ``PhotoImage`` 或 ``None``
（``None`` 表示"当前引擎不支持，请回退到既有 SVG 路径"）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

__all__ = [
    "RoundRectSpec",
    "TrackSpec",
    "ThumbSpec",
    "DrawEngine",
    "SvgEngine",
    "register_engine",
    "get_engine",
    "set_engine",
    "get_engine_name",
    "list_engines",
]

Number = Union[int, float]


# --------------------------------------------------------------------------
# 声明式绘制规格
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RoundRectSpec:
    """一个圆角矩形（可带纯色/渐变描边）的完整描述。

    坐标一律以自身左上角为 ``(0, 0)``——这正是 tkfluent 各组件
    ``create_round_rectangle`` 的实际用法，因此可作为缓存键。
    """

    width: int
    height: int
    rx: float = 0.0
    ry: Optional[float] = None
    fill: Optional[str] = None
    fill_opacity: float = 1.0
    outline: Optional[str] = None
    outline_opacity: float = 1.0
    outline2: Optional[str] = None
    outline2_opacity: float = 1.0
    outline_width: float = 1.0
    # 渐变描边的两个 stop 位置（与既有 svgwrite 实现一致：0.9 / 1.0）
    gradient_stop1: float = 0.9
    gradient_stop2: float = 1.0

    @property
    def effective_ry(self) -> float:
        return self.rx if self.ry is None else self.ry


@dataclass(frozen=True)
class TrackSpec:
    """滑块的进度条槽：左半段（已选中）+ 右半段（未选中）两个圆角矩形。"""

    width: int
    height: int
    width2: float
    radius: float = 3.0
    track_fill: Optional[str] = None
    track_opacity: float = 1.0
    rail_fill: Optional[str] = None
    rail_opacity: float = 1.0


@dataclass(frozen=True)
class ThumbSpec:
    """滑块的圆形把手：外圈渐变伪阴影 + 外填充 + 内填充。"""

    width: int
    height: int
    r1: float
    r2: float
    fill: Optional[str] = None
    fill_opacity: float = 1.0
    outline: Optional[str] = None
    outline_opacity: float = 1.0
    outline2: Optional[str] = None
    outline2_opacity: float = 1.0
    inner_fill: Optional[str] = None
    inner_fill_opacity: float = 1.0


# --------------------------------------------------------------------------
# 引擎基类
# --------------------------------------------------------------------------
class DrawEngine:
    """绘制引擎基类。

    子类需要声明 :attr:`name`、:attr:`kind`，并实现 :meth:`render_roundrect`
    等渲染方法。``kind == "raster"`` 的引擎会被 tkfluent 用作快速路径。
    """

    name: str = "base"
    kind: str = "svg"  # "svg" | "raster"
    #: 依赖的 Python 模块名，供 :meth:`available` 做惰性探测
    requires: Tuple[str, ...] = ()
    #: 人类可读描述
    description: str = ""

    # -- 能力探测 ---------------------------------------------------------
    def available(self) -> bool:
        """依赖是否可导入。"""
        import importlib.util

        for mod in self.requires:
            if importlib.util.find_spec(mod) is None:
                return False
        return True

    @property
    def is_raster(self) -> bool:
        return self.kind == "raster"

    # -- 渲染接口（栅格引擎实现）------------------------------------------
    def render_roundrect(self, spec: RoundRectSpec):
        """返回 ``PIL.Image.Image``（RGBA）。不支持时抛 :class:`NotImplementedError`。"""
        raise NotImplementedError

    def render_track(self, spec: TrackSpec):
        raise NotImplementedError

    def render_thumb(self, spec: ThumbSpec):
        raise NotImplementedError

    def close(self) -> None:
        """释放引擎持有的资源（可选）。"""

    def __repr__(self) -> str:  # pragma: no cover - 调试友好
        return f"<{type(self).__name__} name={self.name!r} kind={self.kind!r}>"


class SvgEngine(DrawEngine):
    """SVG 系引擎的占位实现。

    它们不参与栅格快速路径——真正的绘制仍由 tkfluent 各组件里既有的
    ``Flu*Draw`` 代码完成，这里只用于在注册表里表达"当前选中的是哪个引擎"。
    """

    kind = "svg"

    def render_roundrect(self, spec):  # pragma: no cover - 有意不支持
        raise NotImplementedError(
            f"{self.name} 是 SVG 引擎，请走既有的 svgwrite + tksvg 路径"
        )

    render_track = render_roundrect
    render_thumb = render_roundrect


# --------------------------------------------------------------------------
# 引擎注册表
# --------------------------------------------------------------------------
_ENGINES: "dict[str, DrawEngine]" = {}
_CURRENT: "dict[str, str]" = {"name": "tksvg"}


def register_engine(engine: DrawEngine, *, aliases: Tuple[str, ...] = (),
                    default: bool = False) -> DrawEngine:
    """把一个引擎实例登记进注册表。"""
    _ENGINES[engine.name] = engine
    for alias in aliases:
        _ENGINES[alias] = engine
    if default or not _ENGINES:
        _CURRENT["name"] = engine.name
    return engine


def list_engines() -> "dict[str, bool]":
    """返回 ``{引擎名: 是否可用}``（只列主名，不含别名）。"""
    seen = {}
    for name, engine in _ENGINES.items():
        if engine.name == name:
            seen[name] = engine.available()
    return seen


def get_engine(name: Optional[str] = None) -> DrawEngine:
    """按名字取引擎；``None`` 表示当前引擎。名字未知时回退到当前/默认。"""
    if name is None:
        name = _CURRENT["name"]
    engine = _ENGINES.get(str(name).lower())
    if engine is None:
        engine = _ENGINES.get(_CURRENT["name"])
    if engine is None:  # 理论上不会发生：注册表至少有一个默认引擎
        raise RuntimeError("tkdeft 引擎注册表为空，无法解析绘制引擎")
    return engine


def get_engine_name() -> str:
    return _CURRENT["name"]


def set_engine(name) -> DrawEngine:
    """切换当前引擎。

    ``name`` 可以是引擎名（``"skia"`` / ``"pillow"`` / ``"tksvg"`` / ``"cairo"``
    / ``"wand"``），也可以是兼容旧 API 的整数编号：

    ===== ==========
    编号   引擎
    ===== ==========
    0     tksvg（默认，SVG 文件）
    1     wand（SVG → PNG）
    2     skia（进程内栅格）
    3     pillow（进程内栅格，无额外依赖）
    4     cairo（进程内栅格）
    ===== ==========

    非法或不可用的引擎会抛出 :class:`ValueError`，避免静默降级导致
    "以为开了 skia 其实还在走慢路径"。
    """
    engine = _ENGINES.get(str(name).lower())
    if engine is None:
        raise ValueError(
            f"未知的绘制引擎 {name!r}；可用：{sorted(list_engines())}"
        )
    if not engine.available():
        raise ValueError(
            f"绘制引擎 {engine.name!r} 不可用，缺少依赖：{engine.requires}"
        )
    _CURRENT["name"] = engine.name
    return engine
