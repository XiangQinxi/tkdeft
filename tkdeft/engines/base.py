"""tkdeft 绘制引擎抽象层。

本模块是 ``tkdeft.engines`` 的"零件库"：**绘制规格**（画什么）与
**绘制引擎**（用什么画）都在这里定义，注册表也在这里维护。

设计目标
--------
把"**画什么**"（声明式 spec）与"**用什么画**"（引擎）彻底解耦：

* 过去：每个组件在 ``Flu*Draw`` 里各自拼 svgwrite 对象 → 落盘 → tksvg 解析文件，
  导致每次 hover/按压都要走一遍磁盘 I/O + XML 解析，单帧 ~5ms。
* 现在：组件构造一个不可变的 :class:`RoundRectSpec`，交给当前引擎。
  栅格引擎（skia / pillow / cairo）进程内直接出位图，不碰磁盘；
  SVG 引擎（tksvg / wand）保持原有行为，向后兼容。

三种图元
--------
=============== ==========================================================
规格            说明
=============== ==========================================================
:class:`RoundRectSpec` 圆角矩形（可带纯色/渐变描边），按钮、面板、输入框都用它
:class:`TrackSpec`     滑块/滚动条的进度条槽（左选中 + 右底轨）
:class:`ThumbSpec`     滑块/滚动条的圆形把手（外圈伪阴影 + 两层填充）
=============== ==========================================================

用法速览
--------
::

    from tkdeft.engines import RoundRectSpec, set_engine, render_roundrect

    set_engine("skia")                       # 0=tksvg 1=wand 2=skia 3=pillow 4=cairo
    spec = RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff")
    photo = render_roundrect(spec, master=canvas)   # -> PhotoImage | None

对本模块只暴露三件事：规格、引擎基类、引擎注册表。
具体渲染入口见 :mod:`tkdeft.engines`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

__all__ = [
    "Number",
    "Spec",
    "RoundRectSpec",
    "TrackSpec",
    "ThumbSpec",
    "DrawEngine",
    "SvgEngine",
    "UnknownEngineError",
    "RENDERER_INDEX",
    "DEFAULT_ENGINE_NAME",
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
]

#: 数值类型（宽高、半径、线宽既可以是 int 也可以是 float）
Number = Union[int, float]

#: 兼容历史 ``set_renderer(int)`` API 的编号 → 引擎名映射。
#: tkfluent 直接导入这张表，请勿随意改动编号。
RENDERER_INDEX: Dict[int, str] = {
    0: "tksvg",
    1: "wand",
    2: "skia",
    3: "pillow",
    4: "cairo",
}

#: 引擎名 → 编号（:data:`RENDERER_INDEX` 的反向表）
_NAME_TO_INDEX: Dict[str, int] = {name: index for index, name in RENDERER_INDEX.items()}

#: 出厂默认引擎。栅格引擎与它在抗锯齿上有亚像素差异，为了"升级后界面一个像素都不变"，
#: 默认保持历史上一直使用的 tksvg；想要性能请显式 ``set_engine("skia")``。
DEFAULT_ENGINE_NAME = "tksvg"


# --------------------------------------------------------------------------
# 声明式绘制规格
# --------------------------------------------------------------------------
class _Spec:
    """所有绘制规格的公共基类。

    规格是**不可变**的（子类都是 ``frozen dataclass``），因此可以直接当作
    缓存键。坐标一律以自身左上角为 ``(0, 0)``——这正是各组件
    ``create_round_rectangle`` 的实际用法。
    """

    #: 图元类型，与引擎上的 ``render_<kind>()`` 方法名一一对应
    kind: ClassVar[str] = "spec"

    #: 位图宽高，由子类的 dataclass 字段提供
    width: int
    height: int

    @property
    def pixels(self) -> int:
        """这张位图的像素数（用于缓存预算核算）。"""
        return max(1, int(self.width) * int(self.height))

    def to_dict(self) -> Dict[str, Any]:
        """转成普通字典，便于日志、调试与序列化。"""
        data = {name: getattr(self, name) for name in getattr(self, "__dataclass_fields__", ())}
        data["kind"] = self.kind
        return data

    def describe(self) -> str:
        """一行人类可读的描述，用于报错与调试输出。"""
        return f"{type(self).__name__}(width={self.width}, height={self.height})"


@dataclass(frozen=True)
class RoundRectSpec(_Spec):
    """一个圆角矩形（可带纯色/渐变描边）的完整描述。

    坐标系以自身左上角为 ``(0, 0)``；``width`` / ``height`` 是**位图尺寸**，
    不是坐标对——需要坐标时用 :meth:`from_box`。

    :param width: 位图宽度（像素）
    :param height: 位图高度（像素）
    :param rx: 圆角半径（x 方向）
    :param ry: 圆角半径（y 方向）；``None`` 表示与 ``rx`` 相同
    :param fill: 填充色；``None`` / ``"transparent"`` 表示不填充
    :param fill_opacity: 填充透明度，``0``–``1``
    :param outline: 描边色；``None`` 表示不描边
    :param outline_opacity: 描边透明度
    :param outline2: 渐变描边的第二个颜色；为空则用纯色描边
    :param outline2_opacity: 渐变描边第二个颜色的透明度
    :param outline_width: 描边宽度（描边居中，几何会自动内缩半个线宽）
    :param gradient_stop1: 渐变第一个 stop 的位置（0–1）
    :param gradient_stop2: 渐变第二个 stop 的位置（0–1）
    """

    kind: ClassVar[str] = "roundrect"

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
        """实际生效的 y 方向圆角半径（``ry`` 为空时取 ``rx``）。"""
        return self.rx if self.ry is None else self.ry

    @classmethod
    def from_box(
        cls,
        x1: Number,
        y1: Number,
        x2: Number,
        y2: Number,
        radius: Number = 0,
        radiusy: Optional[Number] = None,
        **kwargs: Any,
    ) -> "RoundRectSpec":
        """按 ``(x1, y1)-(x2, y2)`` 的坐标对构造规格。

        这是给画布类 API 用的便捷入口：画布上的控件习惯用"两个角"描述矩形，
        而规格本身只关心位图尺寸。

        :returns: 新的 :class:`RoundRectSpec`；``radiusy`` 为空时保持 ``None``
            （由 :attr:`effective_ry` 回退到 ``rx``）。
        """
        return cls(
            width=max(1, int(round(float(x2) - float(x1)))),
            height=max(1, int(round(float(y2) - float(y1)))),
            rx=float(radius or 0),
            ry=None if radiusy is None else float(radiusy),
            **kwargs,
        )


@dataclass(frozen=True)
class TrackSpec(_Spec):
    """滑块的进度条槽：左半段（已选中）+ 右半段（未选中）两个圆角矩形。

    :param width: 位图宽度
    :param height: 位图高度
    :param width2: 左半段（选中部分）的宽度，会被夹到 ``0..width``
    :param radius: 圆角半径
    :param track_fill: 选中部分的颜色
    :param track_opacity: 选中部分的透明度
    :param rail_fill: 未选中底轨的颜色
    :param rail_opacity: 未选中底轨的透明度
    """

    kind: ClassVar[str] = "track"

    width: int
    height: int
    width2: float
    radius: float = 3.0
    track_fill: Optional[str] = None
    track_opacity: float = 1.0
    rail_fill: Optional[str] = None
    rail_opacity: float = 1.0

    @classmethod
    def from_box(
        cls,
        x1: Number,
        y1: Number,
        width: Number,
        height: Number,
        width2: Number,
        **kwargs: Any,
    ) -> "TrackSpec":
        """按画布坐标构造规格（``x1`` / ``y1`` 只影响摆放，不影响位图内容）。"""
        return cls(
            width=max(1, int(round(float(width)))),
            height=max(1, int(round(float(height)))),
            width2=float(width2),
            **kwargs,
        )


@dataclass(frozen=True)
class ThumbSpec(_Spec):
    """滑块的圆形把手：外圈渐变伪阴影 + 外填充 + 内填充。

    :param width: 位图宽度（通常等于把手直径 + 阴影余量）
    :param height: 位图高度
    :param r1: 外圆半径（伪阴影所在的那一圈）
    :param r2: 内圆半径
    :param fill: 外填充色（画在 ``r1 - 1`` 的圆里）
    :param fill_opacity: 外填充透明度
    :param outline: 伪阴影渐变的第一个颜色
    :param outline_opacity: 伪阴影第一个颜色的透明度
    :param outline2: 伪阴影渐变的第二个颜色
    :param outline2_opacity: 伪阴影第二个颜色的透明度
    :param inner_fill: 内圆填充色
    :param inner_fill_opacity: 内圆填充透明度
    """

    kind: ClassVar[str] = "thumb"

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

    @classmethod
    def from_box(
        cls,
        x1: Number,
        y1: Number,
        width: Number,
        height: Number,
        r1: Number,
        r2: Number,
        **kwargs: Any,
    ) -> "ThumbSpec":
        """按画布坐标构造规格（``x1`` / ``y1`` 只影响摆放，不影响位图内容）。"""
        return cls(
            width=max(1, int(round(float(width)))),
            height=max(1, int(round(float(height)))),
            r1=float(r1),
            r2=float(r2),
            **kwargs,
        )


#: 任意一种绘制规格
Spec = Union[RoundRectSpec, TrackSpec, ThumbSpec]


# --------------------------------------------------------------------------
# 异常
# --------------------------------------------------------------------------
class UnknownEngineError(ValueError):
    """请求了注册表里不存在的绘制引擎。

    继承自 :class:`ValueError`，因此历史代码里的 ``except ValueError`` 依旧有效。
    """

    def __init__(self, name: Any, available: Optional[List[str]] = None) -> None:
        self.name = name
        self.available = list(available or [])
        message = f"未知的绘制引擎 {name!r}"
        if self.available:
            message += f"；可用：{sorted(self.available)}"
        hint = _suggest_name(str(name), self.available)
        if hint:
            message += f"（你是不是想用 {hint!r}？）"
        super().__init__(message)


def _suggest_name(name: str, candidates: List[str]) -> Optional[str]:
    """给拼错的引擎名一个"你是不是想用 X"的提示。"""
    needle = name.strip().lower()
    if not needle:
        return None
    best: Optional[Tuple[int, str]] = None
    for candidate in candidates:
        # 前缀 / 包含关系优先，其次是共同前缀长度
        if candidate.startswith(needle) or needle.startswith(candidate):
            score = 1000
        else:
            common = 0
            for a, b in zip(needle, candidate):
                if a != b:
                    break
                common += 1
            score = common
        if best is None or score > best[0]:
            best = (score, candidate)
    if best is None or best[0] <= 0:
        return None
    return best[1]


# --------------------------------------------------------------------------
# 引擎基类
# --------------------------------------------------------------------------
class DrawEngine:
    """绘制引擎基类。

    子类需要声明 :attr:`name` / :attr:`kind`，并实现 :meth:`render_roundrect`
    等渲染方法：``kind == "raster"`` 的引擎会被画布用作快速路径。

    :param str name: 引擎名（注册表里的主键，小写）
    :param str kind: ``"svg"`` 或 ``"raster"``
    :param tuple requires: 依赖的 Python 模块名，供 :meth:`available` 惰性探测
    :param str description: 人类可读的一句话说明
    """

    name: str = "base"
    kind: str = "svg"  # "svg" | "raster"
    requires: Tuple[str, ...] = ()
    description: str = ""

    # -- 能力探测 ---------------------------------------------------------
    def available(self) -> bool:
        """依赖是否都能导入。

        :returns: 全部依赖可导入时为 ``True``；不装 ``skia-python`` 也不影响
            其它引擎（只有 :meth:`available` 为 ``False`` 的引擎不能选）。
        """
        import importlib.util

        for mod in self.requires:
            if importlib.util.find_spec(mod) is None:
                return False
        return True

    @property
    def is_raster(self) -> bool:
        """是否是进程内栅格引擎（只有它会参与画布快速路径）。"""
        return self.kind == "raster"

    def supports(self, kind: str) -> bool:
        """是否支持某类图元（``"roundrect"`` / ``"track"`` / ``"thumb"``）。"""
        return callable(getattr(self, f"render_{kind}", None))

    @property
    def index(self) -> int:
        """兼容历史 API 的编号（tksvg=0 … cairo=4）；不在表里时为 ``-1``。"""
        return _NAME_TO_INDEX.get(self.name, -1)

    # -- 渲染接口（栅格引擎实现）------------------------------------------
    def render_roundrect(self, spec: RoundRectSpec):
        """渲染圆角矩形，返回 ``PIL.Image.Image``（RGBA）。

        :raises NotImplementedError: 该引擎不支持这条快速路径
            （SVG 引擎会走既有的 svgwrite + tksvg 流程）。
        """
        raise NotImplementedError

    def render_track(self, spec: TrackSpec):
        """渲染滑块进度条槽，返回 ``PIL.Image.Image``（RGBA）。"""
        raise NotImplementedError

    def render_thumb(self, spec: ThumbSpec):
        """渲染滑块把手，返回 ``PIL.Image.Image``（RGBA）。"""
        raise NotImplementedError

    def render(self, spec: Spec):
        """按规格自身的类型分发到对应的 ``render_*`` 方法。

        这是一个便捷入口，等价于 ``engine.render_roundrect(spec)`` 之类，
        但调用方不需要知道规格的具体类型。
        """
        renderer = getattr(self, f"render_{spec.kind}", None)
        if renderer is None:
            raise NotImplementedError(
                f"{self.name} 不支持图元 {spec.kind!r}"
            )
        return renderer(spec)

    def close(self) -> None:
        """释放引擎持有的资源（可选的钩子，默认什么都不做）。"""

    # -- 描述 -------------------------------------------------------------
    def info(self) -> Dict[str, Any]:
        """引擎的结构化信息，供 CLI / 文档 / 诊断使用。"""
        return {
            "name": self.name,
            "index": self.index,
            "kind": self.kind,
            "available": self.available(),
            "requires": tuple(self.requires),
            "description": self.description or type(self).__doc__ or "",
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试友好
        return f"<{type(self).__name__} name={self.name!r} kind={self.kind!r}>"


class SvgEngine(DrawEngine):
    """SVG 系引擎的占位实现。

    它们不参与栅格快速路径——真正的绘制仍由各组件里既有的 ``Flu*Draw`` 代码
    完成，这里只用于在注册表里表达"当前选中的是哪个引擎"。
    """

    kind = "svg"

    def render_roundrect(self, spec):  # pragma: no cover - 有意不支持
        raise NotImplementedError(
            f"{self.name} 是 SVG 引擎，请走既有的 svgwrite + tksvg 路径"
        )

    render_track = render_roundrect
    render_thumb = render_roundrect

    def supports(self, kind: str) -> bool:
        """SVG 引擎不参与栅格快速路径，因此对任何图元都返回 ``False``。"""
        return False


# --------------------------------------------------------------------------
# 引擎注册表
# --------------------------------------------------------------------------
_ENGINES: Dict[str, DrawEngine] = {}
_CURRENT_NAME: str = DEFAULT_ENGINE_NAME


def _key(name: Any) -> str:
    """把用户输入统一成注册表的键（字符串、小写、去空白）。"""
    return str(name).strip().lower()


def register_engine(
    engine: DrawEngine,
    *,
    aliases: Tuple[str, ...] = (),
    default: bool = False,
) -> DrawEngine:
    """把一个引擎实例登记进注册表。

    :param engine: 引擎实例
    :param aliases: 额外的别名（例如 ``("2",)`` 让 ``set_engine(2)`` 也能命中），
        大小写不敏感
    :param default: 是否同时把它设为当前引擎；注册表为空时也会自动成为当前引擎
    :returns: 传入的 ``engine``，方便写成 ``register_engine(MyEngine(), aliases=...)``

    重复注册同名引擎会覆盖旧的实例（便于测试里替换引擎）。
    """
    _ENGINES[engine.name] = engine
    for alias in aliases:
        _ENGINES[_key(alias)] = engine
    if default or _CURRENT_NAME not in _ENGINES:
        _set_current(engine)
    return engine


def unregister_engine(name: str) -> bool:
    """从注册表里移除一个引擎（连同它的别名）。

    :returns: 是否真的移除了。移除当前引擎时，当前选择会回退到默认引擎
        （默认引擎也没了就退到剩下的第一个）。
    """
    global _CURRENT_NAME
    target = _ENGINES.get(_key(name))
    if target is None:
        return False
    for key in [k for k, engine in _ENGINES.items() if engine is target]:
        _ENGINES.pop(key, None)
    if _ENGINES and _CURRENT_NAME not in _ENGINES:
        if DEFAULT_ENGINE_NAME in _ENGINES:
            _CURRENT_NAME = DEFAULT_ENGINE_NAME
        else:
            _CURRENT_NAME = _ENGINES[next(iter(_ENGINES))].name
    return True


def list_engines() -> Dict[str, bool]:
    """返回 ``{引擎名: 是否可用}``（只列主名，不含别名，按编号排序）。

    ::

        >>> list_engines()
        {'tksvg': True, 'wand': True, 'skia': True, 'pillow': True, 'cairo': True}
    """
    listed = {name: engine.available() for name, engine in _ENGINES.items() if engine.name == name}
    return dict(sorted(listed.items(), key=lambda item: (_NAME_TO_INDEX.get(item[0], 99), item[0])))


def available_engines() -> List[str]:
    """当前环境里真正能用的引擎名列表。"""
    return [name for name, ok in list_engines().items() if ok]


def engine_names() -> List[str]:
    """注册表里的全部引擎名（不过滤可用性）。"""
    return list(list_engines())


def engine_index(name: Optional[str] = None) -> int:
    """取引擎对应的历史编号；``None`` 表示当前引擎。

    :raises UnknownEngineError: 引擎不存在
    :returns: ``0``–``4``；自定义引擎不在 :data:`RENDERER_INDEX` 里时返回 ``-1``
    """
    return get_engine(name).index


def engine_from_index(index: Any) -> str:
    """把历史编号翻译成引擎名。

    :raises UnknownEngineError: 编号不在 :data:`RENDERER_INDEX` 里
    """
    try:
        return RENDERER_INDEX[int(index)]
    except (KeyError, TypeError, ValueError):
        raise UnknownEngineError(index, list(RENDERER_INDEX.values())) from None


def describe_engines() -> List[Dict[str, Any]]:
    """所有引擎的结构化信息列表（按编号排序，含别名与"是否当前"）。

    与 :func:`list_engines` 相比，这里的信息更适合直接打印或喂给 CLI/文档。
    """
    aliases: Dict[str, List[str]] = {}
    for key, engine in _ENGINES.items():
        if key != engine.name:
            aliases.setdefault(engine.name, []).append(key)
    rows = []
    for name, engine in [(n, _ENGINES[n]) for n in list_engines()]:
        info = engine.info()
        info["aliases"] = tuple(sorted(aliases.get(name, ())))
        info["current"] = name == _CURRENT_NAME
        rows.append(info)
    return rows


def get_engine(name: Optional[str] = None, *, strict: bool = True) -> DrawEngine:
    """取引擎实例。

    :param name: 引擎名（大小写不敏感，可以是别名）；``None`` 表示**当前引擎**
    :param strict: 名字未知时抛 :class:`UnknownEngineError`（默认）；
        置 ``False`` 则退回当前引擎，兼容历史行为
    :raises UnknownEngineError: ``strict=True`` 且名字未知
    """
    if name is None:
        engine = _ENGINES.get(_CURRENT_NAME)
        if engine is None:  # 理论上不会发生：注册表至少有一个默认引擎
            raise RuntimeError("tkdeft 引擎注册表为空，无法解析绘制引擎")
        return engine

    engine = _ENGINES.get(_key(name))
    if engine is not None:
        return engine
    if strict:
        raise UnknownEngineError(name, list(list_engines()))
    current = _ENGINES.get(_CURRENT_NAME)
    if current is None:
        raise RuntimeError("tkdeft 引擎注册表为空，无法解析绘制引擎")
    return current


def get_engine_name() -> str:
    """当前引擎的名字（比编号直观）。"""
    return _CURRENT_NAME


def _set_current(engine: DrawEngine) -> None:
    global _CURRENT_NAME
    _CURRENT_NAME = engine.name


def set_engine(name: Any) -> DrawEngine:
    """切换当前引擎。

    ``name`` 可以是引擎名（``"skia"`` / ``"pillow"`` / ``"tksvg"`` / ``"cairo"``
    / ``"wand"``），也可以是兼容旧 API 的整数编号：

    ===== ========== ==========================================================
    编号   引擎       说明
    ===== ========== ==========================================================
    0     tksvg      SVG 文件（默认，保持既有行为）
    1     wand       SVG → PNG（ImageMagick）
    2     skia       进程内栅格，速度与画质最好
    3     pillow     进程内栅格，零额外依赖，永远可用
    4     cairo      进程内栅格（pycairo）
    ===== ========== ==========================================================

    :raises UnknownEngineError: 引擎名/编号不在注册表里
    :raises ValueError: 引擎存在但依赖缺失（报错会说明缺哪个包）

    非法或不可用的引擎都会抛异常，避免静默降级导致"以为开了 skia 其实还在走慢路径"。
    """
    try:
        engine = get_engine(name)
    except UnknownEngineError:
        # 兼容 ``set_engine(2)`` 这种历史写法
        if isinstance(name, int) and not isinstance(name, bool):
            engine = get_engine(engine_from_index(name))
        else:
            raise
    if not engine.available():
        raise ValueError(
            f"绘制引擎 {engine.name!r} 不可用，缺少依赖：{engine.requires}"
        )
    _set_current(engine)
    return engine


def reset_engine() -> DrawEngine:
    """把当前引擎恢复为出厂默认（``tksvg``），返回该引擎。"""
    return set_engine(DEFAULT_ENGINE_NAME)
