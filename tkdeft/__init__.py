"""tkdeft —— 把矢量绘图变成 Tkinter 组件的底座。

本包不提供具体组件，只提供零件：

* :mod:`tkdeft.engines` —— 可插拔的绘制引擎（tksvg / wand / skia / pillow / cairo）
* :mod:`tkdeft.svg` —— SVG 形状助手（统一的圆角矩形几何）
* :mod:`tkdeft.windows` —— ``DCanvas`` / ``DDraw`` / ``DDrawWidget``
* :mod:`tkdeft.object` —— ``DObject`` 配置容器

快速上手::

    from tkdeft.engines import RoundRectSpec, render_roundrect, set_engine

    set_engine("skia")
    photo = render_roundrect(
        RoundRectSpec(width=120, height=32, rx=6, fill="#ffffff"),
        master=my_canvas,
    )
"""

from . import engines
from .utility import *
from .windows import *
from .object import DObject

#: 版本号。tkfluent 会据此判断环境里的 tkdeft 是否够新。
#: 注意：需要与 pyproject.toml 里的 version 保持一致。
__version__ = "0.2.0"

#: 是否提供绘制引擎层（tkfluent >= 0.2.0 依赖它）。
#: 旧版本没有这个子包，用它做能力探测比解析版本号更直接。
HAS_ENGINES = True
