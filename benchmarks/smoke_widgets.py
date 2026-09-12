"""冒烟回归：在每个引擎下实例化 tkfluent 的全部组件并强制重绘。

这是接入绘制引擎层之后最重要的回归测试——引擎快速路径一旦有签名不匹配，
组件会在构造或首次重绘时抛异常，这里能立刻抓到。

用法::

    python benchmarks/smoke_widgets.py            # 全部引擎
    python benchmarks/smoke_widgets.py --engine skia
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def build_all(root):
    """构造每一种组件，返回 [(名字, 控件)]。"""
    import tkflu
    from tkflu.listbox import FluListBox

    made = []

    def add(name, factory):
        try:
            made.append((name, factory()))
        except Exception:
            made.append((name, _Failed(traceback.format_exc())))

    add("FluWindow", lambda: root)
    add("FluFrame", lambda: tkflu.FluFrame(root, width=200, height=100))
    add("FluButton.standard", lambda: tkflu.FluButton(root, text="标准"))
    add("FluButton.accent", lambda: tkflu.FluButton(root, text="强调", style="accent"))
    add("FluButton.menu", lambda: tkflu.FluButton(root, text="菜单", style="menu"))
    add("FluButton.dark", lambda: tkflu.FluButton(root, text="暗色", mode="dark"))
    add("FluBadge", lambda: tkflu.FluBadge(root, text="徽标"))
    add("FluEntry", lambda: tkflu.FluEntry(root, width=160))
    add("FluText", lambda: tkflu.FluText(root, width=160, height=80))
    add("FluLabel", lambda: tkflu.FluLabel(root, text="标签"))
    add("FluToggleButton", lambda: tkflu.FluToggleButton(root, text="开关"))
    add("FluSlider", lambda: tkflu.FluSlider(root))
    add("FluScrollBar", lambda: tkflu.FluScrollBar(root))
    add("FluListBox", lambda: FluListBox(root, width=160, height=80))
    add("FluToolTip", lambda: tkflu.FluToolTip(root, text="提示"))
    add("FluMenuBar", lambda: tkflu.FluMenuBar(root))
    return made


class _Failed:
    def __init__(self, tb):
        self.tb = tb


def exercise(name, widget, root):
    """强制走一遍绘制/主题流程。"""
    widget.pack() if hasattr(widget, "pack") and widget is not root else None
    root.update_idletasks()

    for step, fn in (
        ("_draw", lambda: widget._draw()),
        ("theme(light)", lambda: widget.theme(mode="light")),
        ("theme(dark)", lambda: widget.theme(mode="dark")),
        ("hover-enter", lambda: widget._event_enter()),
        ("hover-leave", lambda: widget._event_leave()),
        ("press", lambda: widget._event_on_button1()),
        ("release", lambda: widget._event_off_button1()),
        ("configure", lambda: widget._event_configure()),
    ):
        try:
            fn()
        except AttributeError:
            continue  # 该组件没有这个钩子，正常
        except Exception:
            return f"{step}: {traceback.format_exc(limit=3)}"
    try:
        root.update()
    except Exception:
        return f"root.update(): {traceback.format_exc(limit=3)}"
    return None


def run_engine(engine_name, verbose=False):
    import tkinter as tk

    import tkflu
    from tkflu.designs.renderer import get_renderer_name, set_renderer

    set_renderer(engine_name)
    root = tkflu.FluWindow()
    root.geometry("640x480")
    root.withdraw()

    failures = []
    for name, widget in build_all(root):
        if isinstance(widget, _Failed):
            failures.append((name, "构造失败", widget.tb))
            continue
        err = exercise(name, widget, root)
        if err:
            failures.append((name, "重绘失败", err))
        elif verbose:
            print(f"    [OK] {name}")

    # 缓存统计
    from tkdeft.engines import cache_stats

    stats = cache_stats()
    try:
        root.destroy()
    except Exception:
        pass
    return get_renderer_name(), failures, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    import tkdeft.engines as eng

    engines = [args.engine] if args.engine else [
        name for name, ok in eng.list_engines().items() if ok
    ]

    total_failures = 0
    for name in engines:
        try:
            used, failures, stats = run_engine(name, args.verbose)
        except Exception:
            print(f"[{name}] 引擎初始化即失败：")
            traceback.print_exc()
            total_failures += 1
            continue
        status = "全部通过" if not failures else f"{len(failures)} 项失败"
        print(f"[{used:7s}] {status}   缓存命中率={stats['hit_rate'] * 100:.1f}% "
              f"条目={stats['entries']} 像素={stats['pixels']}")
        for wname, stage, tb in failures:
            total_failures += 1
            print(f"    !! {wname} @ {stage}")
            print("      " + tb.strip().replace("\n", "\n      "))

    print()
    if total_failures:
        print(f"共 {total_failures} 项失败")
        return 1
    print("全部引擎下的组件冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
