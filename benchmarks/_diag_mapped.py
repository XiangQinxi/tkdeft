"""让窗口真实映射后再量几何（withdraw 状态下量到的是 1x1，没意义）。"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkdeft")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkfluent")

import tkinter as tk

import tkflu
from tkflu.__main__ import build_gallery

GEOMETRY = sys.argv[1] if len(sys.argv) > 1 else "640x680"

root = tkflu.FluWindow(mode="light")
root.geometry(GEOMETRY + "+60+40")
root.deiconify()
root.lift()
try:
    root.attributes("-topmost", True)
except Exception:
    pass

widgets = build_gallery(root, mode="light", log=lambda t: None)
for _ in range(60):
    root.update()
    time.sleep(0.01)

print(f"窗口状态: state={root.state()} viewable={root.winfo_viewable()} "
      f"mapped={bool(root.winfo_ismapped())}")
print(f"窗口实际 {root.winfo_width()}x{root.winfo_height()}")


def show(name, widget, indent=0):
    print(
        f"{' ' * indent}  {name:20s} 实际 {widget.winfo_width():4d}x{widget.winfo_height():<4d} "
        f"请求 {widget.winfo_reqwidth():4d}x{widget.winfo_reqheight():<4d} "
        f"映射={bool(widget.winfo_ismapped())}"
    )


print("\n=== 三个主区域（自上而下应有：菜单栏 / 主区 / 底部面板）===")
for child in root.winfo_children():
    if child.winfo_manager() != "pack":
        continue
    info = child.pack_info()
    show(f"{type(child).__name__}", child)

print("\n=== 底部面板（通过 log_label 反查）===")
log_label = widgets["log_label"]
frame = log_label.master           # FluFrame 的内嵌 Frame 的 master 就是 FluFrame
show("bottom FluFrame", frame)
show("bottom canvas", frame.canvas)
for child in frame.winfo_children():
    show(type(child).__name__, child, indent=2)
    for sub in child.winfo_children():
        txt = sub.dcget("text") if hasattr(sub, "dcget") else ""
        show(f"{type(sub).__name__} {txt!r}", sub, indent=4)

print("\n=== 三个按钮是否真的可见 ===")
for key in ("theme_toggle", "state_toggle", "status_button"):
    w = widgets[key]
    ok = w.winfo_ismapped() and w.winfo_height() > 10
    print(f"  {key:16s} {w.winfo_width()}x{w.winfo_height()} "
          f"映射={bool(w.winfo_ismapped())} -> {'可见' if ok else '!! 不可见'}")

print("\n=== 两栏 ===")
show("left", widgets["label"].master)
show("right", widgets["button"].master)

root.destroy()
