"""tkdeft.extra —— 用核心零件做的可复用功能（不是成品控件）。

核心包只提供零件（画布、绘制后端、配置容器），这里放**可以直接拿去用的小功能**，
每个模块自成一体、按需加载。

当前内容：

* :mod:`tkdeft.extra.ripple` —— Material 涟漪效果：一个管理状态与计时的
  :class:`~tkdeft.extra.ripple.Ripple`，加上算出半透明图层的
  :func:`~tkdeft.extra.ripple.ripple_layer`。它不提供按钮，
  你给自己的控件加三行调用就能用::

      from tkdeft.extra.ripple import Ripple

      self.ripple = Ripple(self, on_frame=self._paint)   # ① 建控制器
      self.ripple.start(event.x, event.y)                # ② 点击处起涟漪
      self.ripple.paint(color="#000", opacity=0.12)      # ③ 在重绘里贴一层
"""

from .ripple import (
    FRAME_MS,
    RIPPLE_MS,
    SUPERSAMPLE,
    Ripple,
    RippleState,
    ease_out_cubic,
    ripple_alpha,
    ripple_layer,
    ripple_radius,
)

__all__ = [
    "Ripple",
    "RippleState",
    "RIPPLE_MS",
    "FRAME_MS",
    "SUPERSAMPLE",
    "ease_out_cubic",
    "ripple_alpha",
    "ripple_radius",
    "ripple_layer",
]
