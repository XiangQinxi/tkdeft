<div align="center">

# tkdeft

</div>

[![Netlify Status](https://api.netlify.com/api/v1/badges/c7626ce2-9556-4e4f-b28e-36dc0b513398/deploy-status)](https://app.netlify.com/sites/tkdeft/deploys)

意为`灵巧`，灵活轻巧好用

继`tkadw`之后的`tkinter`的现代化界面库

> 开发中

---
## 注意
> [!NOTE]
> 这里呢，已经成为[tkfluent](https://pypi.org/project/tkfluent)的基础库了，不含[tkfluent](https://pypi.org/project/tkfluent)的组件。
> 如果你想体验扩展界面库的效果，请去[tkfluent](https://pypi.org/project/tkfluent)查阅。


## 原理
先使用`svgwrite`进行矢量作图（默认会将其存储到临时文件夹中），再用`tksvg`打开图片，将图片利用`Canvas`或`Label`显示出来
[index.md](docs/docs/index.md)
> 这其中还是有些坑的，比如图片不显示等，导致我以前想做，却放弃了，现在知道错误所在了

## 绘制引擎
`tkdeft` 现在把"**画什么**"和"**用什么画**"分开了。组件只需要描述一个
`RoundRectSpec`（尺寸、圆角、填充、描边……），具体由哪个引擎栅格化是可切换的。

```python
from tkdeft.engines import set_engine, list_engines, cache_stats

print(list_engines())      # {'tksvg': True, 'wand': True, 'skia': True, 'pillow': True, 'cairo': True}
set_engine("skia")         # 或 set_engine(2)
print(cache_stats())       # 缓存命中率，便于诊断
```

| 引擎 | 类型 | 说明 | 额外依赖 |
| --- | --- | --- | --- |
| `tksvg` | SVG | 默认，保持既有行为 | 无 |
| `wand` | SVG | 经 Wand(ImageMagick) 转 PNG | `Wand` |
| `skia` | 栅格 | skia-python，进程内出图，画质与速度最好 | `pip install tkdeft[skia]` |
| `pillow` | 栅格 | Pillow 超采样，**永远可用** | 无（Pillow 是硬依赖） |
| `cairo` | 栅格 | pycairo | `pip install tkdeft[cairo]` |

栅格引擎不写临时文件、不解析 SVG、不碰磁盘；渲染结果按规格缓存，
**同尺寸同配色的一组控件共用同一张图片**。

### 实测（120×32 圆角矩形，本机）

| 场景 | 优化前 | 仅修基础设施 | + skia 引擎 |
| --- | --- | --- | --- |
| 圆角矩形（尺寸各异） | 13.81 ms | 4.94 ms | **1.26 ms** |
| 圆角矩形（参数相同） | 10.80 ms | 4.33 ms | **0.02 ms** |
| 按钮重绘 | 5.95 ms | 2.86 ms | **0.15 ms** |
| 按钮 hover 往返 | 13.65 ms | 6.08 ms | **0.26 ms** |
| 20 个按钮批量重绘 | 139.9 ms | 110.4 ms | **2.93 ms** |

复现：`python benchmarks/run_all.py`

## 已修复的缺陷
这一轮审查中定位并修掉的真实问题（都不是"风格问题"）：

| 问题 | 影响 |
| --- | --- |
| `DSvgDraw.temppath()` 每次调用都 `mkstemp()` 且**从不关闭返回的 fd** | 每绘制一帧泄漏一个句柄，并在临时目录留下一个残留文件 |
| `DDrawWidget.__init__` 一次性 `mkstemp()` 四个临时文件 | 每个控件创建即泄漏 4 个句柄（20 个按钮 = 80 个） |
| `DCanvas.create_round_rectangle` 只把图片存进 `self._img` / `self._tkimg` | 同一画布上多张图片时，除最后一张外都会被 GC，**画布 item 变空白** |
| `RenderManager._render_all` 调用 `widget.winfo_zorder()` | `tkinter` **没有**这个方法，只要有脏控件就抛 `AttributeError` |
| `RenderManager._schedule_render` 里 `tk._default_root or list(...)[0]` | 两者都不可用时 `IndexError` |
| `_draw` 结尾又 `mark_dirty(self)` | 集中式调度下同一控件被重绘两遍 |
| svgwrite 生成的矩形用 `translate(0.5,0.5)` + 整宽整高 | 描边中心线压在画布边界上，**下边框和右边框被完全裁掉** |
| `create_svg_image` 对 `way` 未做兜底 | 回退路径遇到非 0/1 的渲染器编号会直接失败 |

## 计划
未来我打算先制作出`SunValley`设计的库然后就去做别的项目，[tkfluent](https://pypi.org/project/tkfluent)

至于完整文档，我后面会加紧制作的。


设计来源： https://pixso.cn/community/file/ItC5JH1TOwj15EeOPcY7LQ?from_share

### 为什么不像tkadw一样做跟易用的主题？
因为`svg`能实现很多漂亮的组件，而我套的模板可能不对其它设计其太大的作用

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
* 详细缺陷清单与性能数据见 [benchmarks/](benchmarks/)