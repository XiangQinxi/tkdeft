# 安装与使用

## 安装

```bash
pip install -U tkdeft
```

`tkdeft` 底层依赖这些库，通常会自动装好：

* `tksvg` —— 让 Tkinter 能显示 SVG（同时也负责矢量绘制）；
* `tkextrafont` —— 加载内嵌字体，保证跨平台外观一致；
* `svgwrite` —— 生成矢量图；
* `pillow` —— 位图处理与 `PhotoImage` 转换；
* `easydict` —— 组件属性容器。

如果安装过程中遇到问题，请先参阅这些项目各自的说明。

## 可选：更快的绘制引擎

默认引擎 `tksvg` 的工作方式是"生成 SVG → 写临时文件 → 再读回来栅格化"，
每次重绘都要碰磁盘。想更快可以装一个**进程内栅格引擎**：

```bash
pip install "tkdeft[skia]"     # skia-python，速度与画质最好
pip install "tkdeft[cairo]"    # pycairo
pip install "tkdeft[raster]"   # 上面两个都装
```

不装也能用——`Pillow` 引擎（编号 3）零额外依赖，一直在。

```python
from tkdeft.engines import set_engine, list_engines

print(list_engines())
set_engine("skia")       # 或 set_engine(2)
```

详见 [绘制引擎](custom-drawing.md)。

## tkdeft 是什么

一句话：**把矢量绘图变成 Tkinter 组件的底座。**

它不含任何具体组件（按钮、输入框都没有），只提供零件：

| 模块 | 内容 |
| --- | --- |
| `tkdeft.engines` | 可插拔的绘制引擎（tksvg / wand / skia / pillow / cairo）与图片缓存 |
| `tkdeft.svg` | 修正过的 SVG 形状助手 |
| `tkdeft.windows` | `DCanvas` / `DDraw` / `DDrawWidget` |
| `tkdeft.object` | `DObject` 配置容器 |

想直接体验"用这套零件搭出来的界面库"，请去看
[tkfluent](https://pypi.org/project/tkfluent)。

## 目录

* [绘制引擎](custom-drawing.md) —— 引擎列表、切换方式、缓存机制、自己写引擎
* [自定义组件](custom-widget.md) —— 用 `DObject` + `DDrawWidget` 做一个控件
* [什么是模板](../template/index.md) —— 为什么这个库不直接做成主题库
