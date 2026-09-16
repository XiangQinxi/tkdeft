"""从画廊截图里裁剪并放大指定区域，便于看清渲染细节。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

SRC = r"C:\Users\Xiang\PycharmProjects\tkdeft\benchmarks\_out\_probe_parent_2.png"
OUT = r"C:\Users\Xiang\PycharmProjects\tkdeft\benchmarks\_out"

img = Image.open(SRC)
print("源图尺寸:", img.size)

REGIONS = {
    "crop_label": (40, 110, 350, 160),      # 左栏第一个标签
    "crop_input": (40, 250, 350, 390),      # 输入区（FluEntry + FluText）
    "crop_menubar": (0, 30, 400, 75),       # 菜单栏
    "crop_bottom": (20, 550, 640, 660),     # 底部面板
}

for name, box in REGIONS.items():
    box = (max(0, box[0]), max(0, box[1]),
           min(img.width, box[2]), min(img.height, box[3]))
    crop = img.crop(box)
    scale = max(1, int(360 / max(1, crop.width)))
    big = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
    path = os.path.join(OUT, f"{name}.png")
    big.save(path)
    print(f"  {name}: 裁剪 {box} -> 放大 {scale}x -> {big.size}  {os.path.basename(path)}")
