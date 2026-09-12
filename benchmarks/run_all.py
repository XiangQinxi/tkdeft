"""一键回归：引擎自检 + 保真度比对 + 全组件冒烟 + 设计稿画廊。

用法::

    python benchmarks/run_all.py            # 全部检查
    python benchmarks/run_all.py --quick    # 跳过耗时较大的基准

任一项失败则以非 0 退出，可直接接进 CI。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("引擎自检（通道序 / alpha / 四边描边）", "check_engines.py", False),
    ("保真度比对（新引擎 vs tksvg 参照）", "check_fidelity.py", False),
    ("设计稿画廊（24 个按钮状态 × 各引擎）", "check_gallery.py", False),
    ("全组件冒烟（全部引擎）", "smoke_widgets.py", False),
    ("画布图片保活 + FluImage", "check_canvas_refs.py", False),
    ("命令行入口 python -m tkflu", "check_main.py", False),
    ("文档站构建（--strict，无警告）", "check_docs.py", False),
]

BENCH = ("性能基准（各引擎）", "bench_render.py", True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过性能基准")
    args = ap.parse_args()

    steps = list(STEPS)
    if not args.quick:
        steps.append(BENCH)

    failures = []
    for title, script, is_bench in steps:
        print("=" * 72)
        print(f"▶ {title}  ({script})")
        print("=" * 72)
        cmd = [sys.executable, os.path.join(HERE, script)]
        if is_bench:
            cmd += ["--repeat", "30", "--label", "run_all"]
        result = subprocess.run(cmd, cwd=HERE)
        if result.returncode != 0:
            failures.append(f"{title} ({script}) 退出码 {result.returncode}")
        print()

    print("=" * 72)
    if failures:
        print(f"回归失败：{len(failures)} 项")
        for item in failures:
            print("  -", item)
        return 1
    print(f"全部回归通过（{len(steps)} 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
