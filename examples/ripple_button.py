"""Material 涟漪按钮示例：把 ``tkdeft.extra`` 里的成品控件跑起来。

控件本身在 :mod:`tkdeft.extra.ripple` 里，这个文件只做三件事：
起一个演示窗口、按 ``T`` 换主题、提供不开窗口的自检。

运行::

    python examples/ripple_button.py                   # 自动挑最快的栅格引擎
    python examples/ripple_button.py --engine tksvg     # SVG 后端，效果一样
    python examples/ripple_button.py --theme dark
    python examples/ripple_button.py --check            # 不开窗口的自检

写法的逐步讲解见文档站 ``usage/ripple-button`` 一页。
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

from tkdeft import DDrawWidget
from tkdeft.engines import available_engines, set_engine
from tkdeft.extra.ripple import (
    THEMES,
    RippleButton,
    ease_out_cubic,
    ripple_alpha,
    ripple_layer,
    ripple_radius,
)

# Windows 控制台默认是 GBK，中文和箭头容易乱码
sys.stdout.reconfigure(encoding="utf-8")

__all__ = ["DemoApp", "check", "main"]


def _ui_font(size: int, weight: str = "normal"):
    """复制一份系统默认字体并调大小——比自己写家族名可靠。"""
    font = tkfont.nametofont("TkDefaultFont").copy()
    font.configure(size=size, weight=weight)
    return font


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

        # command 和 tk.Button 一样：点击（含空格/回车）后调用一次
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
        # dconfigure 内部会重绘，配色字典换掉就完成了换肤
        self.button.dconfigure(theme=self.theme)

    def run(self):
        self.root.mainloop()


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
            expect(isinstance(button, DDrawWidget), "继承自 DDrawWidget 基类")
            start = time.monotonic() - 0.2  # 直接快进到 40% 进度
            button.ripple(80, 24, started=start)
            root.update()
            expect(button._ripple is not None, "点击后涟漪在播")
            expect(len(button.find_withtag("ripple")) == 1, "涟漪是一个独立图层")
            expect(len(button._photo_refs) < 256, "动画没有堆积图片引用")
            button.stop_ripple()
            root.update()
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
