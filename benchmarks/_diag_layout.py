"""量出画廊里各区域的真实几何，定位布局问题。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkdeft")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkfluent")

import tkinter as tk

import tkflu
from tkflu.__main__ import build_gallery

GEOMETRY = sys.argv[1] if len(sys.argv) > 1 else "640x680"

root = tkflu.FluWindow(mode="light")
root.geometry(GEOMETRY)
root.withdraw()

widgets = build_gallery(root, mode="light", log=lambda t: None)
for _ in range(40):
    root.update()


def show(name, widget, indent=0):
    try:
        print(
            f"{' ' * indent}  {name:18s} 实际 {widget.winfo_width():4d}x{widget.winfo_height():<4d} "
            f"请求 {widget.winfo_reqwidth():4d}x{widget.winfo_reqheight():<4d}"
        )
    except Exception as exc:
        print(f"{' ' * indent}  {name:18s} 读取失败: {exc}")


print(f"=== 窗口 {GEOMETRY}（已 update 40 次）===")
show("FluWindow", root)

print("\n=== 菜单栏 ===")
menubar = widgets["menubar"]
show("FluMenuBar", menubar)
for item in menubar.dcget("actions").values():
    label = item.dcget("text")
    print(f"      项 {label!r:10s} 请求 {item.winfo_reqwidth():4d}x{item.winfo_reqheight():<4d} "
          f"（旧的 len*8 = {len(label)*8}）")

print("\n=== root 的直属子控件（自上而下）===")
for child in root.winfo_children():
    info = child.pack_info() if child.winfo_manager() == "pack" else {"side": "?"}
    show(f"{type(child).__name__}[side={info.get('side')}]", child)

print("\n=== 底部面板内部 ===")
bottom = None
for child in root.winfo_children():
    if isinstance(child, tkflu.FluFrame) and child is not widgets.get("frame"):
        bottom = child
if bottom is not None:
    show("bottom", bottom)
    show("canvas", bottom.canvas)
    for child in bottom.winfo_children():
        show(f"{type(child).__name__}", child, indent=2)
        for sub in child.winfo_children():
            txt = ""
            if hasattr(sub, "dcget"):
                txt = f" {sub.dcget('text')!r}"
            show(f"{type(sub).__name__}{txt}", sub, indent=4)
else:
    print("  未找到底部面板")

print("\n=== 图片组件 ===")
img = widgets.get("image")
if img is not None:
    show("FluImage", img)
    items = img.canvas.find_all()
    print(f"  画布元素 {items}（应为 3 个：背景图 + 内嵌 window + 图片）")
    types = [img.canvas.type(i) for i in items]
    print(f"  元素类型 {types}")
else:
    print("  FluImage 未创建")

root.destroy()
