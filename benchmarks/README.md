# benchmarks — 绘制引擎基准与回归

这一组脚本用来**证明**性能提升和修复有效，而不是"看起来应该快了"。

## 一键跑完

```bash
python benchmarks/run_all.py          # 全部（含性能基准）
python benchmarks/run_all.py --quick  # 跳过性能基准
```

任一项失败即以非 0 退出，可直接接进 CI。

## 各项脚本

| 脚本 | 作用 |
| --- | --- |
| `check_engines.py` | 引擎自检：颜色通道序（红/蓝不对称）、alpha 是否被正确保留、半透明彩色是否被正确解预乘、**四条边描边是否都画全** |
| `check_fidelity.py` | 保真度：同一 spec 分别用 `tksvg` 参照与各栅格引擎渲染，逐像素比对，并输出放大拼图供目视 |
| `check_gallery.py` | 设计稿画廊：取 `tkflu.designs.button` 的**真实配色**，渲染 24 个按钮状态（浅色/深色 × 标准/强调/菜单 × 常态/悬停/按下/禁用），各引擎并排 |
| `smoke_widgets.py` | 全组件冒烟：在每个引擎下实例化 tkfluent 的**全部组件**并强制走一遍绘制/主题/悬停/按压流程 |
| `check_canvas_refs.py` | 画布图片保活：同一画布画 5 张图后强制 GC，5 张都必须还在（验证"画面变空白"缺陷已修）；以及 `FluImage` 可正常构造 |
| `check_main.py` | 命令行入口：`--list-engines` / `--help` / 非法引擎的退出码 / `resolve_renderer` 的各分支，以及**逐引擎跑 `--check`** |
| `check_docs.py` | 构建两个项目的文档站（`mkdocs build --strict`），把 nav 引用缺失、正文死链、docstring 无法解析等问题挡在 CI 里 |
| `bench_render.py` | 性能基准，可 `--engine` / `--renderer` 选择引擎，`--installed` 用 site-packages 里的旧版跑基线 |
| `report.py` / `report_before_after.py` | 把上面的 JSON 结果汇总成对比表 |
| `visual_demo.py` | 摆一个真实界面并截图（需要可用的桌面会话，无人值守环境下可能抓到别的窗口） |

!!! note "文档构建依赖"
    `check_docs.py` 需要 mkdocs 工具链。未安装时会**跳过并提示**，
    而不是判定失败。安装：`pip install -r docs/requirements.txt`

## 代表性结果

性能（120×32 圆角矩形，单位 ms）：

| 场景 | 优化前 | 仅修基础设施 | + skia 引擎 |
| --- | --- | --- | --- |
| 圆角矩形（尺寸各异） | 13.81 | 4.94 | **1.26** |
| 圆角矩形（参数相同） | 10.80 | 4.33 | **0.02** |
| 按钮重绘 | 5.95 | 2.86 | **0.15** |
| 按钮 hover 往返 | 13.65 | 6.08 | **0.26** |
| 20 个按钮批量重绘 | 139.9 | 110.4 | **2.93** |

资源泄漏（20 个按钮 + 1 个窗口）：

| | 旧版 | 现在 |
| --- | --- | --- |
| 新增临时文件 | **80 个** | 0 |
| 新增文件描述符 | **80 个** | 0 |
| 5 张图片强制 GC 后存活 | **1/5** | 5/5 |

保真度：24 个按钮状态下，各栅格引擎与 `tksvg` 参照的平均像素差都 **≤ 5.7/255**，
绝大多数状态低于 2。

## `_out/`

脚本生成的图片都落在这里（对比拼图、画廊、各引擎的图元样张），
已加入 `.gitignore`。

## 文档站也在回归里

`check_docs.py` 用 `mkdocs build --strict` 构建 tkdeft 与 tkfluent 两个文档站。
`--strict` 会把**任何** WARNING 当成错误，所以下列问题都会被挡下来：

* `mkdocs.yml` 的 nav 引用了不存在的文件（新增/改名页面后最容易踩）
* 正文里的相对链接指向不存在的页面
* `:::` 指令写错了模块路径，或某个模块导入失败
* docstring 的 `Returns:` 段落格式不规范（缺类型注解等）

新增文档页面后，记得同步 `docs/mkdocs.yml` 的 nav 并跑一次这个检查。
