# 绘制引擎

`tkdeft` 把"**画什么**"和"**用什么画**"分开了。

组件不再直接拼 SVG，而是描述一个 **绘制规格（spec）**——尺寸、圆角、填充色、
描边色与透明度……然后把它交给**当前引擎**去栅格化。换引擎不需要改一行业务代码。

## 内置引擎

| 引擎 | 类型 | 说明 | 额外依赖 |
| --- | --- | --- | --- |
| `tksvg` | SVG | 默认。`svgwrite` 生成 SVG → `tksvg` 栅格化，保持历史行为 | 无 |
| `wand` | SVG | 经 Wand(ImageMagick) 转 PNG | `Wand` |
| `skia` | 栅格 | `skia-python`，进程内直接出位图，速度与画质最好 | `pip install tkdeft[skia]` |
| `pillow` | 栅格 | Pillow 超采样抗锯齿，**永远可用** | 无（Pillow 是硬依赖） |
| `cairo` | 栅格 | `pycairo` | `pip install tkdeft[cairo]` |

## 切换引擎

```python
from tkdeft.engines import set_engine, get_engine, list_engines

print(list_engines())
# {'tksvg': True, 'wand': True, 'skia': True, 'pillow': True, 'cairo': True}

set_engine("skia")     # 按名字
set_engine(2)          # 或按编号：0=tksvg 1=wand 2=skia 3=pillow 4=cairo

print(get_engine().name)
```

引擎不可用时 `set_engine` 会抛 `ValueError`（而不是静默退回慢路径），
免得你以为开了 `skia`、其实还在走磁盘。

## 直接渲染一张图

```python
from tkdeft.engines import RoundRectSpec, render_roundrect

spec = RoundRectSpec(
    width=120, height=32, rx=6,
    fill="#ffffff", fill_opacity=1,
    outline="#000000", outline_opacity=0.2,
    outline_width=1,
)

photo = render_roundrect(spec, master=widget)   # -> tkinter.PhotoImage
```

当前引擎是 SVG 系时返回 `None`，表示"这条路径我不参与"，
调用方应当回退到既有的 `svgwrite` + `tksvg` 流程。

可用的规格有三类：`RoundRectSpec`（圆角矩形）、`TrackSpec`（滑块进度条槽）、
`ThumbSpec`（滑块圆形把手）。

## 缓存

渲染结果按 `(引擎名, 图元类型, spec)` 缓存。因为 spec 是不可变的，
**同尺寸同配色的一组控件会共用同一张 `PhotoImage`**。

```python
from tkdeft.engines import cache_stats, set_cache_budget, clear_cache

print(cache_stats())
# {'interpreters': 1, 'entries': 62, 'pixels': 169244, 'budget': 8000000,
#  'hits': 178, 'misses': 99, 'hit_rate': 0.642, 'overflow': 0}

set_cache_budget(16_000_000)   # 调大像素预算
clear_cache()                  # 清空（注意：会清掉已发出的图片引用）
```

缓存**不做 LRU 淘汰**。原因是 `PhotoImage` 一旦被回收，
引用它的 canvas item 会变成**空白**——这是 Tkinter 的经典陷阱。
所以这里采用"像素预算 + 满了就不再写入"：已经发出去的图片永远保持存活，
缓存不下的规格退化为"每次重新渲染"，只损失速度，绝不损坏画面。

## 自己写一个引擎

继承 `DrawEngine`，实现需要的渲染方法，然后注册：

```python
from tkdeft.engines import DrawEngine, register_engine


class MyEngine(DrawEngine):
    name = "myengine"
    kind = "raster"                  # 只有 raster 会走快速路径
    requires = ("mylib",)            # 用于 available() 探测

    def render_roundrect(self, spec):
        # 返回 PIL.Image（RGBA）即可
        ...


register_engine(MyEngine())
```

`requirements` 里的模块探测不到时，`set_engine("myengine")` 会报错并说明缺什么。

## 坐标与描边约定

所有 spec 的坐标都以自身左上角为 `(0, 0)`，并且**描边是居中的**：
几何会被向内收缩半个线宽，使描边的外沿正好贴合图片边缘。

这正是历史上出问题的地方——旧代码把矩形放在 `(0.5, 0.5)` 却仍用整宽整高，
描边中心线正好压在画布边界上，于是**下边框和右边框被整个裁掉**。
`tkdeft.svg.roundrect_geometry()` 用同一套规则计算 SVG 几何，
保证 SVG 引擎与栅格引擎画面一致。
