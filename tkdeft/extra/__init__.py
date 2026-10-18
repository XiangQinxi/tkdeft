"""tkdeft.extra —— 用核心零件做好的成品控件。

核心包只提供零件（画布、绘制后端、配置容器），这里放"可以直接放进窗口"的
控件。每个模块都自成一体，不导入本包就不会加载它们。

当前内容：

* :mod:`tkdeft.extra.ripple` —— :class:`~tkdeft.extra.ripple.RippleButton`，
  Material 风格的圆角按钮 + 点击处扩散的半透明涟漪

用法::

    from tkdeft.extra import RippleButton

    button = RippleButton(root, text="确定", command=on_ok)
    button.pack()

也可以从子模块导入（等价）::

    from tkdeft.extra.ripple import RippleButton
"""

from .ripple import (
    FRAME_MS,
    RIPPLE_MS,
    SUPERSAMPLE,
    THEMES,
    RippleButton,
    ease_out_cubic,
    ripple_alpha,
    ripple_layer,
    ripple_radius,
)

__all__ = [
    "RippleButton",
    "THEMES",
    "RIPPLE_MS",
    "FRAME_MS",
    "SUPERSAMPLE",
    "ease_out_cubic",
    "ripple_alpha",
    "ripple_radius",
    "ripple_layer",
]
