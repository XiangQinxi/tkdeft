"""重新生成 tkdeft 的 mkdocstrings API 页面。

与 tkfluent 的 ``docs/gen_api_pages.py`` 是同一套做法。

用法（在 ``docs/`` 目录下）::

    python gen_api_pages.py            # 预览
    python gen_api_pages.py --write    # 实际写入
"""

from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

DOCS = pathlib.Path(__file__).resolve().parent / "docs"

#: (文档里用的模块名, 显示标题)
PAGES = [
    ("tkdeft", "tkdeft · 顶层接口"),
    ("tkdeft.engines", "engines · 绘制引擎层入口"),
    ("tkdeft.engines.base", "engines.base · 引擎基类与规格"),
    ("tkdeft.engines.cache", "engines.cache · 图片缓存"),
    ("tkdeft.engines.colors", "engines.colors · 颜色解析"),
    ("tkdeft.engines.skia", "engines.skia · Skia 引擎"),
    ("tkdeft.engines.pillow", "engines.pillow · Pillow 引擎"),
    ("tkdeft.engines.cairo", "engines.cairo · Cairo 引擎"),
    ("tkdeft.svg", "svg · SVG 形状助手"),
    ("tkdeft.windows", "windows · 画布与绘制后端"),
    ("tkdeft.windows.canvas", "windows.canvas · 带绘制的画布"),
    ("tkdeft.windows.draw", "windows.draw · 绘制后端"),
    ("tkdeft.windows.drawwidget", "windows.drawwidget · 交互控件基类"),
    ("tkdeft.object", "object · DObject 配置容器"),
    ("tkdeft.utility", "utility · 字体等工具"),
]

#: 文档名 -> 实际模块名（引擎子模块的文件名带 _engine 后缀）
MODULE_MAP = {
    "tkdeft.engines.skia": "tkdeft.engines.skia_engine",
    "tkdeft.engines.pillow": "tkdeft.engines.pillow_engine",
    "tkdeft.engines.cairo": "tkdeft.engines.cairo_engine",
}

#: 页面专属的 mkdocstrings 选项（键是 ``PAGES`` 里的模块名）。
#: 顶层 ``tkdeft`` 只是"再导出一份"的汇总页，成员在各自的子模块页里已经
#: 完整展开，这里只保留模块文档本身，避免同一份内容出现两遍。
PAGE_OPTIONS = {
    "tkdeft": "    options:\n      members: false\n      show_source: false\n",
    "tkdeft.windows": "    options:\n      members: false\n      show_source: false\n",
}

INDEX = """# API 文档

本项目的 API 文档由 [`mkdocstrings`](https://mkdocstrings.github.io/) 从源码
**自动生成**——页面上看到的就是代码里的文档字符串。

## 怎么读

* 标题形如 `tkdeft.engines · 绘制引擎层入口`，正文按 **模块 → 类 → 方法** 展开；
* 每个条目的参数、返回值、异常都写在文档字符串里，与代码一起维护；
* 右上角的搜索框支持跨页搜索；
* 想直接看实现，点开 `源码` 折叠块。

## 分组

| 分组 | 内容 |
| --- | --- |
| 顶层 | `tkdeft` 的汇总入口（各子模块的常用名字） |
| 绘制引擎 | 引擎注册表、规格对象、缓存、颜色解析，以及三个栅格引擎 |
| 图形与画布 | SVG 形状助手、画布、绘制后端、交互控件基类 |
| 基础 | `DObject` 配置容器、字体等工具 |

## 从哪读起

| 你在做什么 | 先看 |
| --- | --- |
| 画图元 / 写组件 | [`tkdeft.windows.canvas`](tkdeft.windows.canvas.md) 的 `draw_roundrect` 一族 |
| 换引擎 / 调缓存 | [`tkdeft.engines`](tkdeft.engines.md) |
| 自己写一个引擎 | [`tkdeft.engines.base`](tkdeft.engines.base.md) 的 `DrawEngine` |
| 拼 SVG | [`tkdeft.svg`](tkdeft.svg.md) |
| 组件的属性容器 | [`tkdeft.object`](tkdeft.object.md) 的 `DObject` |

## 相关阅读

* [安装](../getstarted/install.md) / [快速上手](../getstarted/quickstart.md) / [概念与架构](../getstarted/concepts.md)
* [绘制引擎](../usage/custom-drawing.md) —— 概念、切换方式、缓存策略、自己写引擎
* [自定义组件](../usage/custom-widget.md) —— 用这些零件搭一个自己的控件
* [常见问题与排查](../usage/faq.md) —— 13 条真实踩过的坑
"""


def main() -> int:
    write = "--write" in sys.argv
    api_dir = DOCS / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for public_name, title in PAGES:
        target = MODULE_MAP.get(public_name, public_name)
        filename = f"{target}.md"
        content = f"# {title}\n\n::: {target}\n" + PAGE_OPTIONS.get(public_name, "")
        action = "更新" if (api_dir / filename).exists() else "新建"
        print(f"  {action} api/{filename:38s} {title}")
        if write:
            (api_dir / filename).write_text(content, encoding="utf-8")
        written += 1

    print(f"\n{'已写入' if write else '待写入'} {written} 个页面")
    if write:
        (api_dir / "index.md").write_text(INDEX, encoding="utf-8")
        print("已写入 api/index.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
