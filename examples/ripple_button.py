"""Material 涟漪按钮：把 tkdeft 的零件拼成一个真控件。

这个示例只做一件事——**点击时从光标位置扩散一圈半透明涟漪**，
顺便把 tkdeft 的四个零件串起来：

=============== ======================================================
零件            在这里负责什么
=============== ======================================================
``DObject``     保存配置（文字、主题、圆角半径……），改完即重绘
``DCanvas``     圆角底色/描边交给绘制引擎，换引擎只需 ``set_engine``
``DDrawWidget`` 维护 ``enter`` / ``button1`` / ``isfocus``，一变就重绘
``Pillow``      只做引擎不做的两件事：**半透明**叠色与**按圆角裁剪**
=============== ======================================================

运行::

    python examples/ripple_button.py                   # 自动挑最快的栅格引擎
    python examples/ripple_button.py --engine tksvg     # SVG 后端，效果一样
    python examples/ripple_button.py --theme dark
    python examples/ripple_button.py --check            # 不开窗口的自检

依赖只有 tkdeft 与 Pillow（tkdeft 本身已经依赖 Pillow）。文档页见
``docs/docs/examples/ripple-button.md``。
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from typing import Dict, Optional

from easydict import EasyDict
from PIL import Image, ImageChops, ImageDraw, ImageTk

from tkdeft import DDrawWidget
from tkdeft.engines import available_engines, set_engine

# Windows 控制台默认是 GBK，中文和箭头容易乱码
sys.stdout.reconfigure(encoding="utf-8")

__all__ = [
    "THEMES",
    "RIPPLE_MS",
    "FRAME_MS",
    "ease_out_cubic",
    "ripple_alpha",
    "ripple_radius",
    "ripple_layer",
    "RippleButton",
    "main",
]

#: 一次涟漪的总时长（毫秒）。Material 规范里大控件约 450–600ms。
RIPPLE_MS = 500

#: 动画帧间隔。16ms 约等于 60fps；渲染跟不上时 Tk 会自然丢帧。
FRAME_MS = 16

#: 栅格化涟漪时的超采样倍率（最后缩小，边缘才不锯齿）。
SUPERSAMPLE = 3

#: 配色字典。换主题＝换一份字典再重绘，不需要改绘制代码。
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
    """Material 的「减速」曲线：起步快、收尾慢。"""
    progress = min(1.0, max(0.0, progress))
    return 1.0 - (1.0 - progress) ** 3


def ripple_alpha(progress: float, peak: float = 0.12) -> float:
    """涟漪的不透明度：前 15% 淡入，之后按幂曲线淡出。"""
    if progress <= 0.0 or progress >= 1.0:
        return 0.0
    fade_in = min(1.0, progress / 0.15)
    fade_out = max(0.0, 1.0 - (progress - 0.15) / 0.85) ** 1.2
    return peak * fade_in * fade_out


def ripple_radius(width: float, height: float, x: float, y: float) -> float:
    """从 ``(x, y)`` 到最远角的距离——涟漪扩到它才算盖满整个按钮。"""
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
    这里改成在 Pillow 里先画「圆 ∩ 圆角矩形」的遮罩，再整体缩放：
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
    :param theme: ``THEMES`` 里的主题名
    :param command: 点击回调（与 ``tk.Button`` 一致）
    """

    attributes = EasyDict(
        {
            "text": "涟漪按钮",
            "theme": "light",
            "enabled": True,
            "corner_radius": 8,
            "ripple_opacity": 0.12,
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
        self.command = command

        self.font = tkfont.nametofont("TkDefaultFont").copy()
        self.font.configure(size=10, weight="bold")

        self._ripple: Optional[_Ripple] = None
        self._job: Optional[str] = None

        self.bind("<space>", self._event_activate, add="+")
        self.bind("<Return>", self._event_activate, add="+")
        self.bind("<Map>", self._event_map, add="+")
        self.bind("<Destroy>", self._event_destroy, add="+")

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    @property
    def palette(self) -> Dict[str, object]:
        """当前主题的配色字典。"""
        return THEMES.get(self.dcget("theme", "light"), THEMES["light"])

    def dconfigure(self, *args, **kwargs) -> "RippleButton":
        """改配置后立即重绘（``dconfigure(theme="dark")`` 就能换主题）。"""
        super().dconfigure(*args, **kwargs)
        self._draw()
        return self

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _draw(self, event=None):
        super()._draw(event)
        if not self.winfo_ismapped():
            return
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
        # draw_* 的返回值就是 canvas item id；打标签方便"只删某一件"
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
            peak_opacity=self.dcget(
                "ripple_opacity", self.palette["ripple_opacity"]
            ),
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

        :param started: 起始时刻（``time.monotonic()``）；给自检/截图复现用
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
        ``winfo_width()`` 还是 1）。而"先把控件 pack 好、再 ``mainloop()``"
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


# ----------------------------------------------------------------------
# 演示窗口
# ----------------------------------------------------------------------
class DemoApp:
    """一个最小窗口：标题 + 按钮 + 状态行，按 ``T`` 换主题。"""

    def __init__(self, theme: str = "light", engine: Optional[str] = None):
        self.theme = theme if theme in THEMES else "light"
        palette = THEMES[self.theme]

        self.root = tk.Tk()
        title = "tkdeft 示例 · Material 涟漪按钮"
        if engine:
            title += f" · {engine}"
        self.root.title(title)
        self.root.geometry("460x280")
        self.root.configure(background=palette["page"])
        self.font_title = _ui_font(15, "bold")
        self.font_body = _ui_font(9)

        self.title_label = tk.Label(
            self.root,
            text="Material 涟漪按钮",
            font=self.font_title,
            background=palette["page"],
            foreground=palette["text"],
        )
        self.title_label.pack(pady=(34, 10))

        self.button = RippleButton(
            self.root, text="涟漪按钮", theme=self.theme, command=self._on_clicked
        )
        self.button.pack()

        self.clicks = 0
        self.status = tk.Label(
            self.root,
            text="点一下按钮，涟漪会从光标处扩散",
            font=self.font_body,
            background=palette["page"],
            foreground=palette["muted"],
        )
        self.status.pack(pady=(18, 0))

        self.hint = tk.Label(
            self.root,
            text="空格 = 中心触发 · T = 切换主题",
            font=self.font_body,
            background=palette["page"],
            foreground=palette["muted"],
        )
        self.hint.pack(side="bottom", pady=16)

        self.button.bind("<<Clicked>>", self._on_clicked)
        self.root.bind("<KeyPress-t>", self.toggle_theme)
        self.root.bind("<KeyPress-T>", self.toggle_theme)

    def _on_clicked(self, event=None):
        self.clicks += 1
        self.status.configure(text=f"已点击 {self.clicks} 次")

    def toggle_theme(self, event=None):
        self.theme = "dark" if self.theme == "light" else "light"
        palette = THEMES[self.theme]
        self.root.configure(background=palette["page"])
        for label in (self.title_label, self.status, self.hint):
            label.configure(
                background=palette["page"], foreground=palette["muted"]
            )
        self.title_label.configure(foreground=palette["text"])
        # dconfigure 内部会重绘，配色字典换掉就完成了换肤
        self.button.dconfigure(theme=self.theme)

    def run(self):
        self.root.mainloop()


# ----------------------------------------------------------------------
# 自检：不开窗口也能验一半
# ----------------------------------------------------------------------
def check(engine: Optional[str] = None) -> int:
    """自检涟漪的几何/透明度，以及控件能不能真的跑完一段动画。

    :param engine: 指定绘制引擎；为空则保持 tkdeft 当前引擎
    :returns: ``0`` 全部通过，``1`` 有失败项
    """
    if engine:
        set_engine(engine)

    failures = []

    def expect(ok: bool, message: str) -> None:
        print(("  [OK]   " if ok else "  [FAIL] ") + message)
        if not ok:
            failures.append(message)

    print("== 涟漪的数学与图层（纯 Pillow，不需要桌面）==")
    expect(ease_out_cubic(0.0) == 0.0 and ease_out_cubic(1.0) == 1.0, "缓动曲线端点正确")
    expect(abs(ease_out_cubic(0.5) - 0.875) < 1e-9, "缓动曲线 0.5 → 0.875")
    expect(ripple_alpha(0.0) == 0.0 and ripple_alpha(1.0) == 0.0, "进度 0/1 不透明度为 0")
    expect(
        ripple_alpha(0.3) > ripple_alpha(0.6) > ripple_alpha(0.9) > 0.0,
        "淡出段单调递减",
    )
    expect(
        abs(ripple_radius(100, 50, 0, 0) - math.hypot(100, 50)) < 1e-9,
        "半径 = 到最远角的距离",
    )

    empty = ripple_layer(160, 40, 8, 80, 20, 0.0)
    expect(empty.getbbox() is None, "progress=0 的图层完全透明")
    layer = ripple_layer(160, 40, 8, 80, 20, 0.5)
    expect(layer.getpixel((80, 20))[3] > 0, "圆心处有半透明像素")
    expect(layer.getpixel((0, 0))[3] == 0, "圆角外的像素被裁掉")
    expect(layer.size == (160, 40), "图层与按钮等大")

    widths = []
    for progress in (0.2, 0.5, 0.9):
        box = ripple_layer(160, 40, 8, 80, 20, progress).getbbox()
        widths.append(0 if box is None else box[2] - box[0])
    expect(widths[0] < widths[1] <= widths[2], f"涟漪随时间扩散（{widths}）")

    print("== 控件生命周期（需要一个能映射窗口的桌面）==")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"  [SKIP] 没有可用的 Tk 显示：{exc}")
        root = None

    if root is not None:
        root.geometry("320x140+160+160")
        button = RippleButton(root, text="涟漪按钮", command=lambda: None)
        button.pack(pady=44)
        root.update()
        if not button.winfo_ismapped():
            print("  [SKIP] 窗口没能映射（当前会话没有可用桌面）")
            root.destroy()
        else:
            expect(len(button.find_all()) >= 2, "映射后画出了底色与文字")
            start = time.monotonic() - 0.2  # 直接快进到 40% 进度
            button.ripple(80, 24, started=start)
            root.update()
            expect(button._ripple is not None, "点击后涟漪在播")
            expect(len(button.find_withtag("ripple")) == 1, "涟漪是一个独立图层")
            expect(len(button._photo_refs) < 256, "动画没有堆积图片引用")
            button.stop_ripple()
            root.update()
            expect(not button.find_withtag("ripple"), "停止后涟漪图层被移除")
            root.destroy()

    print()
    if failures:
        print(f"自检失败：{len(failures)} 项")
        for message in failures:
            print("  -", message)
        return 1
    print("自检通过")
    return 0


def _default_engine() -> Optional[str]:
    """挑一个进程内栅格引擎——涟漪动画用它最顺。"""
    available = available_engines()
    for name in ("skia", "cairo", "pillow"):
        if name in available:
            return name
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="tkdeft 示例：Material 涟漪按钮",
    )
    parser.add_argument(
        "--engine",
        choices=available_engines() or None,
        default=None,
        help="绘制引擎；默认自动挑一个栅格引擎（skia > cairo > pillow）",
    )
    parser.add_argument(
        "--theme", choices=sorted(THEMES), default="light", help="初始主题"
    )
    parser.add_argument(
        "--check", action="store_true", help="只做自检，不开窗口"
    )
    args = parser.parse_args(argv)

    if args.check:
        return check(args.engine)

    engine = args.engine or _default_engine()
    if engine:
        set_engine(engine)
        print(f"绘制引擎：{engine}")
    else:
        print("绘制引擎：tkdeft 默认（没有可用的进程内栅格引擎）")

    DemoApp(theme=args.theme, engine=engine).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
