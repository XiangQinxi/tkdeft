# 文档怎么维护

面向**改这个文档站的人**（不是给读者看的）。站点本身在 [`docs/`](docs/) 下，
用 mkdocs + Material + mkdocstrings 构建。

## 目录结构

```
docs/
├── mkdocs.yml            站点配置（nav / 插件 / 扩展）
├── requirements.txt      文档工具链版本（与 tkfluent 保持一致）
├── gen_api_pages.py      生成 api/*.md（每个模块一个页面）
├── gen_figures.py        生成 docs/assets/*.png（插图）
├── diagrams/*.mmd        流程图源码（mermaid），由 gen_figures.py 渲染
└── docs/                 真正的站点内容
    ├── index.md          主页
    ├── getstarted/       安装 / 快速上手 / 概念与架构
    ├── usage/            指南总览 / 绘制引擎 / 自定义组件 / 回归与性能 / FAQ / 升级
    ├── api/              由 gen_api_pages.py + 源码文档字符串生成
    ├── assets/           插图（提交进仓库）
    ├── template/ blog/   模板说明与博客
    └── stylesheets/extra.css
```

## 改内容

| 想改什么 | 改哪里 |
| --- | --- |
| 某段说明文字、示例代码 | 对应的 `.md`（`docs/docs/**`） |
| 某个 API 的说明 | **改源码的文档字符串**，然后重新生成 API 页（见下） |
| 导航顺序、新增页面 | `mkdocs.yml` 的 `nav` |
| 配色、插图样式 | `docs/docs/stylesheets/extra.css` |

## 两个生成脚本

```bash
cd docs

# 新增/改名了公开模块后，重新生成 API 页
python gen_api_pages.py            # 预览会写哪些
python gen_api_pages.py --write    # 实际写

# 重新生成插图（需要能起 Tk 窗口；流程图还需要 Node/npx）
python gen_figures.py              # 预览会生成哪些
python gen_figures.py --write
python gen_figures.py --write --only engines-compare   # 只生成一张
```

### 插图

`gen_figures.py` 里的插图都是**真实渲染**出来的，不是画上去的示意图：

| 插图 | 怎么来的 |
| --- | --- |
| `engines-compare.png` | 各引擎渲染同一组 `RoundRectSpec` / `TrackSpec` / `ThumbSpec` |
| `three-primitives.png` | 同上，放大 3 倍并标注关键字段 |
| `stroke-inset.png` | 示意图（线宽放大到 16px 才看得见）；**不是**截图对比，原因见函数注释 |
| `perf-bars.png` | 汇总 `benchmarks/result_r*.json` |
| `gallery-light.png` / `gallery-dark.png` | 起 tkfluent 组件画廊，用 Win32 `PrintWindow` 截整窗 |
| `architecture.png` / `engine-paths.png` / `render-pipeline.png` / `cache.png` / `click-flow.png` | `diagrams/*.mmd` 经 mermaid-cli 渲染 |

!!! warning "流程图为什么是预渲染的图片"
    Material 的 mermaid 支持是**运行时从 unpkg CDN 拉脚本**的，而本站启用了
    `offline` 插件（离线可读）。直接写 ` ```mermaid ` 的话，离线打开就只剩一段
    代码。所以流程图以 `diagrams/*.mmd` 为源、渲染成 PNG 提交进仓库。
    改图流程：改 `.mmd` → `python gen_figures.py --write` → 提交图片。

    流程图渲染需要 Node（`npx`）与一个 Chromium 系浏览器（脚本会自动找 Edge /
    Chrome）。两者都没有时脚本会**跳过**，已提交的图片不受影响。

### 页面里引用插图

用 Material 的 `<figure markdown>` 写法，图注会跟着样式走：

```markdown
<figure markdown>
  ![说明](../assets/xxx.png)
  <figcaption>图注：写清楚这张图要说明什么</figcaption>
</figure>
```

`assets/` 与 `usage/` 是同级目录，注意相对路径（`usage/` 下的页面要用 `../assets/`）。

## 本地预览与构建

```bash
cd docs
mkdocs serve -f mkdocs.yml            # 本地预览（改完自动刷新）
```

!!! danger "不要直接 `mkdocs build`"
    `docs/site` 是**已提交**的构建产物，直接 `mkdocs build` 会把它覆盖掉。
    要构建就用临时目录：

    ```bash
    mkdocs build --strict --site-dir /tmp/tkdeft-docs
    ```

## 提交前的检查

```bash
cd ..                                  # 回到仓库根目录
python benchmarks/check_docs.py        # 两个文档站都构建一遍（--strict）
python benchmarks/check_docs.py tkdeft # 只构建 tkdeft
```

`--strict` 会把 WARNING 当 ERROR，能挡下：

* nav 里引用了不存在的文件；
* 正文里的相对链接 / 图片路径写错；
* mkdocstrings 解析不了某段文档字符串。

锚点（`#xxx`）也已经在 `mkdocs.yml` 里调成 `warn`。**中文标题的锚点会被
slugify 成 `#_1` 这类**，所以要链接某个小节时，请显式写一个稳定的 id：

```markdown
## 缓存 { #cache }
```

然后 `[缓存](custom-drawing.md#cache)`。

## 新增一个页面

1. 在 `docs/docs/` 下建 `.md`，第一行是 `# 标题`；
2. 在 `mkdocs.yml` 的 `nav` 里登记（**没登记就不会进站**）；
3. 如果它是新的公开模块，跑一次 `python gen_api_pages.py --write`；
4. `python benchmarks/check_docs.py tkdeft` 确认零警告。
