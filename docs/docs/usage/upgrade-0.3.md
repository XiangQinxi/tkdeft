# 从 0.2 升级到 0.3

**结论先放这里：0.3.0 是纯加法，没有破坏性改动。** 旧代码可以原样跑，
升级后你多出一些更省事的入口。这一页只讲"改了会得到什么、以及值得顺手改的地方"。

```bash
pip install -U tkdeft
```

## 一句话总结

| 0.2 的写法 | 0.3 的写法 | 收益 |
| --- | --- | --- |
| 先试 `create_roundrect_raster`，返回 `None` 再回退 SVG | `canvas.draw_roundrect(...)` | 少写 10 行样板，且不会再漏掉回退分支 |
| `self._img = ...; self._tkimg = ...` 手工保活 | 统一入口内部已保活 | 不会再出现"画布变空白" |
| `get_renderer() == 1` 判断 Wand 特例 | 不变（仍然兼容），但新增 `get_engine_name()` | 语义更清楚，不会再落进"新引擎编号没人管"的空档 |
| `DObject` 只有 `dconfigure` / `dcget` | 新增 `dget` / `dhas` / `dkeys` / `dvalues` / `ditems` / `dcopy` / `dreset` | 可遍历、可复制、可重置 |
| 想列出引擎只有 `list_engines()` | 新增 `describe_engines()` / `available_engines()` / `engine_index()` | 拿到编号、类型、依赖、是否当前 |

## 值得顺手改的四处

### 1. 用统一入口替代"两路绘制"样板

0.2 里每个组件都要自己写一遍这个模式：

```python
# 旧：栅格优先 + SVG 回退，每个组件抄一遍
item = self.create_roundrect_raster(x1, y1, x2, y2, radius,
                                    fill=fill, outline=outline, width=width)
if item is not None:
    return item
self._img = self.svgdraw.create_roundrect(x1, y1, x2, y2, radius,
                                          fill=fill, outline=outline, width=width)
self._tkimg = self.svgdraw.create_svg_image(self._img)
return self._keep_photo(self.create_image(x1, y1, anchor="nw", image=self._tkimg),
                        self._tkimg)
```

0.3 收敛成一行，而且返回值**一定**是 item id：

```python
# 新：判定与回退都由 tkdeft 负责
return self.draw_roundrect(x1, y1, x2, y2, radius,
                           fill=fill, outline=outline, width=width)
```

需要给某类图元换一套 SVG 实现时，覆盖钩子而不是重写流程：

```python
class MyCanvas(DCanvas):
    def draw_roundrect_svg(self, x1, y1, x2, y2, radius, radiusy=None,
                           *, temppath=None, temppath2=None, **kwargs):
        kwargs.setdefault("id", ".MyFigure")      # 只改"怎么画"
        return super().draw_roundrect_svg(x1, y1, x2, y2, radius, radiusy,
                                          temppath=temppath, temppath2=temppath2,
                                          **kwargs)
```

### 2. 想强制走 SVG 做对照

```python
canvas.raster_enabled = False               # 这个画布之后全走 SVG
canvas.draw_roundrect(..., raster=False)    # 只这一次走 SVG
```

做引擎对照、排查"只在 SVG 路径下出现的问题"时特别有用。

### 3. `theme()` 里别用参数判断分支（tkfluent 踩过的真坑）

一键换肤时 `FluThemeManager` **只传 `mode`**，如果你写：

```python
def theme(self, mode="light", style=None):
    if mode.lower() == "dark":
        if style.lower() == "accent":     # ✗ style 可能是 None → AttributeError
```

运行时就会崩在 `'NoneType' object has no attribute 'lower'`。正确做法是用构造时存下来的
`self.style`，并给它一个兜底：

```python
    style = getattr(self, "style", None) or "standard"
```

### 4. 别让容错逻辑吞掉真异常

自检/测试里为了跳过"没有这个钩子的组件"而写 `except AttributeError: continue`，
会把**钩子内部**抛出的 `AttributeError` 一起吞掉——测试全绿、界面一点就崩。
判断"有没有这个能力"要先用 `getattr`/`hasattr` 问，而不是事后 `try/except` 猜。

## 新老名字对照

旧名字一个都没删，下面这些是"新名字更好用"的对照：

| 旧 | 新 | 备注 |
| --- | --- | --- |
| `create_round_rectangle(...)` | `draw_roundrect(...)` | 旧名仍在，等价于新入口 |
| `create_roundrect_raster(...)` | `draw_roundrect(..., raster=True)` | 旧名仍在，只走栅格、不支持时返回 `None` |
| `create_svg_image(path, path2, way=get_renderer())` | `create_svg_image(path, path2)` | `way=None` 时按当前引擎自动选 tksvg / Wand |
| `set_renderer(2)`（tkfluent） | `set_engine("skia")` | 编号写法仍然兼容 |
| `renderer.py` 里自定义的引擎表 | `describe_engines()` | 不用再维护第二份表 |

## 升级后请跑一遍

```bash
python benchmarks/run_all.py --quick      # 8 项回归（含两个文档站）
```

如果目录里有你自己的组件，重点看两件事：

1. 有没有"只看引擎编号判断分支"的代码（`== 0` / `elif == 1` 且没有 else）——
   新增引擎编号会落进空档；
2. 有没有手工管理 `PhotoImage` 引用、或自己 `mkstemp()` 的地方——
   这两类问题在 [常见问题与排查](../usage/faq.md) 里有对照写法。

## 相关

* [绘制引擎](custom-drawing.md) —— 0.3 新增的引擎查询接口
* [自定义组件](custom-widget.md) —— 统一入口与可覆盖钩子
* [更新日志](../index.md) —— 完整的版本变更清单
