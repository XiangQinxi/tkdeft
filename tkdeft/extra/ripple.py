"""Material 涟漪按钮：``tkdeft.extra`` 里的成品控件。

用法::

    import tkinter

    from tkdeft.extra import RippleButton

    root = tkinter.Tk()
    button = RippleButton(root, text="确定", command=lambda: print("clicked"))
    button.pack(padx=24, pady=24)
    root.mainloop()

涟漪是一张半透明图层：**圆角矩形遮罩 ∩ 扩散圆**，由 Pillow 现场合成——
Tk 的 canvas item 没有 alpha，遮不住圆角；而 Pillow 一次就能把半透明、
圆角裁剪和抗锯齿都做对。按钮的底色与描边仍然走 tkdeft 的绘制引擎，
所以 ``set_engine("skia")`` 这类设置对它依然有效。

* 状态位 ``enter`` / ``button1`` / ``isfocus`` 由
  :class:`~tkdeft.windows.drawwidget.DDrawWidget` 维护，一变就重绘；
* 点击（鼠标在控件内松开，或空格/回车）会调用 ``command`` 并生成
  ``<<Clicked>>``；
* 配色在 :data:`THEMES` 里，``dconfigure(theme="dark")`` 即换肤。

.. note::
   本模块依赖 Pillow（tkdeft 本身已经依赖它）。动画建议用进程内栅格引擎
   （``skia`` / ``cairo`` / ``pillow``）：SVG 引擎每帧都要写临时文件再解析，
   涟漪会明显掉帧，功能本身仍然正确。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from tkinter import font as tkfont
from typing import Dict, Optional

from easydict import EasyDict
from PIL import Image, ImageChops, ImageDraw, ImageTk

from ..windows.drawwidget import DDrawWidget

__all__ = [
    "THEMES",
    "RIPPLE_MS",
    "FRAME_MS",
    "SUPERSAMPLE",
    "ease_out_cubic",
    "ripple_alpha",
    "ripple_radius",
    "ripple_layer",
    "RippleButton",
]

#: 一次涟漪的总时长（毫秒）。Material 规范里大控件约 450–600ms。
RIPPLE_MS = 500

#: 动画帧间隔。16ms 约等于 60fps；渲染跟不上时 Tk 会自然丢帧。
FRAME_MS = 16

#: 栅格化涟漪时的超采样倍率（最后缩小，边缘才不锯齿）。
SUPERSAMPLE = 3

#: 配色字典。换主题＝换一份字典再重绘，不需要改绘制代码。
#: 可以通过 ``RIPPLE_THEMES["mine"] = {...}`` 追加自己的主题。
THEMES: Dict[str, Dict[str, object]] = {
    "light": {
        "page": "#f3f3f3",
        "rest": "#ffffff",
        "hover": "#f7f7f7",
        "pressed": "#ededed",
        "disabled": "#f0f0f0",
        "outline": "#000000",
        "outline_opacity": 0.12,
        "text": "#1b1b1b",
        "text_disabled": "#8a8a8a",
        "muted": "#6b6b6b",
        "ripple": "#000000",
        "ripple_opacity": 0.12,
        "focus": "#005fb8",
    },
    "dark": {
        "page": "#202020",
        "rest": "#2b2b2b",
        "hover": "#333333",
        "pressed": "#262626",
        "disabled": "#262626",
        "outline": "#ffffff",
        "outline_opacity": 0.10,
        "text": "#f5f5f5",
        "text_disabled": "#7a7a7a",
        "muted": "#a0a0a0",
        "ripple": "#ffffff",
        "ripple_opacity": 0.16,
        "focus": "#60cdff",
    },
}


# ----------------------------------------------------------------------
# 涟漪的数学：半径、不透明度、图层
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
    """从 ``(x, y)`` 到最远角的距离——涟漪扩到它才算盖满整个按钮。

    :param width: 按钮宽度
    :param height: 按钮高度
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
    radius: float,
    x: float,
    y: float,
    progress: float,
    color: str = "#000000",
    peak_opacity: float = 0.12,
) -> Image.Image:
    """算出某一帧的涟漪图层（RGBA，尺寸就是按钮尺寸）。

    为什么不用 ``Canvas.create_oval``：Tk 的 canvas item 没有 alpha——
    给 canvas item 设 ``-alpha`` 是整块位图的透明度，而且**圆角遮不住**。
    这里改成在 Pillow 里先画「圆 ∩ 圆角矩形」的遮罩，再整体缩小：
    半透明、圆角裁剪、抗锯齿就都对了。

    :param width: 按钮宽度（像素）
    :param height: 按钮高度（像素）
    :param radius: 按钮圆角半径，用来裁剪涟漪
    :param x: 涟漪圆心 x（控件坐标）
    :param y: 涟漪圆心 y
    :param progress: ``0``–``1`` 的播放进度
    :param color: 涟漪颜色
    :param peak_opacity: 最浓时的 alpha
    :returns: 与按钮等大的 RGBA 图层，进度 0/1 时完全透明
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
        (0, 0, size[0] - 1, size[1] - 1), radius=radius * scale, fill=255
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


def _ui_font(size: int, weight: str = "normal"):
    """复制一份系统默认字体并调大小——比自己写家族名可靠。"""
    font = tkfont.nametofont("TkDefaultFont").copy()
    font.configure(size=size, weight=weight)
    return font


@dataclass
class _Ripple:
    """一次涟漪的状态：圆心 + 开始时刻（``time.monotonic()``）。"""

    x: float
    y: float
    started: float

    def progress(self) -> float:
        elapsed_ms = (time.monotonic() - self.started) * 1000.0
        return min(1.0, max(0.0, elapsed_ms / RIPPLE_MS))


# ----------------------------------------------------------------------
# 控件
# ----------------------------------------------------------------------
class RippleButton(DDrawWidget):
    """带 Material 涟漪的圆角按钮。

    :class:`~tkdeft.windows.drawwidget.DDrawWidget` 本身就是一种
    :class:`~tkdeft.windows.canvas.DCanvas`，所以继承它就有「能画圆角矩形」
    和 ``enter`` / ``button1`` / ``isfocus`` 三个状态位 + ``<<Clicked>>`` 事件。

    :param master: 父容器
    :param text: 按钮文字
    :param theme: :data:`THEMES` 里的主题名（``"light"`` / ``"dark"``）
    :param command: 点击回调（与 ``tk.Button`` 一致，不带参数）
    :param font: 文字字体，默认是系统默认字体加粗；传 ``tkinter.font.Font`` 可覆盖

    可配置项（用 ``dconfigure`` 修改，改完立即重绘）：

    ``text``
        按钮文字。
    ``theme``
        主题名，决定 :attr:`palette`。
    ``enabled``
        置 ``False`` 时按钮变灰且不响应点击，状态查询返回 ``"disabled"``。
    ``corner_radius``
        圆角半径，默认 ``8``；会自动夹到不超过一半宽高。
    ``ripple_opacity``
        涟漪峰值 alpha；``None`` 表示跟随主题。
    ``font``
        字体对象；``None`` 表示用默认字体。
    """

    attributes = EasyDict(
        {
            "text": "涟漪按钮",
            "theme": "light",
            "enabled": True,
            "corner_radius": 8,
            "ripple_opacity": None,
            "font": None,
        }
    )

    def __init__(
        self,
        master=None,
        *,
        text: str = "涟漪按钮",
        theme: str = "light",
        command=None,
        font=None,
        **kwargs
    ):
        kwargs.setdefault("width", 200)
        kwargs.setdefault("height", 48)
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("takefocus", 1)
        kwargs.setdefault("background", THEMES["light"]["page"])
        super().__init__(master, **kwargs)

        self.attributes = EasyDict(dict(type(self).attributes))
        self.attributes.text = text
        self.attributes.theme = theme
        self.attributes.font = font
        self.command = command

        self._default_font = _ui_font(10, "bold")
        self._ripple: Optional[_Ripple] = None
        self._job: Optional[str] = None

        # <<Clicked>> 由基类在"鼠标在控件内松开"时发出；空格/回车这里也补一次，
        # 统一由它触发 command，避免两条路径各调一次。
        self.bind("<<Clicked>>", self._invoke_command, add="+")
        self.bind("<space>", self._event_activate, add="+")
        self.bind("<Return>", self._event_activate, add="+")
        self.bind("<Map>", self._event_map, add="+")
        self.bind("<Destroy>", self._event_destroy, add="+")

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    @property
    def palette(self) -> Dict[str, object]:
        """当前主题的配色字典（``THEMES`` 里的一项）。"""
        return THEMES.get(self.dcget("theme", "light"), THEMES["light"])

    @property
    def font(self):
        """实际使用的字体：配置了就用配置的，否则用默认加粗字体。"""
        return self.dcget("font", None) or self._default_font

    def dconfigure(self, *args, **kwargs) -> "RippleButton":
        """改配置后立即重绘（``dconfigure(theme="dark")`` 就能换主题）。"""
        super().dconfigure(*args, **kwargs)
        self._draw()
        return self

    def _invoke_command(self, event=None):
        """``<<Clicked>>`` 的默认处理：调用 ``command``。"""
        if not self.dcget("enabled", True):
            return None
        if self.command is not None:
            self.command()
        return None

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _draw(self, event=None):
        super()._draw(event)
        if self.winfo_ismapped():
            self._paint()

    def _paint(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return

        palette = self.palette
        state = self.interaction_state(self.dcget("enabled", True))
        radius = float(
            min(self.dcget("corner_radius", 8), width / 2.0, height / 2.0)
        )

        self.delete("all")

        # 1) 底色 + 1px 描边：交给绘制引擎（栅格引擎会命中缓存）
        fill = palette["disabled"] if state == "disabled" else palette[state]
        body = self.draw_roundrect(
            0,
            0,
            width,
            height,
            radius,
            fill=fill,
            outline=palette["outline"],
            outline_opacity=palette["outline_opacity"],
            width=1,
            temppath=self.temppath,
        )
        # draw_* 的返回值就是 canvas item id；打标签方便「只删某一件」
        self.addtag_withtag("body", body)

        # 2) 涟漪：压在底色之上、文字之下
        if self._ripple is not None and state != "disabled":
            self._draw_ripple(width, height, radius)

        # 3) 文字
        text_color = (
            palette["text_disabled"] if state == "disabled" else palette["text"]
        )
        self.create_text(
            width / 2.0,
            height / 2.0,
            text=self.dcget("text", ""),
            fill=text_color,
            font=self.font,
            tags=("text",),
        )

        # 4) 键盘焦点环：画在最上层，向内缩 3px，不压住文字
        if self.isfocus and state != "disabled":
            ring = self.draw_roundrect(
                3,
                3,
                width - 3,
                height - 3,
                max(radius - 3.0, 1.0),
                fill="transparent",
                outline=palette["focus"],
                outline_opacity=1.0,
                width=2,
                temppath=self.temppath2,
            )
            self.addtag_withtag("focus", ring)

    def _ripple_opacity(self) -> float:
        """涟漪峰值 alpha：配置优先，否则跟随主题。"""
        configured = self.dcget("ripple_opacity", None)
        if configured is None:
            return float(self.palette["ripple_opacity"])
        return float(configured)

    def _draw_ripple(self, width: int, height: int, radius: float):
        ripple = self._ripple
        if ripple is None:
            return
        layer = ripple_layer(
            width,
            height,
            radius,
            ripple.x,
            ripple.y,
            ripple.progress(),
            color=self.palette["ripple"],
            peak_opacity=self._ripple_opacity(),
        )
        photo = ImageTk.PhotoImage(layer, master=self)
        item = self.create_image(0, 0, anchor="nw", image=photo, tags=("ripple",))
        # Tk 不会自己保住 PhotoImage，松手就变白板
        self._keep_photo(item, photo)

    # ------------------------------------------------------------------
    # 涟漪动画
    # ------------------------------------------------------------------
    def ripple(self, x: float, y: float, started: Optional[float] = None) -> None:
        """从 ``(x, y)`` 起播一次涟漪。

        :param x: 圆心 x（控件坐标）
        :param y: 圆心 y
        :param started: 起始时刻（``time.monotonic()``）；给自检/截图复现用，
            传 ``time.monotonic() - 0.2`` 就等于快进到 40% 进度
        """
        self._stop_tick()
        self._ripple = _Ripple(
            float(x), float(y), time.monotonic() if started is None else started
        )
        self._paint()
        self._schedule()

    def stop_ripple(self) -> None:
        """立刻停掉正在播的涟漪并擦干净。"""
        self._stop_tick()
        self._ripple = None
        self._paint()

    def _schedule(self):
        if self._job is None and self._ripple is not None:
            self._job = self.after(FRAME_MS, self._tick)

    def _stop_tick(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _tick(self):
        self._job = None
        if not self.winfo_exists() or self._ripple is None:
            return
        if self._ripple.progress() >= 1.0:
            # 最后一帧把涟漪擦掉，纹理和叠加层都回到静止状态
            self._ripple = None
            self._paint()
            return
        self._paint()
        self._schedule()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _event_map(self, event=None):
        """窗口第一次真正显示出来时补画一次。

        ``DDrawWidget._draw`` 在 ``winfo_ismapped()`` 为假时直接返回（那时的
        ``winfo_width()`` 还是 1）。而「先把控件 pack 好、再 ``mainloop()``」
        的写法里，``<Configure>`` 往往在映射**之前**就发完了，之后不会再来
        一次——所以只靠基类的绑定，按钮会一直空着，直到鼠标划过才画出来。
        """
        self._draw(event)

    def _event_on_button1(self, event=None):
        super()._event_on_button1(event)
        if not self.dcget("enabled", True):
            return
        self.focus_set()
        x = event.x if event is not None else self.winfo_width() / 2.0
        y = event.y if event is not None else self.winfo_height() / 2.0
        self.ripple(x, y)

    def _event_activate(self, event=None):
        """空格 / 回车：从中心播涟漪，并发一次 ``<<Clicked>>``。"""
        if not self.dcget("enabled", True) or not self.isfocus:
            return None
        self.ripple(self.winfo_width() / 2.0, self.winfo_height() / 2.0)
        self.event_generate("<<Clicked>>")
        return "break"

    def _event_destroy(self, event=None):
        if event is not None and getattr(event, "widget", None) is not self:
            return
        self._stop_tick()
        self._ripple = None
