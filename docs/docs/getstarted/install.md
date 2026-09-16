# 安装

## 环境要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Python | **3.8+** | `pyproject.toml` 里写的是 `^3.7`，但硬依赖 `Pillow >= 10.2` 实际要求 3.8+ |
| Tk | **8.6+** | `tksvg` 依赖它；Windows 官方 Python 自带，Linux 需要 `python3-tk` |
| 平台 | Windows / macOS / Linux | 本项目的开发与回归环境是 Windows + CPython 3.13 + Tk 8.6.15 |

可以用一条命令确认 Tk 版本：

```python
import tkinter

print(tkinter.TkVersion)      # 8.6
```

## 安装

```bash
pip install -U tkdeft
```

这会带上这些**硬依赖**，一般不需要你操心：

| 包 | 作用 |
| --- | --- |
| `tksvg` | 让 Tkinter 能显示 SVG（默认引擎就是它） |
| `svgwrite` | 生成矢量图 |
| `pillow` | 位图处理与 `PhotoImage` 转换；**Pillow 引擎**也靠它 |
| `numpy` | 栅格引擎的像素运算 |
| `tkextrafont` | 加载内嵌字体，保证跨平台外观一致 |
| `easydict` | 组件属性容器（`DObject.attributes`） |

## 可选：更快的绘制引擎

默认引擎 `tksvg` 的工作方式是"生成 SVG → 写临时文件 → 再读回来栅格化"，每次重绘都要碰磁盘。
装上**进程内栅格引擎**后，图元直接在内存里出图：

```bash
pip install "tkdeft[skia]"      # skia-python，速度与画质最好
pip install "tkdeft[cairo]"     # pycairo
pip install "tkdeft[raster]"    # 上面两个都装
```

不装也能用——`Pillow` 引擎（编号 3）零额外依赖，**永远可用**。

## 验证安装

```python
import tkdeft

print(tkdeft.__version__)            # 0.3.0

from tkdeft.engines import describe_engines

for row in describe_engines():
    state = "可用" if row["available"] else f"缺依赖 {list(row['requires'])}"
    print(f"{row['index']}  {row['name']:8s} {state}")
```

```
0  tksvg    可用
1  wand     可用
2  skia     可用
3  pillow   可用
4  cairo    可用
```

`tksvg` 与 `pillow` 应当总是可用；`skia` / `cairo` / `wand` 取决于你装了什么。
**能列出名字不等于能用**——判据是 `available` 那一列。

## 三个常见安装问题

### 1. `ModuleNotFoundError: No module named 'tkdeft.engines'`

环境里装的是 0.2.0 之前的 tkdeft（没有引擎层）：

```bash
pip install -U tkdeft
```

如果你在 IDE 里跑的是仓库源码，而 `import` 又命中了 site-packages 里的旧版本，
请参考下一节"参与开发"里的做法，把仓库以 **editable** 方式装进环境。

### 2. 装了 skia 却提示缺依赖

`set_engine("skia")` 会检查依赖并**直接报错**，而不是静默退回慢路径：

```python
from tkdeft.engines import set_engine

set_engine("skia")
# ValueError: 绘制引擎 'skia' 不可用，缺少依赖：('skia', 'numpy', 'PIL')
```

常见原因是把包装进了**另一个** Python 解释器。用 `sys.executable` 确认一下：

```bash
python -c "import sys; print(sys.executable)"
python -m pip install "tkdeft[skia]"
```

### 3. 界面一个像素都不能变

默认引擎仍然是 `tksvg`，正是为了让老项目升级后外观不变；
栅格引擎与它在抗锯齿上有**亚像素差异**。要显式切换：

```python
from tkdeft.engines import set_engine

set_engine("skia")     # 或 set_engine(2)
```

## 参与开发（editable 安装）

在仓库目录里：

```bash
git clone https://github.com/XiangQinxi/tkdeft.git
cd tkdeft
python -m pip install -e .
```

editable 安装让 `import tkdeft` 稳定命中仓库代码，改完立即生效，不用重装。

!!! warning "测试脚本会自己插 `sys.path`，别被它骗了"
    `benchmarks/` 里的脚本会把仓库路径插到 `sys.path` 最前面，所以"检查全过"
    **不等于**用户在 IDE 里直接运行就没问题。改完公共接口后，请另外用真实方式
    跑一遍。踩坑记录见 [回归与性能](../usage/benchmarks.md#method)。

只刷新版本元数据、不动依赖：

```bash
python -m pip install -e . --no-deps
```

## 下一步

* [快速上手](quickstart.md) —— 五分钟画出第一个圆角矩形
* [概念与架构](concepts.md) —— 规格 / 引擎 / 画布 三者是什么关系
* [绘制引擎](../usage/custom-drawing.md) —— 切换、缓存、自己写引擎
