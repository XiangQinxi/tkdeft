"""验证 ``python -m tkflu`` 的命令行入口。

覆盖：--list-engines、--help、--check（每个引擎各跑一遍）、非法引擎的退出码、
以及 --renderer auto 的挑选结果。
"""

from __future__ import annotations

import io
import os
import sys
import contextlib

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_TKFLUENT = os.path.join(os.path.dirname(_ROOT), "tkfluent")
for _p in (_TKFLUENT, _ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

failures = []


def record(ok, message):
    print(f"  {'OK ' if ok else '!! '} {message}")
    if not ok:
        failures.append(message)


def capture(argv):
    """调用 main()，返回 (退出码, 合并后的输出)。"""
    from tkflu.__main__ import main

    buffer = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        try:
            result = main(argv)
            code = 0 if result is None else result
        except SystemExit as exc:  # argparse 的 --help/错误
            code = exc.code if isinstance(exc.code, int) else 0
        except Exception as exc:
            code = -1
            buffer.write(f"\n{type(exc).__name__}: {exc}")
    return code, buffer.getvalue()


def main() -> int:
    import tkdeft.engines as eng

    print("=== 命令行入口 ===")

    code, out = capture(["--list-engines"])
    record(code == 0, f"--list-engines 退出码 {code}")
    record("tksvg" in out and "skia" in out, "--list-engines 列出了引擎名")

    code, out = capture(["--help"])
    record(code == 0, f"--help 退出码 {code}")
    record("--renderer" in out, "--help 包含 --renderer")

    code, out = capture(["--renderer", "不存在的引擎"])
    record(code == 2, f"非法引擎返回 2（实际 {code}）")
    record("错误" in out or "Error" in out, "非法引擎有错误提示")

    from tkflu.__main__ import resolve_renderer

    record(resolve_renderer(None) is None, "resolve_renderer(None) -> None（沿用库默认）")
    record(resolve_renderer("default") is None, "resolve_renderer('default') -> None")
    record(resolve_renderer("2") == "skia", "resolve_renderer('2') -> skia")
    record(resolve_renderer("SKIA") == "skia", "resolve_renderer 大小写不敏感")
    auto = resolve_renderer("auto")
    record(auto in ("skia", "cairo", "pillow", "tksvg", "wand"),
           f"resolve_renderer('auto') -> {auto}")

    print("\n=== --check 逐引擎 ===")
    for engine in ("tksvg", "wand", "skia", "pillow", "cairo"):
        if not eng.list_engines().get(engine):
            print(f"  --  {engine} 不可用，跳过")
            continue
        code, out = capture(["--check", "-r", engine])
        ok = code == 0 and "自检完成" in out
        record(ok, f"--check -r {engine} 退出码 {code}")
        if not ok:
            print("      输出尾部：" + out.strip().splitlines()[-1] if out.strip() else "")

    code, out = capture(["--check", "--mode", "dark", "--primary", "purple",
                         "--no-animation", "--geometry", "700x620"])
    record(code == 0, f"--check 带深色/主色/无动画组合 退出码 {code}")

    print()
    if failures:
        print(f"失败 {len(failures)} 项")
        return 1
    print("命令行入口验证通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
