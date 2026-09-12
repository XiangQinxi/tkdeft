# tkdeft

[![Netlify Status](https://api.netlify.com/api/v1/badges/c7626ce2-9556-4e4f-b28e-36dc0b513398/deploy-status)](https://app.netlify.com/sites/tkdeft/deploys)

意为 `灵巧`，灵活轻巧好用。

继 `tkadw` 之后的 `tkinter` 现代化界面库。

> 开发中

---

## 注意

这里已经成为 [tkfluent](https://pypi.org/project/tkfluent) 的**基础库**，
本身**不含** [tkfluent](https://pypi.org/project/tkfluent) 的组件。

如果你想体验扩展界面库的效果，请去
[tkfluent](https://pypi.org/project/tkfluent) 查阅。

## 原理

一句话：**先用矢量绘图生成图片，再交给 `Canvas` / `Label` 显示出来。**

具体走哪条路是可切换的：

| 方式 | 过程 |
| --- | --- |
| SVG 引擎（默认 `tksvg`） | `svgwrite` 生成 SVG → 写临时文件 → `tksvg` 读回来栅格化 |
| 栅格引擎（`skia` / `pillow` / `cairo`） | 进程内直接画到位图，**完全不碰磁盘** |

栅格引擎配合图片缓存后，相同规格的绘制结果会被复用——在
[tkfluent](https://pypi.org/project/tkfluent) 里实测按钮重绘快了约 **39 倍**。

细节见 [绘制引擎](usage/custom-drawing.md)。

> 这其中还是有些坑的，比如图片不显示——那其实是 `PhotoImage` 被垃圾回收
> 导致的，见 [自定义组件](usage/custom-widget.md)。

## 快速上手

```bash
pip install -U tkdeft
```

```python
from tkdeft.engines import RoundRectSpec, render_roundrect, set_engine

set_engine("skia")                       # 换成进程内栅格引擎（可选）

spec = RoundRectSpec(width=120, height=32, rx=6,
                     fill="#ffffff", outline="#000000",
                     outline_opacity=0.2, outline_width=1)

photo = render_roundrect(spec, master=my_canvas)   # -> PhotoImage
```

想搭自己的组件，请看 [自定义组件](usage/custom-widget.md)。

## 目录

* [安装与使用](usage/index.md)
* [绘制引擎](usage/custom-drawing.md)
* [自定义组件](usage/custom-widget.md)
* [API 文档](api/index.md)
* [什么是模板](template/index.md)

## 计划

未来我打算先制作出 `SunValley` 设计的库然后就去做别的项目，
[tkfluent](https://pypi.org/project/tkfluent)。

至于完整文档，我后面会加紧制作的。

## 设计来源

<https://pixso.cn/community/file/ItC5JH1TOwj15EeOPcY7LQ?from_share>

### 为什么不像 tkadw 一样做跟易用的主题？

因为 `svg` 能实现很多漂亮的组件，而我套的模板可能不对其它设计起太大的作用。

所以我将这个设计库放在这里当做模板，供其它设计者参考使用。

## 更新日志

### 2024-01-22
发布`0.0.1`版本，模板组件包括`DButton`

### 2023-01-23
发布`0.0.2`版本，补充模板组件`DEntry`、`DFrame`、`DText`, `DBadge`

### 2023-01-25
发布`0.0.3` `0.0.4`版本，粗心了，两次补充依赖
发布`0.0.5`版本，模板组件主题由`theme(mode=..., style=...)`设置，不再使用如`DDarkButton`这样的，添加`DWindow.wincustom`自定义窗口（仅限Windows）
发布`0.0.6`版本，模板组件`DBadge`补充样式`style=accent`，并对自定义窗口进行稍微调整

### 2023-01-26
发布`0.0.7`版本，模板库`Fluent`已移至`tkfluent`库

### 2024-09-16
发布`0.0.9`版本，一些小修改

### 2025-06-26
发布`0.1.0`版本，完善功能

### 2026-09-12
发布`0.2.0`版本：

* 新增 `tkdeft.engines` 绘制引擎层，可插拔切换 `tksvg` / `wand` / `skia` / `pillow` / `cairo`
* 新增进程内栅格引擎（skia-python / Pillow / pycairo），完全不落盘
* 新增按规格缓存的图片缓存，参数相同的绘制结果直接复用
* 新增 SVG 形状助手 `tkdeft.svg`，统一并修正圆角矩形几何
* 修复临时文件 / fd 泄漏、`PhotoImage` 被 GC 导致画面空白、
  `RenderManager` 的 `winfo_zorder` 崩溃等问题
* 文档补齐：[绘制引擎](usage/custom-drawing.md)、[自定义组件](usage/custom-widget.md)、
  [API 文档](api/index.md)
