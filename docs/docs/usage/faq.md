# 常见问题与排查

这一页收集的是**真实踩过的坑**——大部分来自 Tkinter 本身的语义，而不是 `tkdeft`
的 bug。每条都按 **症状 / 原因 / 怎么办** 写，配可运行的片段。

排查顺序建议：

1. 先看当前引擎对不对：`python -c "from tkdeft.engines import get_engine_name; print(get_engine_name())"`
2. 再跑一遍自检：`python -m tkflu --check -r <引擎名>`
3. 还不对就跑回归：`python benchmarks/run_all.py --quick`（详见 [回归与性能](benchmarks.md)）

---

## 一、画面不对

### 1. 画布上的图片变成空白

**症状**：同一画布上画了多张图片，过一会儿（触发 GC 后）除最后一张外**全部变空白**；
或者窗口 resize 之后图元消失。

**原因**：Tkinter 的画布元素**不会**替 Python 侧持有 `PhotoImage` 引用。图片对象一旦被
垃圾回收，对应的 canvas item 就变成空白——这是 Tkinter 的经典陷阱。历史代码只用
`self._tkimg` 保存"最后一张"，所以画第二张时第一张就失去了引用。

**怎么办**：让画布替你保管引用，或者直接用统一入口（内部已经保活）。

```python
# ✓ 推荐：统一入口自己会 _keep_photo，返回的一定是 canvas item id
item = canvas.draw_roundrect(0, 0, 120, 32, 6, fill="#ffffff")

# ✓ 手工绘制：把 PhotoImage 交给画布保管
photo = canvas.svgdraw.create_svg_image(path)
item = canvas.create_image(0, 0, anchor="nw", image=photo)
canvas._keep_photo(item, photo)          # ← 关键的一行
```

```python
# ✗ 历史错误写法：只存"最后一张"
self._tkimg = canvas.svgdraw.create_svg_image(path)
canvas.create_image(0, 0, anchor="nw", image=self._tkimg)
# 下一次绘制覆盖 self._tkimg 后，上一张就可能在 GC 时变空白
```

`DCanvas._keep_photo(item, photo)` 按 item id 记录引用，并在元素失效后自动清理；
`draw_roundrect` / `draw_track` / `draw_thumb` 内部都调了它。

!!! tip "为什么缓存不做 LRU 淘汰"
    因为"淘汰"就等于"回收图片"就等于"画面变空白"。缓存改用像素预算
    （默认 8M 像素，满了就不再写入），已经发出去的图片永远存活。
    详见 [绘制引擎](custom-drawing.md)。

### 2. `canvas.delete("all")` 把叠加内容一起删掉

**症状**：自己往画布上追加的元素（文字、图元、内嵌控件）在组件下一次重绘后消失。

**原因**：`delete("all")` 删除的是**画布上的全部 item**，包括子窗口 item 和所有叠加元素。
"整幅重绘"风格的组件会在 `_draw()` 开头调用它，于是你以为"加进去了"的东西立刻被擦掉。

**怎么办**：叠加内容要放在 `delete("all")` **之后**画；稳妥的做法是覆盖 `_draw`，
先让基类画完背景，再画自己的东西。`FluFrame`（tkfluent）这类"画布 + 内嵌控件"的结构
必须这样处理。

```python
from tkdeft.windows.canvas import DCanvas
from tkdeft.windows.drawwidget import DDrawWidget


class MyCanvas(DCanvas):
    """只提供绘制后端——注意 _draw 不在 DCanvas 上，而在 DDrawWidget 上。"""


class MyWidget(MyCanvas, DDrawWidget):
    def _draw(self, event=None):
        super()._draw(event)           # 基类：同步背景色；未映射时它会提前返回
        if not self.winfo_ismapped():  # 但那只是结束 super()，这里要自己再判一次
            return

        self.delete("all")             # 整幅重绘：清掉画布上的全部 item
        self.element = self.draw_roundrect(
            0, 0, self.winfo_width(), self.winfo_height(), 6,
            fill="#ffffff", outline="#000000",
        )
        self.tag_raise(self.element)   # 需要压在最上层时显式抬升
```

更多"怎么搭一个自己的控件"见 [自定义组件](custom-widget.md)。

---

## 二、尺寸与布局

### 3. `withdraw()` 状态下量不到尺寸

**症状**：控件的 `winfo_width()` 恒为 `1`，布局断言全部失败，按尺寸画的图只有一个小点。

**原因**：窗口未映射时 Tk 不做几何计算，`winfo_width()/winfo_height()` 一律返回 `1`
（它们反映的是"最后一次 `<Configure>` 确定的几何"，而还没映射时压根没有这个事件）。

**怎么办**：先让窗口真实映射并 `update()`，再测量。

```python
import tkinter

root = tkinter.Tk()
root.geometry("640x480")
root.update()                     # ← 让 Tk 完成一次布局

widget.pack()
root.update()
print(widget.winfo_width())       # 现在才是真实宽度
```

!!! note "写布局检查时"
    没有可用桌面会话的环境里应当**跳过而不是失败**——
    `benchmarks/check_layout.py` 就是这么做的。

### 4. 不要用 `len(text) * N` 估算文本宽度

**症状**：中文菜单项/标签被裁掉，或者按钮挤成一团（`"文件"` 按 `len * 8` 只算出 **16px**）。

**原因**：CJK 是**宽字符**，一个汉字大约等于两个西文字符的宽度；按字符个数乘常数
严重偏窄，中英文混排时误差更大。

**怎么办**：向 Tk 要真实字体度量。

```python
from tkinter.font import Font

font = Font(family="Segoe UI", size=10)

width = font.measure("文件")      # ✓ 真实像素宽度
# width = len("文件") * 8         # ✗ 对中文差一倍以上
```

---

## 三、生命周期与资源

### 5. 不要直接对 root 调 `after_cancel()`

**症状**：关窗时刷 `TclError: can't delete Tcl command`；严重时 `root.destroy()`
根本没销毁窗口、`tkinter._default_root` 残留，之后再建窗口就撞
`bad window path name`。

**原因**：`after` 回调注册在 **Tcl 解释器**上，而生成的 Tcl 命令名记在**发起控件**的
`_tclCommands` 列表里。直接对 root 调 `after_cancel()` 会删掉那条 Tcl 命令，但
`root._tclCommands.remove(name)` 会**静默失败**（名字不在 root 的列表里）；等那个控件
自己被销毁时，`Misc.destroy` 拿这个已经删掉的命令再删一次 → 抛异常 → 异常一路冒到
`root.destroy()`。

**怎么办**：**谁注册，谁取消**。`tkfluent` 的做法是把 after id 记在控件上，
销毁时用控件自己取消（实现见 `tkflu/_after.py`）。

```python
class MyWidget(DCanvas, DDrawWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._after_id = None
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._after_id = self.after(10, self._deferred_update)

    def _deferred_update(self):
        self._after_id = None
        if self.winfo_exists():
            self.update()

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self:
            return          # 子控件的 <Destroy> 也会冒泡到父控件
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)   # self 就是注册者，正确
            except Exception:
                pass
            self._after_id = None
```

!!! danger "别图省事"
    `root.after_cancel(some_id)` 往往"看起来能跑"——代价要到控件销毁时才结算，
    而且症状出现在**关窗**那一刻，很难联想到元凶。

### 6. 临时文件与文件描述符：不要自己 `mkstemp()`

**症状**：长跑程序句柄耗尽；系统临时目录里堆满 `tkdeft.temp.*`。历史实测：
20 个按钮泄漏 **80 个文件 + 80 个 fd**。

**原因**：旧实现每次绘制都 `mkstemp()` 新建文件，且从不 `close(fd)`。

**怎么办**：用绘制对象提供的 scratch 路径——惰性创建、复用一个文件、控件销毁时回收。

```python
# ✓ 绘制后端：同一个 slot 始终复用同一个路径
path = draw.scratch_path(".svg", slot=1)

# ✓ 控件内部：直接用现成的 temppath ~ temppath4（惰性属性）
item = self.draw_roundrect(..., temppath=self.temppath, temppath2=self.temppath3)

# ✗ 不要自己建
from tempfile import mkstemp
fd, path = mkstemp(suffix=".svg")   # fd 忘了关 → 每帧泄漏一个
```

!!! tip "谁负责回收"
    `DSvgDraw.cleanup()` 会删掉本对象创建的 scratch 文件；`DCanvas` 在
    `<Destroy>` 事件里自动调用它。

### 7. 长期运行程序的句柄回收

**症状**：反复创建/销毁控件后，临时文件不减少、图片引用（`_photo_refs`）一直涨。

**原因**：清理动作挂在 `<Destroy>` 事件上。如果你覆盖了
`DCanvas._event_destroy_draw` 却没有调用 `super()`，或者用的是裸 `tkinter.Canvas`
而不是 `DCanvas`，清理就不会发生。

**怎么办**：别丢掉父类实现。

```python
def _event_destroy_draw(self, event=None):
    super()._event_destroy_draw(event)   # ← cleanup() + 清空 _photo_refs
    # 自己的清理逻辑写在这里
```

它做两件事：调用 `svgdraw.cleanup()` 删除 scratch 临时文件；清空 `_photo_refs`。

---

## 四、Tk 解释器与 master

### 8. 创建控件不传 `master`

**症状**：内嵌控件"跑到别的窗口去了"、控件销毁后内嵌的原生控件不回收、多 `Toplevel`
场景下嵌不进去。

**原因**：不传 `master` 时，Tkinter 会把控件挂到**默认根窗口**（`tkinter._default_root`），
而不是你正在构造的那个控件。

**怎么办**：显式传 `master`；自定义控件里创建原生控件时传 `master=self`。

```python
from tkinter import Entry

class MyEntry(DCanvas, DDrawWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = Entry(self)      # ✓ 挂到自身，随自身一起销毁
        # Entry()                     # ✗ 不传 master → 挂到默认根窗口
```

!!! warning "图片也绑定解释器"
    `PhotoImage` 同样绑定在具体的 Tk 解释器上，所以创建图片时要带
    `master=`（`DCanvas` 会把自身注入给绘制后端）。多解释器场景下漏传会报
    `image "pyimage1" doesn't exist`。

---

## 五、绘制引擎

### 9. 引擎装了却用不了

**症状**：`set_engine("skia")` 抛 `ValueError`，提示缺少依赖。

**原因**：依赖确实没装（或装在另一个 Python 解释器里），于是该引擎的 `available()`
为 `False`。`tkdeft` 宁可报错也不静默退回慢路径。

**怎么办**：先看清单，再切。

```python
from tkdeft.engines import list_engines, describe_engines, set_engine

list_engines()          # {'tksvg': True, 'wand': True, 'skia': True, ...}
describe_engines()      # 每项的编号 / 类型 / 依赖 / 是否可用 / 是否当前

for row in describe_engines():
    if not row["available"]:
        print(row["name"], "缺少依赖：", row["requires"])

set_engine("skia")      # 缺依赖时抛 ValueError，并说明缺哪个包
```

!!! tip "名字拼错会怎样"
    拼错会抛 `UnknownEngineError`（`ValueError` 的子类），错误信息里附带
    "你是不是想用 …" 的提示。引擎清单与自定义引擎见
    [绘制引擎](custom-drawing.md) 与 [engines API](../api/tkdeft.engines.md)。

### 10. 想固定走 SVG 做对照

**症状**：想验证"栅格引擎和 `tksvg` 画得是不是一样"，或想排查只在 SVG 路径下出现的问题，
但默认已经走了快速路径。

**怎么办**：按画布关，或按单次调用关。

```python
canvas.raster_enabled = False             # 这个画布之后全走 SVG
canvas.draw_roundrect(..., raster=False)  # 只这一次走 SVG

from tkdeft.engines import reset_engine
reset_engine()                            # 引擎整体退回默认 tksvg（=0）
```

### 11. 引擎渲染失败不会被抛出来

**症状**：界面"看着不太对"，但控制台只有一条 `RuntimeWarning`（每个引擎只警告一次），
之后再无任何提示。

**原因**：单个引擎渲染失败会**自动回退到 SVG 路径**，以免整个界面挂掉；错误只记录
最后一次。这是刻意的容错设计，但也就意味着异常不会冒泡到你面前。

**怎么办**：主动查。

```python
from tkdeft.engines import last_engine_error, clear_engine_error

print(last_engine_error())   # -> "skia: ValueError: ..." 或 None（正常）
clear_engine_error()         # 清掉记录，允许下次失败时重新警告一次
```

### 12. 以为开了 skia，其实还在走慢路径

**症状**：切了引擎但没变快。

**原因**：设置被别处覆盖了（环境变量、子进程、其他模块导入时又调 `set_renderer(0)`），
或者当前根本就没切成功。

**怎么办**：别凭记忆，直接问当前状态。

```python
from tkdeft.engines import get_engine_name, get_engine

print(get_engine_name())     # -> "skia"
print(get_engine().kind)     # -> "raster"（只有栅格引擎才走快速路径）

# tkfluent 里对应的是：
from tkflu.designs.renderer import get_renderer, get_renderer_name

print(get_renderer(), get_renderer_name())    # -> 2 skia
```

!!! note "环境变量里也有一份"
    `tkfluent` 会把当前编号记在环境变量 `tkfluent.renderer` 里，便于子进程继承；
    直接对比它与 `get_engine_name()`，就能确认两边是否一致。

---

## 六、验证手段

### 13. 截 Tk 窗口不要用 `PIL.ImageGrab`

**症状**：截出来的图是**别的窗口**（例如浏览器），或者内容错位、缺一块。

**原因**：`ImageGrab` 按**屏幕坐标**抓取，在 DPI 缩放、多虚拟桌面、窗口被遮挡的情况下
都会抓错对象。

**怎么办**：按**窗口句柄**抓（Win32 `PrintWindow`）——既不受遮挡影响，也不受坐标映射影响。

```bash
# 把整个组件画廊真实显示出来并截图，输出到 benchmarks/_out/
python benchmarks/visual_demo.py light skia
python benchmarks/visual_demo.py dark pillow
```

实现见 `benchmarks/visual_demo.py` 里的 `capture_window()` / `grab()`；更多见
[回归与性能](benchmarks.md)。

!!! note "截图前记得让窗口映射"
    窗口处于 `withdraw()` 状态时 `PrintWindow` 抓到的是空白——截图前先
    `deiconify()` 或 `update()`。
