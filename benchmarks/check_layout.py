"""画廊布局回归：把用户报过的几类"看得见的毛病"变成断言。

覆盖：

1. **菜单栏项宽度** —— ``len(label) * 8`` 对中文严重偏窄（"文件" 只算出 16px），
   必须按实际字体度量。
2. **底部按钮可见** —— FluFrame 的内部高度要减去边框与圆角，标签默认高度 32、
   按钮 32，塞不下就会被压成不可见。
3. **FluImage 真的有图** —— 父类 ``_draw`` 的 ``canvas.delete("all")`` 会把
   图片元素一起删掉，表现为"一个空盒子"。
4. **FluLabel 文字不被裁** —— 默认宽度 120 的固定画布 + 居中文本，
   长文本会左右都被裁掉。
5. **内嵌 Entry / Text 挂在正确的主控件下** —— 不传 master 会挂到默认根窗口，
   多 Toplevel / 多解释器场景下会嵌不进去，且控件销毁后不回收。

"可见性"必须在**窗口真实映射**的状态下测量：withdraw 状态下子控件尺寸是 1x1，
量不出问题。
"""

from __future__ import annotations

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

failures = []


def check(ok, message):
    print(f"  {'OK ' if ok else '!! '} {message}")
    if not ok:
        failures.append(message)


def main() -> int:
    import tkinter as tk

    import tkflu
    from tkflu.__main__ import build_gallery

    root = tkflu.FluWindow(mode="light")
    root.geometry("640x680+80+40")
    root.deiconify()
    root.lift()
    widgets = build_gallery(root, mode="light", log=lambda t: None)

    # 必须真正映射，否则拿到的尺寸都是 1x1
    for _ in range(60):
        root.update()
        time.sleep(0.01)

    if not root.winfo_ismapped():
        print("  跳过：窗口未能映射（无桌面会话），无法测量真实布局")
        root.destroy()
        return 0

    # ---- 1. 菜单栏 ---------------------------------------------------------
    print("=== 1. 菜单栏项宽度 ===")
    menubar = widgets["menubar"]
    for item in menubar.dcget("actions").values():
        label = item.dcget("text")
        got = item.winfo_reqwidth()
        naive = len(label) * 8
        cells = sum(2 if ord(ch) > 0x2E80 else 1 for ch in label)
        needed = cells * 6  # 每个"拉丁字宽"至少 6px 才不至于挤成一团
        check(got >= needed, f"{label!r} 宽度 {got}px ≥ {needed}px（旧的 len*8 会算成 {naive}px）")

    # ---- 2. 底部按钮可见 ---------------------------------------------------
    print("\n=== 2. 底部操作按钮可见 ===")
    for key, name in (
        ("theme_toggle", "切换主题"),
        ("state_toggle", "切换可用状态"),
        ("status_button", "刷新状态"),
    ):
        widget = widgets[key]
        visible = bool(widget.winfo_ismapped()) and widget.winfo_height() >= 20
        check(
            visible,
            f"{name} 实际 {widget.winfo_width()}x{widget.winfo_height()} 已映射={bool(widget.winfo_ismapped())}",
        )

    # ---- 3. FluImage 真的有图 ---------------------------------------------
    print("\n=== 3. FluImage 渲染出图片 ===")
    image_widget = widgets.get("image")
    if image_widget is None:
        check(False, "FluImage 未创建")
    else:
        kinds = [image_widget.canvas.type(i) for i in image_widget.canvas.find_all()]
        check(
            kinds.count("image") >= 2,
            f"画布元素类型 {kinds}（需要至少 2 个 image：背景 + 图片本身）",
        )

    # ---- 4. FluLabel 文字不被裁 -------------------------------------------
    print("\n=== 4. FluLabel 长文本不被裁 ===")
    long_text = "FluLabel（悬停看提示）"
    probe = tkflu.FluLabel(root, text=long_text, mode="light")
    probe.pack()
    for _ in range(10):
        root.update()
    bbox = probe.bbox(probe.element_text)
    text_width = (bbox[2] - bbox[0]) if bbox else 0
    canvas_width = probe.winfo_width()
    check(
        canvas_width >= text_width,
        f"文本 {text_width}px 能放进 {canvas_width}px 的画布（旧默认宽度 120px 会裁掉）",
    )
    probe.destroy()

    # 显式指定宽度时不应被改写
    fixed = tkflu.FluLabel(root, text=long_text, width=120, mode="light")
    fixed.pack()
    for _ in range(10):
        root.update()
    check(
        fixed.winfo_reqwidth() == 120,
        f"显式 width=120 保持不变（实际 {fixed.winfo_reqwidth()}）",
    )
    fixed.destroy()

    # ---- 5. 内嵌 Entry / Text 的归属 --------------------------------------
    print("\n=== 5. 内嵌 Entry / Text 挂在自身控件下 ===")
    stray = [
        child
        for child in root.winfo_children()
        if isinstance(child, (tk.Entry, tk.Text))
    ]
    check(
        not stray,
        f"root 下没有游离的 Entry/Text（发现 {len(stray)} 个：{[str(s) for s in stray]}）",
    )
    for key, attr in (("entry", "entry"), ("text", "text")):
        widget = widgets[key]
        inner = getattr(widget, attr)
        check(
            inner is not None and inner.master is widget,
            f"{key} 的内嵌控件 master 是它自己（实际 {inner.master if inner else None}）",
        )

    try:
        root.destroy()
    except Exception:
        pass

    print()
    if failures:
        print(f"布局回归失败 {len(failures)} 项：")
        for line in failures:
            print("  -", line)
        return 1
    print("布局回归通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
