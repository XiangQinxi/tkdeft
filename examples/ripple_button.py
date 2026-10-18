"""Material 涟漪按钮示例：用 ``tkdeft.extra.ripple`` 给一个自绘按钮加涟漪。

``tkdeft.extra.ripple`` 只提供**涟漪功能**，不提供按钮。这个文件才定义按钮：
圆角底色、悬停/按压/禁用状态、文字、焦点环，再加上三行涟漪调用。

运行::

    python examples/ripple_button.py                   # 自动挑最快的栅格引擎
    python examples/ripple_button.py --engine tksvg     # SVG 后端，效果一样
    python examples/ripple_button.py --theme dark
    python examples/ripple_button.py --check            # 不开窗口的自检

拆解讲解见文档站 ``usage/ripple-button`` 一页。
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Dict, Optional

from easydict import EasyDict

from tkdeft import DDrawWidget
from tkdeft.engines import available_engines, set_engine
from tkdeft.extra.ripple import (
    Ripple,
    ease_out_cubic,
    ripple_alpha,
    ripple_layer,
    ripple_radius,
)

# Windows 控制台默认是 GBK，中文和箭头容易乱码
sys.stdout.reconfigure(encoding="utf-8")

__all__ = ["THEMES", "RippleButton", "DemoApp", "check", "main"]

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


def _ui_font(size: int, weight: str = "normal"):
    """复制一份系统默认字体并调大小——比自己写家族名可靠。"""
    font = tkfont.nametofont("TkDefaultFont").copy()
    font.configure(size=size, weight=weight)
    return font


class RippleButton(DDrawWidget):
    """带涟漪的圆角按钮——顺带演示怎么把涟漪接到自己的控件上。"""

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

        # ① 建一个涟漪控制器：它只记账和计时，每帧回调我们自己重绘
        self.ripple = Ripple(self, on_frame=self._paint)

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
        """当前主题的配色字典。"""
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
        self.addtag_withtag("body", body)

        # 2) ② 在这一层贴涟漪：压在底色之上、文字之下
        if state != "disabled":
            self.ripple.paint(
                color=self.palette["ripple"],
                opacity=self.ripple_opacity(),
                corner_radius=radius,
            )

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

    def ripple_opacity(self) -> float:
        """涟漪峰值 alpha：配置优先，否则跟随主题。"""
        configured = self.dcget("ripple_opacity", None)
        if configured is None:
            return float(self.palette["ripple_opacity"])
        return float(configured)

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _event_map(self, event=None):
        """窗口第一次真正显示出来时补画一次（``<Configure>`` 常在映射之前）。"""
        self._draw(event)

    def _event_on_button1(self, event=None):
        super()._event_on_button1(event)
        if not self.dcget("enabled", True):
            return
        self.focus_set()
        # ③ 从光标处起涟漪；控制器会按 16ms 一帧回调 _paint
        x = event.x if event is not None else self.winfo_width() / 2.0
        y = event.y if event is not None else self.winfo_height() / 2.0
        self.ripple.start(x, y)

    def _event_activate(self, event=None):
        """空格 / 回车：从中心播涟漪，并发一次 ``<<Clicked>>``。"""
        if not self.dcget("enabled", True) or not self.isfocus:
            return None
        self.ripple.start()
        self.event_generate("<<Clicked>>")
        return "break"

    def _event_destroy(self, event=None):
        if event is not None and getattr(event, "widget", None) is not self:
            return
        self.ripple.stop()


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

        self.root.bind("<KeyPress-t>", self.toggle_theme)
        self.root.bind("<KeyPress-T>", self.toggle_theme)

    def _on_clicked(self):
        self.clicks += 1
        self.status.configure(text=f"已点击 {self.clicks} 次")

    def toggle_theme(self, event=None):
        self.theme = "dark" if self.theme == "light" else "light"
        palette = THEMES[self.theme]
        self.root.configure(background=palette["page"])
        for label in (self.title_label, self.status, self.hint):
            label.configure(background=palette["page"], foreground=palette["muted"])
        self.title_label.configure(foreground=palette["text"])
        self.button.dconfigure(theme=self.theme)

    def run(self):
        self.root.mainloop()


def check(engine: Optional[str] = None) -> int:
    """自检涟漪的几何/透明度，以及控制器接到按钮上能不能真的跑起来。

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
    expect(layer.size == (160, 40), "图层与控件等大")

    widths = []
    for progress in (0.2, 0.5, 0.9):
        box = ripple_layer(160, 40, 8, 80, 20, progress).getbbox()
        widths.append(0 if box is None else box[2] - box[0])
    expect(widths[0] < widths[1] <= widths[2], f"涟漪随时间扩散（{widths}）")

    print("== 控制器接到控件上（需要一个能映射窗口的桌面）==")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"  [SKIP] 没有可用的 Tk 显示：{exc}")
        root = None

    if root is not None:
        clicked = []
        root.geometry("320x140+160+160")
        button = RippleButton(root, text="涟漪按钮", command=lambda: clicked.append(1))
        button.pack(pady=44)
        root.update()
        if not button.winfo_ismapped():
            print("  [SKIP] 窗口没能映射（当前会话没有可用桌面）")
            root.destroy()
        else:
            expect(len(button.find_all()) >= 2, "映射后画出了底色与文字")
            expect(isinstance(button.ripple, Ripple), "按钮持有一个 Ripple 控制器")

            start = time.monotonic() - 0.2  # 直接快进到 40% 进度
            button.ripple.start(80, 24, started=start)
            root.update()
            expect(button.ripple.active, "点击后涟漪在播")
            button._paint()               # 宿主自己在下一帧会这么调
            button.update_idletasks()
            expect(len(button.find_withtag("ripple")) == 1, "涟漪是一层独立贴图")
            expect(len(button._photo_refs) < 256, "动画没有堆积图片引用")

            button.ripple.stop()
            button._paint()
            button.update_idletasks()
            expect(not button.find_withtag("ripple"), "停止后涟漪图层被移除")

            button.event_generate("<<Clicked>>")
            root.update()
            expect(len(clicked) == 1, "<<Clicked>> 调到 command 且只调一次")
            button.dconfigure(theme="dark")
            root.update()
            expect(button.palette["page"] == "#202020", "dconfigure(theme=) 换到深色主题")
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
    parser.add_argument("--check", action="store_true", help="只做自检，不开窗口")
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
