# 自定义组件

`tkdeft` 本身**不带任何具体组件**——它提供的是"把矢量图形变成 Tkinter 控件"
所需的那套零件。想做一个自己的组件，通常只要组合这四样东西：

| 零件 | 作用 |
| --- | --- |
| `DObject` | 统一的属性配置接口（`dconfigure` / `dcget`） |
| `DCanvas` | 带绘制能力的画布 |
| `DDraw` | 把 SVG / 位图变成 `PhotoImage` |
| `DDrawWidget` | 事件 → 状态 → 重绘 的交互骨架 |

配套的完整示例可以参考 [tkfluent](https://pypi.org/project/tkfluent)——
它就是用这几个零件搭出来的组件库。

## DObject：配置容器

`DObject` 给组件一个**统一读写属性**的接口，避免到处写 `self.xxx = ...`：

```python
from easydict import EasyDict

from tkdeft.object import DObject


class MyWidget(DObject):
    def __init__(self):
        self.attributes = EasyDict({
            "text": "",
            "text_color": "#000000",
            "state": "normal",
        })

    def set_text(self, text):
        self.dconfigure(text=text)


widget = MyWidget()
widget.set_text("你好")
print(widget.dcget("text"))      # 你好
print(widget.dcget("没这个键"))   # None
```

要点：

* `dconfigure(**kwargs)` **只接受已经存在于 `attributes` 里的键**，
  写错的键会被静默忽略——这是有意的，防止笔误污染组件状态。
* 所以要新增一个可配置项，必须先把键放进 `attributes`。
* `dcget(key)` 读不到时返回 `None`，不抛异常。

## DDrawWidget：交互骨架

`DDrawWidget` 是"用画布画出来的控件"的基类，它替你处理好了
**鼠标/焦点事件 → 内部状态 → 重绘** 这条链路：

```python
from tkdeft.svg import add_roundrect
from tkdeft.windows.canvas import DCanvas
from tkdeft.windows.draw import DSvgDraw
from tkdeft.windows.drawwidget import DDrawWidget


class MyDraw(DSvgDraw):
    def create_roundrect(self, x1, y1, x2, y2, radius, radiusy=None,
                         temppath=None, fill="transparent", outline="black",
                         width=1):
        drawing = self.create_drawing(x2 - x1, y2 - y1, temppath=temppath)
        add_roundrect(drawing[1], x1, y1, x2, y2, radius, radiusy,
                      fill=fill, outline=outline, width=width)
        drawing[1].save()
        return drawing[0]


class MyCanvas(DCanvas):
    draw = MyDraw


class MyWidget(MyCanvas, DDrawWidget):
    def _draw(self, event=None):
        super()._draw(event)              # 处理背景色等公共部分
        if not self.winfo_ismapped():
            return

        width, height = self.winfo_width(), self.winfo_height()
        if hasattr(self, "element"):
            self.delete(self.element)

        if self.button1:
            color = "#cccccc"
        elif self.enter:
            color = "#ffffff"
        else:
            color = "#f3f3f3"

        self.element = self.create_roundrect(
            0, 0, width, height, 6,
            temppath=self.temppath,
            fill=color, outline="#000000", width=1,
        )
```

`DDrawWidget` 已经绑好并维护了这些状态，供 `_draw` 直接读取：

| 属性 | 含义 |
| --- | --- |
| `self.enter` | 鼠标是否在控件内 |
| `self.button1` | 左键是否按下 |
| `self.isfocus` | 是否持有焦点 |
| `self.temppath` ~ `temppath4` | 可复用的临时文件路径（惰性创建） |

触发重绘的事件：`<Configure>` `<Enter>` `<Leave>` `<Button-1>`
`<ButtonRelease-1>` `<FocusIn>` `<FocusOut>`。

松开左键且鼠标仍在控件内时，会生成一个 `<<Clicked>>` 虚拟事件：

```python
widget.bind("<<Clicked>>", lambda event: print("clicked"))
```

!!! warning "不要自己 mkstemp"
    `self.temppath` 这类属性是**惰性**的：真正用到时才创建文件，
    由绘图对象持有、并在控件销毁时回收。

    历史版本在 `__init__` 里一次性 `mkstemp()` 四个临时文件且从不关闭
    返回的 fd——20 个按钮就会泄漏 **80 个文件描述符 + 80 个残留文件**。
    请直接使用 `self.temppath`。

## 一次点击的完整顺序

```text
<Button-1>        →  button1 = True   → _draw()
<ButtonRelease-1> →  button1 = False  → _draw()
                          ↓
                   鼠标仍在控件内 → 生成 <<Clicked>>
```

所以"按住后把鼠标拖出去再松开"不会触发点击，与系统控件行为一致。

## 换一个绘制引擎

你的组件不需要关心底层是 SVG 还是 skia。只要在 `_draw` 里优先走栅格
快速路径，就能自动获得"进程内出图 + 结果缓存"的收益：

```python
item = self.create_roundrect_raster(
    0, 0, width, height, 6,
    fill="#ffffff", outline="#000000", outline_opacity=0.2,
)
if item is None:
    item = self.create_roundrect(...)      # 回退到 SVG
```

`create_roundrect_raster` 在当前引擎是 SVG 系（tksvg / wand）时返回 `None`，
表示"这条路径我不参与"，于是平稳回退到你自己的 SVG 实现。
细节见 [绘制引擎](custom-drawing.md)。

## 别忘了保活图片

Tkinter 的画布元素**不会**替 Python 侧持有 `PhotoImage` 引用。
一旦图片被垃圾回收，对应的画布元素会变成**空白**：

```python
# ✗ 同一画布上多张图片时，只有最后一张能活下来
self._img = self.svgdraw.create_svg_image(path)
self.create_image(0, 0, anchor="nw", image=self._img)

# ✓ 交给画布保管
self._img = self.svgdraw.create_svg_image(path)
item = self.create_image(0, 0, anchor="nw", image=self._img)
self._keep_photo(item, self._img)
```

`DCanvas._keep_photo(item, photo)` 按画布元素 id 记录引用，
并在元素失效后自动清理。
