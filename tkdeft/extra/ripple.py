"""Material 涟漪效果的可复用零件：给任意画布控件加一层涟漪。

这里**不含按钮**。控件的外观、状态、文字都由你自己画，只用这里的三样东西：

* :func:`ripple_layer` —— 算出某一帧的 RGBA 图层（圆角裁剪 + 抗锯齿 + 半透明）；
* :class:`Ripple` —— 管理「谁在扩散、扩散到哪了」，到点回调你重绘；
* :func:`ease_out_cubic` / :func:`ripple_alpha` —— 想自己控制节奏时改这两条曲线。

接到已有控件上通常只加三处::

    from tkdeft.extra.ripple import Ripple

    class MyButton(DDrawWidget):
        def __init__(self, master, **kwargs):
            super().__init__(master, **kwargs)
            self.ripple = Ripple(self, on_frame=self._paint)

        def _paint(self):
            self.delete("all")
            ...画底色...
            self.ripple.paint(color="#000000", opacity=0.12, corner_radius=8)
            ...画文字...

        def _event_on_button1(self, event):
            super()._event_on_button1(event)
            self.ripple.start(event.x, event.y)

每帧重绘由你决定：``Ripple`` 不碰 canvas item，只在 ``on_frame`` 时叫你一声，
所以涟漪压在哪一层、和文字谁先谁后，完全由 ``paint()`` 的调用位置决定。

不依赖 ``DDrawWidget`` 也行——任何有 ``create_image`` / ``winfo_width`` 的控件都能用。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from PIL import Image, ImageChops, ImageDraw, ImageTk

__all__ = [
    "RIPPLE_MS",
    "FRAME_MS",
    "SUPERSAMPLE",
    "Ripple",
    "RippleState",
    "ease_out_cubic",
    "ripple_alpha",
    "ripple_radius",
    "ripple_layer",
]

#: 一次涟漪的总时长（毫秒）。Material 规范里大控件约 450–600ms。
RIPPLE_MS = 500

#: 动画帧间隔。16ms 约等于 60fps；渲染跟不上时 Tk 会自然丢帧。
FRAME_MS = 16

#: 栅格化涟漪时的超采样倍率（最后缩小，边缘才不锯齿）。
SUPERSAMPLE = 3


# ----------------------------------------------------------------------
# 数学与图层
# ----------------------------------------------------------------------
def ease_out_cubic(progress: float) -> float:
    """Material 的「减速」曲线：起步快、收尾慢。

    :param progress: ``0``–``1`` 的播放进度（超出范围会被夹到端点上）
    :returns: ``0``–``1`` 的缓动值
    """
    progress = min(1.0, max(0.0, progress))
    return 1.0 - (1.0 - progress) ** 3


def ripple_alpha(progress: float, peak: float = 0.12) -> float:
    """涟漪的不透明度：前 15% 淡入，之后按幂曲线淡出。

    :param progress: ``0``–``1`` 的播放进度
    :param peak: 最浓时的 alpha
    :returns: 该帧的 alpha；进度 0 与 1 都返回 ``0``
    """
    if progress <= 0.0 or progress >= 1.0:
        return 0.0
    fade_in = min(1.0, progress / 0.15)
    fade_out = max(0.0, 1.0 - (progress - 0.15) / 0.85) ** 1.2
    return peak * fade_in * fade_out


def ripple_radius(width: float, height: float, x: float, y: float) -> float:
    """从 ``(x, y)`` 到最远角的距离——涟漪扩到它才算盖满整个控件。

    :param width: 控件宽度
    :param height: 控件高度
    :param x: 圆心 x
    :param y: 圆心 y
    :returns: 需要扩散到的半径
    """
    return max(
        math.hypot(corner_x - x, corner_y - y)
        for corner_x, corner_y in ((0, 0), (width, 0), (0, height), (width, height))
    )


def ripple_layer(
    width: int,
    height: int,
    corner_radius: float,
    x: float,
    y: float,
    progress: float,
    color: str = "#000000",
    peak_opacity: float = 0.12,
) -> Image.Image:
    """算出某一帧的涟漪图层（RGBA，尺寸就是控件尺寸）。

    为什么不用 ``Canvas.create_oval``：Tk 的 canvas item 没有 alpha——
    给 item 设 ``-alpha`` 是整块位图的透明度，而且**圆角遮不住**。
    这里改成在 Pillow 里先画「圆 ∩ 圆角矩形」的遮罩，再整体缩小：
    半透明、圆角裁剪、抗锯齿就都对了。

    :param width: 控件宽度（像素）
    :param height: 控件高度（像素）
    :param corner_radius: 控件圆角半径，用来裁剪涟漪（矩形控件传 ``0``）
    :param x: 涟漪圆心 x（控件坐标）
    :param y: 涟漪圆心 y
    :param progress: ``0``–``1`` 的播放进度
    :param color: 涟漪颜色
    :param peak_opacity: 最浓时的 alpha
    :returns: 与控件等大的 RGBA 图层，进度 0/1 时完全透明
    """
    width = int(round(width))
    height = int(round(height))
    layer = Image.new("RGBA", (max(width, 1), max(height, 1)), (0, 0, 0, 0))
    opacity = ripple_alpha(progress, peak_opacity)
    if width <= 0 or height <= 0 or opacity <= 0.0:
        return layer

    scale = SUPERSAMPLE
    size = (width * scale, height * scale)

    # 1) 圆角矩形遮罩：涟漪不能漫出圆角
    clip = Image.new("L", size, 0)
    ImageDraw.Draw(clip).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=corner_radius * scale, fill=255
    )

    # 2) 当前半径的圆
    r = ripple_radius(width, height, x, y) * ease_out_cubic(progress) * scale
    circle = Image.new("L", size, 0)
    ImageDraw.Draw(circle).ellipse(
        (x * scale - r, y * scale - r, x * scale + r, y * scale + r), fill=255
    )

    # 3) 交集 = 圆 ∩ 圆角矩形（darker 逐像素取较小值），再缩小做抗锯齿
    mask = ImageChops.darker(clip, circle).resize((width, height), Image.LANCZOS)
    mask = mask.point(lambda value: int(value * opacity))

    layer = Image.new("RGBA", (width, height), color)
    layer.putalpha(mask)
    return layer


# ----------------------------------------------------------------------
# 状态与动画
# ----------------------------------------------------------------------
@dataclass
class RippleState:
    """一次涟漪：圆心、开始时刻，以及「现在播到哪了」。"""

    x: float
    y: float
    started: float

    def progress(self, duration: float = RIPPLE_MS) -> float:
        """当前进度（``0``–``1``），按 ``time.monotonic()`` 现算。"""
        elapsed_ms = (time.monotonic() - self.started) * 1000.0
        return min(1.0, max(0.0, elapsed_ms / duration))


class Ripple:
    """把涟漪接到一个控件上：只管状态与计时，绘制时机交给你。

    :param widget: 宿主控件（``DCanvas`` / ``DDrawWidget`` 或任何有
        ``create_image`` / ``winfo_width`` 的 Tk 控件）；用来取尺寸、贴图层
    :param on_frame: 每帧回调，通常是宿主自己的重绘方法；``None`` 表示不自动刷新
    :param duration: 一次涟漪的时长（毫秒），默认 :data:`RIPPLE_MS`
    :param frame_ms: 帧间隔（毫秒），默认 :data:`FRAME_MS`

    控制器不保存颜色：颜色/浓度/圆角都在 :meth:`paint` 时传进来，所以同一份
    状态可以跟着主题换色，不需要重建对象。
    """

    def __init__(
        self,
        widget,
        on_frame: Optional[Callable[[], None]] = None,
        *,
        duration: float = RIPPLE_MS,
        frame_ms: int = FRAME_MS,
    ):
        self.widget = widget
        self.on_frame = on_frame
        self.duration = duration
        self.frame_ms = frame_ms

        self._states: List[RippleState] = []
        self._job: Optional[str] = None
        self._photos: Dict[int, object] = {}

        # 宿主被销毁时把 after 撤掉，免得回调打到已销毁的控件上
        try:
            widget.bind("<Destroy>", self._event_destroy, add="+")
        except Exception:            # 不是 Tk 控件（测试替身）就跳过
            pass

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    @property
    def states(self) -> List[RippleState]:
        """正在播放的涟漪（只读副本，按开始顺序）。"""
        return list(self._states)

    @property
    def active(self) -> bool:
        """是否还有涟漪在播。"""
        return bool(self._states)

    def start(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        started: Optional[float] = None,
    ) -> RippleState:
        """从 ``(x, y)`` 起播一次涟漪；不传坐标按控件中心算。

        :param x: 圆心 x（控件坐标）
        :param y: 圆心 y
        :param started: 起始时刻（``time.monotonic()``）；给自检/截图复现用，
            传 ``time.monotonic() - 0.2`` 就等于快进到 40% 进度
        :returns: 新加入的状态，可用它自己算进度
        """
        if x is None:
            x = self.widget.winfo_width() / 2.0
        if y is None:
            y = self.widget.winfo_height() / 2.0
        state = RippleState(
            float(x), float(y), time.monotonic() if started is None else started
        )
        self._states.append(state)
        self._schedule()
        return state

    def stop(self) -> None:
        """立刻停掉所有涟漪并撤掉计时器。"""
        self._stop_tick()
        self._states.clear()

    def advance(self) -> None:
        """丢掉已经播完的涟漪（一般不用手调，内部计时器会做）。"""
        self._states = [
            state for state in self._states if state.progress(self.duration) < 1.0
        ]

    # ------------------------------------------------------------------
    # 计时
    # ------------------------------------------------------------------
    def _schedule(self) -> None:
        if self._job is None and self._states:
            self._job = self.widget.after(self.frame_ms, self._tick)

    def _stop_tick(self) -> None:
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def _tick(self) -> None:
        self._job = None
        if not self._states:
            return
        self.advance()
        self._notify()
        self._schedule()

    def _notify(self) -> None:
        if self.on_frame is not None:
            self.on_frame()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def paint(
        self,
        color: str = "#000000",
        opacity: float = 0.12,
        corner_radius: float = 0.0,
        tag: str = "ripple",
    ) -> int:
        """把所有正在播的涟漪画到宿主控件上，返回最后一张图层对应的 item。

        在你自己的 ``_paint`` 里调用——位置决定层级：先画底色再调它，
        涟漪就在底色之上；之后再画文字，文字就在最上面。

        :param color: 涟漪颜色
        :param opacity: 最浓时的 alpha
        :param corner_radius: 控件圆角半径；矩形控件传 ``0``
        :param tag: 给贴图打的 canvas tag，方便宿主用 ``delete(tag)`` 单独清理
        :returns: 最后一张图层对应的 canvas item id；没有涟漪时返回 ``0``
        """
        self._prune_photos()
        width = self.widget.winfo_width()
        height = self.widget.winfo_height()
        if width <= 1 or height <= 1:
            return 0

        last = 0
        for state in self._states:
            progress = state.progress(self.duration)
            if progress >= 1.0:
                continue
            layer = ripple_layer(
                width,
                height,
                corner_radius,
                state.x,
                state.y,
                progress,
                color=color,
                peak_opacity=opacity,
            )
            photo = ImageTk.PhotoImage(layer, master=self.widget)
            item = self.widget.create_image(
                0, 0, anchor="nw", image=photo, tags=(tag,)
            )
            self._keep_photo(item, photo)
            last = item
        return last

    def _keep_photo(self, item: int, photo) -> None:
        """Tk 不会自己保住 PhotoImage：交给 DCanvas 的缓存，否则自己记账。"""
        keep = getattr(self.widget, "_keep_photo", None)
        if callable(keep):
            keep(item, photo)
            return
        if hasattr(self.widget, "_photo_refs") and isinstance(
            self.widget._photo_refs, dict
        ):
            self.widget._photo_refs[item] = photo
            return
        self._photos[item] = photo

    def _prune_photos(self) -> None:
        """删掉已被宿主 ``delete`` 过的 item 对应的照片引用。"""
        if not self._photos:
            return
        stale = [item for item in self._photos if not self.widget.type(item)]
        for item in stale:
            del self._photos[item]

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def _event_destroy(self, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not self.widget:
            return
        self._stop_tick()
        self._states.clear()
