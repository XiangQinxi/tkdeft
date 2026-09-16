# API 文档

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
