"""tkdeft / tkfluent 绘制性能基准。

用法（自动优先使用本地源码而非 site-packages）::

    python benchmarks/bench_render.py --label baseline
    python benchmarks/bench_render.py --renderer 2 --label skia

测量路径：

1. ``svg_gen``        —— 仅生成 SVG 字符串并落盘（引擎前半程）
2. ``svg_raster``     —— 仅把 SVG 文件栅格化成 PhotoImage（引擎后半程）
3. ``roundrect_vary`` —— 端到端圆角矩形，尺寸每帧不同（缓存必然 miss）
4. ``roundrect_same`` —— 端到端圆角矩形，参数完全一致（应命中缓存）
5. ``button_draw``    —— FluButton 完整一次 ``_draw``
6. ``button_hover``   —— 鼠标进入 + 离开（真实交互最高频路径）
7. ``batch_20``       —— 20 个按钮批量重绘
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")

# 是否强制使用 site-packages 里未修改的版本（用于测"优化前"的基线）。
# 注意：路径注入必须发生在 import tkflu / tkdeft 之前，所以放到 main() 里。
_USE_INSTALLED = False


def _setup_path():
    if _USE_INSTALLED:
        return
    for _p in (_TKFLUENT, _ROOT):
        if os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)


def _timeit(fn, repeat: int, warmup: int = 5):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return {
        "mean_ms": round(statistics.fmean(samples), 4),
        "median_ms": round(statistics.median(samples), 4),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 4),
        "min_ms": round(samples[0], 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=40)
    ap.add_argument("--json", default=None)
    ap.add_argument("--renderer", type=int, default=None,
                    help="0=tksvg 1=wand 2=skia 3=pillow 4=cairo")
    ap.add_argument("--label", default=None)
    ap.add_argument("--installed", action="store_true",
                    help="强制使用 site-packages 中未修改的版本（测优化前基线）")
    args = ap.parse_args()

    global _USE_INSTALLED
    _USE_INSTALLED = args.installed
    _setup_path()

    import tkflu
    from tkflu.button import FluButtonCanvas
    from tkflu.designs.renderer import get_renderer, set_renderer

    if args.renderer is not None:
        set_renderer(args.renderer)

    # 只允许一个 Tk 解释器：以 FluWindow 作为唯一 root
    root = tkflu.FluWindow()
    root.geometry("560x360")
    root.withdraw()

    results = {
        "label": args.label or f"renderer={get_renderer()}",
        "renderer": get_renderer(),
        "python": sys.version.split()[0],
        "tk": root.tk.call("info", "patchlevel"),
    }

    cnv = FluButtonCanvas(root, width=420, height=320)
    cnv.pack()
    root.update()

    KWRECT = dict(
        r1=6,
        fill="#ffffff",
        fill_opacity=1,
        outline="#000000",
        outline2=None,
        outline_opacity=0.2,
        outline2_opacity=1,
        width=1,
    )

    # ---- 1. 仅 SVG 生成 + 落盘 -------------------------------------------
    from tempfile import mkstemp

    _fd, _tmpsvg = mkstemp(suffix=".svg", prefix="bench.")
    os.close(_fd)
    _fd2, _tmppng = mkstemp(suffix=".png", prefix="bench.")
    os.close(_fd2)

    KWDRAW = dict(
        radius=6,
        fill="#ffffff",
        fill_opacity=1,
        outline="#000000",
        outline2=None,
        outline_opacity=0.2,
        outline2_opacity=1,
        width=1,
    )

    def _gen():
        cnv.svgdraw.create_roundrect(0, 0, 120, 32, temppath=_tmpsvg, **KWDRAW)

    try:
        results["svg_gen"] = _timeit(_gen, args.repeat)
    except Exception as exc:  # 引擎可能不走 SVG
        results["svg_gen"] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- 2. 仅栅格化 ------------------------------------------------------
    try:
        _svg_path = cnv.svgdraw.create_roundrect(
            0, 0, 120, 32, temppath=_tmpsvg, **KWDRAW)

        def _raster():
            cnv.svgdraw.create_svg_image(path=_svg_path, path2=_tmppng,
                                         way=get_renderer())

        results["svg_raster"] = _timeit(_raster, args.repeat)
    except Exception as exc:
        results["svg_raster"] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- 3. 端到端 · 尺寸每帧不同 -----------------------------------------
    counter = {"i": 0}

    def _vary():
        counter["i"] += 1
        s = 40 + (counter["i"] % 97)
        cnv.create_round_rectangle(0, 0, s, s, **KWRECT)

    results["roundrect_vary"] = _timeit(_vary, args.repeat)

    # ---- 4. 端到端 · 参数完全一致 -----------------------------------------
    def _same():
        cnv.create_round_rectangle(0, 0, 120, 32, **KWRECT)

    results["roundrect_same"] = _timeit(_same, args.repeat)

    # ---- 5. FluButton 完整 _draw -----------------------------------------
    btn = tkflu.FluButton(root, text="确定", width=120, height=32)
    btn.pack()
    root.update()
    results["button_draw"] = _timeit(btn._draw, args.repeat)

    # ---- 6. hover 往返 ----------------------------------------------------
    def _hover():
        btn._event_enter()
        btn._event_leave()

    results["button_hover"] = _timeit(_hover, args.repeat)

    # ---- 7. 20 个按钮批量 -------------------------------------------------
    btns = [tkflu.FluButton(root, text=f"按钮{i}", width=100, height=32)
            for i in range(20)]
    for b in btns:
        b.pack()
    root.update()

    def _batch():
        for b in btns:
            b._draw()

    results["batch_20"] = _timeit(_batch, args.repeat, warmup=2)

    out = json.dumps(results, ensure_ascii=False, indent=2)
    print(out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(out)

    try:
        root.destroy()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
