# tkdeft

[![Netlify Status](https://api.netlify.com/api/v1/badges/c7626ce2-9556-4e4f-b28e-36dc0b513398/deploy-status)](https://app.netlify.com/sites/tkdeft/deploys)

意为 `灵巧`，灵活轻巧好用。

一句话：**把矢量绘图变成 Tkinter 控件的底座。**

它本身**不含**任何具体组件（按钮、输入框都没有），只提供零件——
[tkfluent](https://pypi.org/project/tkfluent) 就是用这些零件搭出来的组件库：

<figure markdown>
  ![tkfluent 组件画廊（浅色）](assets/gallery-light.png)
  <figcaption>用 tkdeft 搭出来的组件库（tkfluent）——按钮、徽标、输入框、滑块、面板全部由这里的图元拼成</figcaption>
</figure>

## 它解决什么问题

Tkinter 想做出现代界面，通常得"先用矢量绘图生成图片，再交给 `Canvas` 显示"。
这段路有三个反复踩的坑：

| 坑 | tkdeft 的做法 |
| --- | --- |
| 每帧都要写 SVG 文件再读回来，慢 | 可插拔引擎：`skia` / `pillow` / `cairo` **进程内出图，完全不落盘**；配合规格缓存后按钮重绘快 **几十倍** |
| 图片被 GC 后画布元素变空白 | 画布按 item id 保管 `PhotoImage` 引用，统一入口内部自动保活 |
| 描边居中导致下/右边框被裁 | `tkdeft.svg` 统一几何：**内缩半个线宽**，SVG 与栅格引擎共用同一套规则 |

细节见 [概念与架构](getstarted/concepts.md)。

## 快速上手

```bash
pip install -U tkdeft
```

```python
import tkinter

from tkdeft.windows.canvas import DCanvas

root = tkinter.Tk()
canvas = DCanvas(root, width=240, height=120, background="#f3f3f3")
canvas.pack()

# 一行画图元：栅格引擎走进程内快速路径，否则自动回退 SVG
canvas.draw_roundrect(20, 20, 200, 76, 8,
                      fill="#ffffff", outline="#000000", outline_opacity=0.25)

root.mainloop()
```

想换引擎、拿单张图片、写自己的控件：[快速上手](getstarted/quickstart.md)。

## 绘制引擎

同一份**绘制规格**（`RoundRectSpec` / `TrackSpec` / `ThumbSpec`）交给不同引擎：

<figure markdown>
  ![各引擎渲染同一份规格](assets/engines-compare.png)
  <figcaption>5 个内置引擎渲染同一组规格的结果。<code>tksvg</code> 是默认引擎，也是保真度比对里的参照</figcaption>
</figure>

| 编号 | 引擎 | 类型 | 说明 | 额外依赖 |
| --- | --- | --- | --- | --- |
| 0 | `tksvg` | SVG | 默认，保持既有行为 | 无 |
| 1 | `wand` | SVG | 经 Wand(ImageMagick) 转 PNG | `Wand` |
| 2 | `skia` | 栅格 | skia-python，进程内出图，画质与速度最好 | `pip install tkdeft[skia]` |
| 3 | `pillow` | 栅格 | Pillow 超采样，**永远可用** | 无（Pillow 是硬依赖） |
| 4 | `cairo` | 栅格 | pycairo | `pip install tkdeft[cairo]` |

```python
from tkdeft.engines import set_engine, list_engines, describe_engines, cache_stats

print(list_engines())      # {'tksvg': True, 'wand': True, 'skia': True, ...}
set_engine("skia")         # 或 set_engine(2)
print(cache_stats())       # 命中率，便于诊断
```

<figure markdown>
  ![架构总览](assets/architecture.png)
  <figcaption>规格 → 引擎 → 画布。中间那条虚线是规格缓存：命中时中间的栅格化整段被跳过</figcaption>
</figure>

## 文档导航

| 从零开始 | |
| --- | --- |
| [安装](getstarted/install.md) | 环境要求、可选引擎、验证安装 |
| [快速上手](getstarted/quickstart.md) | 五分钟跑通第一个图元与控件 |
| [概念与架构](getstarted/concepts.md) | 规格 / 引擎 / 画布，一次重绘发生了什么 |

| 深入使用 | |
| --- | --- |
| [绘制引擎](usage/custom-drawing.md) | 切换、查询、缓存、颜色、自己写引擎 |
| [自定义组件](usage/custom-widget.md) | 用这些零件搭一个自己的控件 |
| [回归与性能](usage/benchmarks.md) | 9 项回归与性能基准怎么跑 |
| [常见问题与排查](usage/faq.md) | 13 条真实踩过的坑 |
| [从 0.2 升级到 0.3](usage/upgrade-0.3.md) | 纯加法升级，值得顺手改的四处 |

| 参考 | |
| --- | --- |
| [API 文档](api/index.md) | 由源码文档字符串自动生成 |
| [什么是模板](template/index.md) | 为什么这个库不直接做成主题库 |

## 项目状态

| | |
| --- | --- |
| 版本 | `0.3.0`（tkdeft 与 tkfluent 同步发版） |
| 回归 | `python benchmarks/run_all.py` **9 项**全绿（引擎自检 / 保真度 / 画廊 / 冒烟 / 保活 / 布局 / 命令行 / 文档站 / 性能） |
| 文档站 | `mkdocs build --strict` 零警告 |
| 静态检查 | `ruff check tkdeft` 零告警 |

```bash
# 一条命令验证一切（9 项）
python benchmarks/run_all.py --quick      # 8 项，跳过性能基准
python benchmarks/run_all.py              # 9 项
```

## 计划

未来我打算先制作出 `SunValley` 设计的库然后就去做别的项目，
[tkfluent](https://pypi.org/project/tkfluent)。

至于完整文档，我后面会加紧制作的。

## 设计来源

<https://pixso.cn/community/file/ItC5JH1TOwj15EeOPcY7LQ?from_share>

### 为什么不像 tkadw 一样做更易用的主题？

因为 `svg` 能实现很多漂亮的组件，而我套的模板可能不对其它设计起太大的作用。

所以我将这个设计库放在这里当做模板，供其它设计者参考使用。

## 更新日志

版本变更（新增了什么、修掉了什么、升级要注意什么）统一记录在
**[更新日志](blog/index.md)** 里，按时间倒序排列：

| 版本 | 一句话 |
| --- | --- |
| [`0.3.0`](blog/posts/2026-09-13.md) | 把对外接口补齐：统一绘制入口、引擎查询、`DObject` 接口补全 |
| [`0.2.0`](blog/posts/2026-09-12.md) | 可插拔绘制引擎层 + 进程内栅格引擎 + 规格缓存 |
| [`0.1.0`](blog/posts/2025-06-26.md) | 完善功能，定位收敛为"tkfluent 的底层零件库" |
| [更早](blog/posts/2024-01-26.md) | `0.0.1` – `0.0.9` 的起步阶段 |

完整列表见 [更新日志](blog/index.md)。
