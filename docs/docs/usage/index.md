# 指南总览

`tkdeft` 不带具体组件——它提供的是"把矢量图形变成 Tkinter 控件"的零件。
下面五页覆盖了从入门到排查的全部内容；如果你是第一次来，按顺序读前三页即可。

## 从零开始

| 页面 | 讲什么 | 适合谁 |
| --- | --- | --- |
| [安装](../getstarted/install.md) | 环境要求、可选引擎、验证安装、editable 开发 | 还没装好的人 |
| [快速上手](../getstarted/quickstart.md) | 五分钟：画图元、换引擎、拿 `PhotoImage`、写一个能点的小控件 | 想马上看到效果的人 |
| [概念与架构](../getstarted/concepts.md) | 规格 / 引擎 / 画布 的关系，一次重绘发生了什么，描边与图片保活的坑 | 想搞清楚"为什么这么设计"的人 |

## 深入使用

### [绘制引擎](custom-drawing.md)

"画什么"和"用什么画"是分开的。这一页讲：

* 5 个内置引擎（`tksvg` / `wand` / `skia` / `pillow` / `cairo`）各自的类型与依赖；
* 怎么切换、怎么查询（`describe_engines()` / `available_engines()` / `engine_index()`）；
* 缓存为什么**刻意不做 LRU 淘汰**，像素预算怎么调；
* 颜色的各种写法（`parse_color`）；
* 怎么自己写一个引擎并注册。

### [自定义组件](custom-widget.md)

用 `DObject` + `DCanvas` + `DSvgDraw` + `DDrawWidget` 搭一个自己的控件：

* `DObject` 的属性接口（`dconfigure` / `dcget` / `dkeys` / `dcopy` …）；
* `DDrawWidget` 的事件 → 状态 → 重绘 骨架；
* 三个统一绘制入口与两个"强制走某条路"的开关；
* 怎么写自己的绘制后端（`create_drawing` / `scratch_path` / `cleanup`）。

### [回归与性能](benchmarks.md)

`benchmarks/` 一身两职：回归套件 + 性能基准。

* `python benchmarks/run_all.py`（9 项）与 `--quick`（8 项）；
* 9 个检查脚本各自覆盖什么；
* 怎么跑单引擎基准、怎么汇总成对比表；
* 两条方法论提醒（测试插 `sys.path`、单次运行测不出泄漏）；
* 新增一个检查的三步。

### [常见问题与排查](faq.md)

13 条真实踩过的坑，每条都是 **症状 / 原因 / 怎么办**：

* 画布上的图片变空白（`PhotoImage` 被 GC）；
* `delete("all")` 把叠加内容删掉；
* `withdraw()` 时量不到尺寸；
* 不要对 root 调 `after_cancel()`（会让 `root.destroy()` 失败）；
* 临时文件与文件描述符、`master` 传错、引擎装了却用不了；
* 为什么截 Tk 窗口不能用 `PIL.ImageGrab`。

### [从 0.2 升级到 0.3](upgrade-0.3.md)

0.3.0 是纯加法升级，没有破坏性改动。这一页给出"值得顺手改的四处"与新老名字对照。

## 参考

* [API 文档](../api/index.md) —— 由源码文档字符串自动生成，覆盖全部公开接口
* [什么是模板](../template/index.md) —— 为什么这个库不直接做成主题库
