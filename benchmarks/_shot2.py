"""用 Win32 PrintWindow 直接按窗口句柄截图（不受遮挡与 DPI 坐标影响）。"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkdeft")
sys.path.insert(0, r"C:\Users\Xiang\PycharmProjects\tkfluent")

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


class BITMAPINFOHEADER(ctypes.Structure):
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


def capture(hwnd, width, height, flag=2):
    """flag=2 是 PW_RENDERFULLCONTENT，能抓到 DWM 合成后的内容。"""
    from PIL import Image

    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(memdc, bmp)

    ok = user32.PrintWindow(hwnd, memdc, flag)

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = -height  # 负数 = 自上而下
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memdc, bmp, 0, height, buffer, ctypes.byref(header), 0)
    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return image.convert("RGB"), bool(ok)


def main() -> int:
    import tkflu
    from tkflu.__main__ import build_gallery

    mode = sys.argv[1] if len(sys.argv) > 1 else "light"
    engine = sys.argv[2] if len(sys.argv) > 2 else "skia"
    out_dir = r"C:\Users\Xiang\PycharmProjects\tkdeft\benchmarks\_out"
    os.makedirs(out_dir, exist_ok=True)

    tkflu.set_renderer(engine)
    root = tkflu.FluWindow(mode=mode)
    root.geometry("640x680+70+40")
    root.title(f"tkfluent · {mode} · {engine}")
    root.deiconify()
    root.lift()
    build_gallery(root, mode=mode, log=lambda t: None)

    for _ in range(80):
        root.update()
        time.sleep(0.012)

    w, h = root.winfo_width(), root.winfo_height()
    child = int(root.winfo_id())
    parent = user32.GetParent(child)
    print(f"Tk 窗口 {w}x{h}  child hwnd={child}  parent hwnd={parent}")

    for label, hwnd in (("parent", parent), ("child", child)):
        for flag in (2, 0):
            img, ok = capture(hwnd, w, h, flag)
            colors = img.getcolors(maxcolors=1 << 22)
            score = len(colors) if colors else 0
            path = os.path.join(out_dir, f"_probe_{label}_{flag}.png")
            img.save(path)
            print(f"  {label} flag={flag} PrintWindow={ok} 色彩数={score} -> {os.path.basename(path)}")

    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
