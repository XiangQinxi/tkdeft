"""构建两个项目的文档站，让 nav / 链接问题在 CI 里就暴露出来。

`mkdocs build --strict` 会把任何 WARNING 当成错误——包括：

* nav 里引用了不存在的文件
* 正文里的相对链接指向不存在的页面
* mkdocstrings 无法导入某个模块或解析某段 docstring

用法::

    python benchmarks/check_docs.py           # 构建两个站点
    python benchmarks/check_docs.py tkdeft    # 只构建一个

依赖 mkdocs 等文档工具链（见各项目的 docs/requirements.txt）。
未安装时会跳过并给出提示，而不是判定失败。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECTS_ROOT = os.path.dirname(os.path.dirname(_HERE))  # PycharmProjects

SITES = {
    "tkdeft": os.path.join(_PROJECTS_ROOT, "tkdeft", "docs"),
    "tkfluent": os.path.join(_PROJECTS_ROOT, "tkfluent", "docs"),
}

#: 构建时把仓库根加入 PYTHONPATH，让 mkdocstrings 能导入本地源码
SOURCE_PATHS = {
    "tkdeft": [os.path.join(_PROJECTS_ROOT, "tkdeft")],
    "tkfluent": [
        os.path.join(_PROJECTS_ROOT, "tkfluent"),
        os.path.join(_PROJECTS_ROOT, "tkdeft"),
    ],
}


def _has_mkdocs() -> bool:
    try:
        import mkdocs  # noqa: F401
    except ImportError:
        return False
    return True


def _missing_plugins() -> list:
    missing = []
    for module in ("mkdocstrings", "mkdocstrings_handlers", "mkdocs_rss_plugin"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return missing


def build(name: str) -> int:
    docs_dir = SITES[name]
    if not os.path.isdir(docs_dir):
        print(f"  跳过：找不到 {docs_dir}")
        return 1

    env = dict(os.environ)
    paths = SOURCE_PATHS.get(name, [])
    env["PYTHONPATH"] = os.pathsep.join(paths + [env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )

    site_dir = tempfile.mkdtemp(prefix=f"docs-{name}-")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict",
             "--site-dir", site_dir],
            cwd=docs_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        shutil.rmtree(site_dir, ignore_errors=True)

    if result.returncode == 0:
        print(f"  [{name}] 构建通过（--strict，无警告）")
        return 0

    print(f"  [{name}] 构建失败（退出码 {result.returncode}）")
    for line in (result.stdout or "").splitlines() + (result.stderr or "").splitlines():
        if "WARNING" in line or "ERROR" in line:
            print("     " + line.strip())
    return 1


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    names = only or list(SITES)

    print("=== 文档站构建检查 ===")
    if not _has_mkdocs():
        print("  跳过：未安装 mkdocs。")
        print("  安装：pip install -r docs/requirements.txt")
        return 0
    missing = _missing_plugins()
    if missing:
        print(f"  跳过：缺少插件 {missing}")
        print("  安装：pip install -r docs/requirements.txt")
        return 0

    failed = 0
    for name in names:
        if name not in SITES:
            print(f"  未知项目 {name!r}；可用：{list(SITES)}")
            failed += 1
            continue
        failed += build(name)

    print()
    if failed:
        print(f"{failed} 个文档站构建失败")
        return 1
    print("文档站构建检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
