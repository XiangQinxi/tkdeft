# 涟漪效果：给任意控件加一层扩散动画

`tkdeft.extra.ripple` **不提供按钮**。它只提供涟漪本身：
一个管理状态与计时的控制器，加上算出半透明图层的纯函数。
你已经有的按钮、卡片、缩略图，只要在重绘里按顺序多调几行，就能得到 Material 那种扩散效果。

`examples/ripple_button.py` 里的 `RippleButton` 是把这几行接起来的演示：
圆角底色、悬停/按压/禁用、文字、焦点环它自己画，涟漪交给 `tkdeft.extra.ripple`。

<figure markdown>
  ![涟漪逐帧与不透明度曲线](../assets/ripple-frames.png)
  <figcaption>四帧由 <code>ripple_layer()</code> 合成：底色走绘制引擎，涟漪是「圆角遮罩 ∩ 扩散圆」的 RGBA 图层。蓝点是按下位置，曲线是同一份 <code>ripple_alpha()</code></figcaption>
</figure>

## 三步接上

```python
from tkdeft.extra.ripple import Ripple


class MyButton(DDrawWidget):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.ripple = Ripple(self, on_frame=self._paint)     # ① 建控制器

    def _paint(self):
        self.delete("all")
        ...画底色...
        self.ripple.paint(color="#000000", opacity=0.12,     # ② 在合适层级贴涟漪
                          corner_radius=8)
        ...画文字...

    def _event_on_button1(self, event):
        super()._event_on_button1(event)
        self.ripple.start(event.x, event.y)                  # ③ 点击处起涟漪
```

控制器不碰 canvas item、也不决定颜色：它只在每帧通过 `on_frame` 喊你一声，
你来 `delete("all")` 再按「底色 → 涟漪 → 文字」的顺序重画。
所以涟漪压在哪一层、要不要跟着主题换色，全都由你的重绘代码决定。

不依赖 `DDrawWidget` 也行——任何有 `create_image` 和 `winfo_width` 的 Tk 控件都能用；
`on_frame` 也可以传 `None`，自己用 `after` 轮询 `states`。

## API

### 控制器

```python
Ripple(widget, on_frame=None, *, duration=500, frame_ms=16)
```

| 参数 | 说明 |
| --- | --- |
| `widget` | 宿主控件，用来取尺寸、贴图层 |
| `on_frame` | 每帧回调，通常直接传宿主的重绘方法 |
| `duration` | 一次涟漪的时长（毫秒） |
| `frame_ms` | 帧间隔（毫秒），默认 16 ≈ 60fps |

| 方法 / 属性 | 说明 |
| --- | --- |
| `start(x=None, y=None, started=None)` | 起播一次涟漪；不传坐标按控件中心。`started` 传 `time.monotonic()` 时刻可快进到某一帧；返回 `RippleState` |
| `stop()` | 立刻停掉全部涟漪并撤销计时器 |
| `paint(color="#000000", opacity=0.12, corner_radius=0.0, tag="ripple")` | 把所有正在播的涟漪贴上去，返回最后一张的 item id（没有则 `0`）；在宿主的重绘里调用 |
| `active` | 是否还有涟漪在播 |
| `states` | 正在播的 `RippleState` 列表，每个都能 `progress(duration)` |
| `advance()` | 丢掉已播完的状态（内部计时器会做，一般不用手调） |

### 纯函数

| 函数 | 说明 |
| --- | --- |
| `ripple_layer(width, height, corner_radius, x, y, progress, color="#000000", peak_opacity=0.12)` | 算出某一帧的 RGBA 图层：圆角裁剪 + 抗锯齿 + 半透明 |
| `ripple_alpha(progress, peak=0.12)` | 该帧的浓度：前 15% 淡入，之后幂曲线淡出 |
| `ripple_radius(width, height, x, y)` | 从 `(x, y)` 到最远角的距离，涟漪扩到它才盖满控件 |
| `ease_out_cubic(progress)` | 半径的缓动曲线：起步快、收尾慢 |

想完全自己控制节奏，可以只用 `ripple_layer()`，不碰控制器：

```python
from tkdeft.extra.ripple import ripple_layer

layer = ripple_layer(200, 48, 8, 100, 24, progress=0.4, peak_opacity=0.12)
photo = ImageTk.PhotoImage(layer, master=self)
item = self.create_image(0, 0, anchor="nw", image=photo)
self._keep_photo(item, photo)      # 别忘了保活
```

## 为什么不用 `create_oval`

Material 的涟漪是一圈**半透明**的圆，压在底色上，还要被**圆角**裁掉。
Tk 的 canvas item 没有逐像素 alpha：

* 给 item 设 `-alpha` 是**整块位图**的透明度，不是渐变的圆；
* `-stipple` 能给网点状的半透明，但没有抗锯齿，也没法逐帧变化浓度；
* `create_oval` 画出来的是**不透明**圆，会盖住底色和描边。

所以这里让 Pillow 先算出一张与控件等大的 RGBA 图层，再用 `create_image` 贴上去——
透明度、圆角裁剪、抗锯齿就都对上了。

## 图层是怎么算的

```python
scale = SUPERSAMPLE                     # 3 倍超采样，缩小后边缘才不毛刺
size = (width * scale, height * scale)

clip = Image.new("L", size, 0)          # 圆角矩形：涟漪不能漫出圆角
ImageDraw.Draw(clip).rounded_rectangle(
    (0, 0, size[0] - 1, size[1] - 1), radius=corner_radius * scale, fill=255
)

r = ripple_radius(width, height, x, y) * ease_out_cubic(progress) * scale
circle = Image.new("L", size, 0)        # 当前半径的实心圆
ImageDraw.Draw(circle).ellipse(
    (x * scale - r, y * scale - r, x * scale + r, y * scale + r), fill=255
)

# 逐像素取较小值 = 求交；再缩小到控件尺寸，顺便得到抗锯齿
mask = ImageChops.darker(clip, circle).resize((width, height), Image.LANCZOS)
mask = mask.point(lambda value: int(value * opacity))

layer = Image.new("RGBA", (width, height), color)
layer.putalpha(mask)
```

`ripple_radius()` 取的是**按下点到最远角**的距离——涟漪扩到这么大才算盖满控件，
否则从角落按下时涟漪会在控件中间就停住。

浓度单独走一条曲线（`ripple_alpha`）：前 15% 淡入、之后按 `**1.2` 淡出。
半径与浓度分开，视觉上才像 Material：先是**一团浓色迅速铺开**，再**整体慢慢褪掉**。

## 计时：16 ms 一帧，进度按时间算

```python
def _tick(self):
    self._job = None
    if not self._states:
        return
    self.advance()            # 丢掉已经播完的
    self._notify()            # 叫宿主重绘
    self._schedule()          # 再来一帧
```

进度不是"每帧 +16 ms"累加出来的，而是每帧用 `time.monotonic()` 重新算：

```python
@dataclass
class RippleState:
    x: float
    y: float
    started: float

    def progress(self, duration=500):
        elapsed_ms = (time.monotonic() - self.started) * 1000.0
        return min(1.0, max(0.0, elapsed_ms / duration))
```

这样**掉帧只丢帧、不拖时长**：主线程卡一下，下一帧直接跳到正确的进度。
`start(started=...)` 把起始时刻开放出来，一行就能复现"播到 40%"的那一帧。

`after(...)` 挂在宿主控件上，撤销也用宿主的 `after_cancel`；
**不要对 `root` 调 `after_cancel`**（见 [常见问题与排查](faq.md) 第 5 条）。
控制器还替你在宿主 `<Destroy>` 时清掉计时器，免得回调打到已销毁的控件上。

## 图片保活

每一帧都是新的 `PhotoImage`，**必须保活**，否则 Python 侧一回收，画布上的图就变白板。
控制器已经处理：宿主是 `DCanvas` 时走它的 `_keep_photo()`，否则自己记一份并在下次
`paint()` 时清理已被 `delete` 的 item。

```python
photo = ImageTk.PhotoImage(layer, master=self)
item = self.create_image(0, 0, anchor="nw", image=photo, tags=("ripple",))
self._keep_photo(item, photo)      # 少了这一行，涟漪跑几帧就消失
```

## 拿示例当参照

```bash
python examples/ripple_button.py                      # 默认自动挑栅格引擎（skia > cairo > pillow）
python examples/ripple_button.py --engine tksvg       # 指定引擎，观察每帧重绘的开销差异
python examples/ripple_button.py --theme dark         # 深色主题
python examples/ripple_button.py --check              # 只跑自检，不开窗口
```

| 参数 | 作用 |
| --- | --- |
| `--engine NAME` | 用哪个绘制引擎（`tksvg` / `wand` / `skia` / `pillow` / `cairo`） |
| `--theme {light,dark}` | 初始主题；窗口里按 `T` 也能切 |
| `--check` | 非交互自检：涟漪几何 + 控制器接到控件后的生命周期，退出码 `0` 表示全过 |

示例里的接法与上面「三步接上」完全一致，只多了按钮自己的状态与配色；
想抄得完整一点就直接看 [`examples/ripple_button.py`](https://github.com/XiangQinxi/tkdeft/blob/master/examples/ripple_button.py)。

## 写自己的控件时会踩的三个坑

### 坑 1：基类顺序写错会直接崩

```python
class RippleButton(DCanvas, DDrawWidget): ...
# TypeError: Cannot create a consistent method resolution order (MRO)
#            for bases DCanvas, DDrawWidget
```

`DDrawWidget` 本身就继承自 `DCanvas`（中间还隔着 `DDrawWidgetCanvas`）,
所以只需要 `class RippleButton(DDrawWidget)`。基类一多，MRO 立刻罢工。

### 坑 2：`draw_roundrect()` 不接受 `tags`

```python
item = self.draw_roundrect(..., tags=("body",))
# ValueError: Invalid attribute 'tags' for svg-element <rect>.
```

`draw_roundrect()` 的额外关键字参数最终会交给 svgwrite 的 `rect(**kwargs)`，
而 `tags` 不是合法 SVG 属性——**只有走 SVG 回退路径时才会暴露**，
在栅格引擎上测不出来。打标签请用返回值：

```python
item = self.draw_roundrect(...)
self.addtag_withtag("body", item)
```

### 坑 3：第一帧是空的，直到鼠标划过

**症状**：窗口起来了，控件位置一片空白；鼠标移上去才出现。

**原因**：`DDrawWidget._draw()` 里有一句 `if not self.winfo_ismapped(): return`。
"先把控件 `pack()` 好、再 `mainloop()`"的写法中，`<Configure>` 往往在窗口
**映射之前**就发完了（那时 `winfo_width()` 还是 `1`），映射之后再也不会来一次——
于是控件永远停在"没画"的状态，涟漪自然也起不来。

**怎么办**：补一个 `<Map>` 绑定，映射发生时再画一次（示例里这么做）：

```python
self.bind("<Map>", self._event_map, add="+")

def _event_map(self, event=None):
    self._draw(event)
```

这个问题只影响"先建 UI 再进事件循环"的写法；如果你在已经显示的窗口里
动态创建控件，`<Configure>` 会正常到来，看不出异常。

## 性能

每帧都是**全量重绘**（`delete("all")` + 重新渲染底色 + 合成涟漪图层），
在本仓库的开发机上测一个 200×48 的按钮、40 帧的耗时：

| 引擎 | 中位数 | p95 |
| --- | --- | --- |
| `skia` | 0.42 ms | 0.90 ms |
| `pillow` | 0.38 ms | 0.79 ms |
| `cairo` | 0.41 ms | 0.64 ms |
| `tksvg` | 4.66 ms | 6.43 ms |
| `wand` | 5.35 ms | 7.41 ms |

60 fps 的预算是每帧 16.7 ms，所以哪怕走默认的 SVG 引擎（`tksvg`）也还有两倍余量；
换成栅格引擎后开销低一个数量级。测量方式是包住 `_paint()` + `update_idletasks()`
循环 40 次，取中位数与 p95。

!!! tip "想再快一点"
    真正贵的是每帧重新渲染底色。把底色渲一次缓存成 `PhotoImage`，
    只在尺寸 / 主题 / 状态变化时重建，涟漪帧就只剩"合成 + 贴图"。
    示例里没这么做，是因为它想演示"最直白的写法够不够用"——答案在这个尺寸下是够的。

## 下一步

* [自定义组件](custom-widget.md) —— `DObject` / `DCanvas` / `DDrawWidget` 的完整接口
* [绘制引擎](custom-drawing.md) —— 换引擎、写引擎、缓存与像素预算
* [API：extra.ripple](../api/tkdeft.extra.ripple.md) —— 每个函数与方法的签名、参数
