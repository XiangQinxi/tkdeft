"""tkdeft —— 把矢量绘图变成 Tkinter 控件的底座。

本包不提供具体组件，只提供零件：

* :mod:`tkdeft.engines` —— 可插拔的绘制引擎（tksvg / wand / skia / pillow / cairo）
* :mod:`tkdeft.svg` —— SVG 形状助手（统一的圆角矩形几何）
* :mod:`tkdeft.windows` —— ``DCanvas`` / ``DDraw`` / ``DSvgDraw`` / ``DDrawWidget``
* :mod:`tkdeft.object` —— ``DObject`` 配置容器
* :mod:`tkdeft.utility` —— 字体等零碎工具
* :mod:`tkdeft.extra` —— 可选的附加功能（目前是 Material 涟漪效果）

最常用的东西都从顶层再导出一份，所以下面两种写法等价::

    from tkdeft.engines import RoundRectSpec, set_engine, render_roundrect
    from tkdeft import RoundRectSpec, set_engine, render_roundrect

快速上手
--------
::

    import tkinter
    from tkdeft import DCanvas, RoundRectSpec, set_engine

    set_engine("skia")                     # 换成进程内栅格引擎（可选）

    root = tkinter.Tk()
    canvas = DCanvas(root, width=200, height=100)
    canvas.pack()
    canvas.draw_roundrect(0, 0, 120, 32, 6, fill="#ffffff", outline="#000000")
    root.mainloop()

想直接要一张图片（不起窗口）::

    photo = render_roundrect(
        RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff"),
        master=canvas,
    )

能力探测
--------
旧版本没有 :mod:`tkdeft.engines` 子包，因此依赖方用 :data:`HAS_ENGINES`
做能力探测，比解析版本号更直接::

    import tkdeft

    if getattr(tkdeft, "HAS_ENGINES", False):
        from tkdeft.engines import set_engine

附加功能
--------
:mod:`tkdeft.extra` 里是可以直接拿去用的小功能，它按需加载（用到时才 import
Pillow 的 ``ImageTk``）::

    from tkdeft.extra.ripple import Ripple
    from tkdeft import extra          # 等价，懒加载整个子包
"""

from __future__ import annotations

import importlib

from . import engines, svg, utility, windows
from .engines import (
    DEFAULT_ENGINE_NAME,
    RENDERER_INDEX,
    DrawEngine,
    RoundRectSpec,
    SvgEngine,
    ThumbSpec,
    TrackSpec,
    UnknownEngineError,
    available_engines,
    cache_stats,
    clear_cache,
    describe_engines,
    get_cache,
    get_engine,
    get_engine_name,
    list_engines,
    register_engine,
    render,
    render_roundrect,
    render_thumb,
    render_track,
    reset_engine,
    set_cache_budget,
    set_engine,
)
from .object import DObject
from .svg import add_roundrect, roundrect_geometry
from .utility import SEGOE_FONT_FILE, SegoeFont, segoe_font, segue_font_file
from .windows import (
    DCanvas,
    DDraw,
    DDrawWidget,
    DDrawWidgetCanvas,
    DDrawWidgetDraw,
    DSvgDraw,
)

#: 版本号。tkfluent 会据此判断环境里的 tkdeft 是否够新。
#: 注意：需要与 pyproject.toml 里的 version 保持一致。
__version__ = "0.3.0"

#: :data:`__version__` 的数字形式，便于比较：``(0, 3, 0)``
__version_info__ = tuple(int(part) for part in __version__.split(".") if part.isdigit())

#: 是否提供绘制引擎层（tkfluent >= 0.2.0 依赖它）。
#: 旧版本没有这个子包，用它做能力探测比解析版本号更直接。
HAS_ENGINES = True


def __getattr__(name: str):
    """按需加载 :mod:`tkdeft.extra`。

    ``import tkdeft`` 不应该顺带把 Pillow 的 ``ImageTk`` 和附加功能拉进来，
    所以这里只在真的用到时再导入::

        from tkdeft import extra          # 触发 __getattr__
    """
    if name == "extra":
        # 用 import_module 而不是 ``from . import extra``：后者会走
        # ``_handle_fromlist`` → ``getattr(self, "extra")`` → 又回到本函数，无限递归。
        return importlib.import_module(".extra", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 子包
    "engines",
    "svg",
    "utility",
    "windows",
    "extra",
    # 版本与能力探测
    "__version__",
    "__version_info__",
    "HAS_ENGINES",
    # 基础
    "DObject",
    # 画布与绘制后端
    "DCanvas",
    "DDraw",
    "DSvgDraw",
    "DDrawWidget",
    "DDrawWidgetCanvas",
    "DDrawWidgetDraw",
    "add_roundrect",
    "roundrect_geometry",
    # 字体
    "SegoeFont",
    "segue_font_file",
    "SEGOE_FONT_FILE",
    "segoe_font",
    # 绘制引擎
    "DrawEngine",
    "SvgEngine",
    "RoundRectSpec",
    "TrackSpec",
    "ThumbSpec",
    "UnknownEngineError",
    "RENDERER_INDEX",
    "DEFAULT_ENGINE_NAME",
    "register_engine",
    "get_engine",
    "get_engine_name",
    "set_engine",
    "reset_engine",
    "list_engines",
    "available_engines",
    "describe_engines",
    "render",
    "render_roundrect",
    "render_track",
    "render_thumb",
    "get_cache",
    "clear_cache",
    "cache_stats",
    "set_cache_budget",
]
