"""把画廊真实显示出来并截图（窗口已能映射）。"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkdeft")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkfluent")

import tkflu
from tkflu.__main__ import build_gallery

OUT = r"C:\Users\Xiang\PycharmProjects\tkdeft\benchmarks\_out"
os.makedirs(OUT, exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "light"
engine = sys.argv[2] if len(sys.argv) > 2 else "skia"

tkflu.set_renderer(engine)
root = tkflu.FluWindow(mode=mode)
root.geometry("640x680+70+40")
root.title(f"tkfluent · {mode} · {engine}")
root.deiconify()
root.lift()
try:
    root.attributes("-topmost", True)
except Exception:
    pass

build_gallery(root, mode=mode, log=lambda t: None)
for _ in range(80):
    root.update()
    time.sleep(0.012)

x, y = root.winfo_rootx(), root.winfo_rooty()
w, h = root.winfo_width(), root.winfo_height()
print(f"窗口位置 ({x},{y}) 尺寸 {w}x{h} mapped={bool(root.winfo_ismapped())}")

from PIL import ImageGrab

best = None
for _ in range(8):
    root.update()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    colors = img.convert("RGB").getcolors(maxcolors=1 << 22)
    score = len(colors) if colors else 0
    if best is None or score > best[0]:
        best = (score, img)
    time.sleep(0.08)

path = os.path.join(OUT, f"gallery_ui_{mode}_{engine}.png")
best[1].save(path)
print(f"已保存 {path}  色彩数={best[0]}")

root.destroy()
