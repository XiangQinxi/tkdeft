"""把 tkfluent 的组件画廊真实显示出来并截图。

**为什么不用 PIL.ImageGrab**：它按屏幕坐标抓取，在 DPI 缩放或多虚拟桌面的
环境里经常抓到别的窗口（表现为"截出来是浏览器 / 视频播放器"）。
这里改用 Win32 的 ``PrintWindow`` —— 直接按窗口句柄取内容，
既不受遮挡影响，也不受 DPI 坐标映射影响。

用法::

    python benchmarks/visual_demo.py                    # 浅色 + skia
    python benchmarks/visual_demo.py dark skia
    python benchmarks/visual_demo.py light pillow 720x760
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

OUT = os.path.join(_HERE, "_out")

# ---------------------------------------------------------------------------
# Win32 截图
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

user32.GetWindowDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.PrintWindow.restype = wintypes.BOOL
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capture_window(hwnd, width, height, flag=2):
    """按窗口句柄抓图。

    ``flag=2`` 是 ``PW_RENDERFULLCONTENT``：抓 DWM 合成后的内容，
    支持它的系统上效果最好；不支持时退回 ``flag=0``。
    """
    from PIL import Image

    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(memdc, bitmap)

    ok = user32.PrintWindow(hwnd, memdc, flag)

    header = _BitmapInfoHeader()
    header.biSize = ctypes.sizeof(_BitmapInfoHeader)
    header.biWidth = width
    header.biHeight = -height  # 负数 = 自上而下
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0  # BI_RGB

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memdc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return image.convert("RGB"), bool(ok)


def grab(root, path):
    """把已映射的窗口截到 ``path``，返回一行说明。"""
    width, height = root.winfo_width(), root.winfo_height()
    child = int(root.winfo_id())
    parent = user32.GetParent(child)

    # 父句柄（真正的顶层窗口）抓得更完整；flag=2 与 flag=0 各试一次取内容最丰富的
    best = None
    for hwnd, flag in ((parent, 2), (parent, 0), (child, 2)):
        for _ in range(3):
            root.update()
            image, ok = capture_window(hwnd, width, height, flag)
            colors = image.getcolors(maxcolors=1 << 22)
            score = len(colors) if colors else 0
            if best is None or score > best[0]:
                best = (score, image, ok, flag)
            time.sleep(0.05)

    score, image, ok, flag = best
    image.save(path)
    return f"{image.width}x{image.height} 色彩数={score} PrintWindow={ok} flag={flag}"


def main() -> int:
    import tkflu
    from tkflu.__main__ import build_gallery

    mode = sys.argv[1] if len(sys.argv) > 1 else "light"
    engine = sys.argv[2] if len(sys.argv) > 2 else "skia"
    geometry = sys.argv[3] if len(sys.argv) > 3 else "640x680"
    os.makedirs(OUT, exist_ok=True)

    tkflu.set_renderer(engine)
    root = tkflu.FluWindow(mode=mode)
    root.geometry(f"{geometry}+70+40")
    root.title(f"tkfluent · {mode} · {engine}")
    root.deiconify()
    root.lift()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    build_gallery(root, mode=mode, log=lambda text: None)

    # 等 Tk 走完布局与首帧绘制，否则会抓到还没画完的内容
    for _ in range(80):
        root.update()
        time.sleep(0.012)

    if not root.winfo_ismapped():
        print("窗口未能映射（当前会话没有可用桌面），无法截图")
        root.destroy()
        return 1

    path = os.path.join(OUT, f"gallery_ui_{mode}_{engine}.png")
    print(f"[{mode}/{engine}] {grab(root, path)} -> {path}")

    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
