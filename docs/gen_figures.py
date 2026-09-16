"""生成文档站用的插图，输出到 ``docs/docs/assets/``。

插图全部**由真实的绘制路径产生**（不是画上去的示意图）：栅格部分直接调用
各引擎的 ``render_*``，SVG 部分用 :class:`tkdeft.windows.draw.DSvgDraw` 生成
SVG 后再用 tksvg / Wand 栅格化，画廊截图则复用 ``benchmarks/visual_demo.py``
的 Win32 ``PrintWindow`` 抓图。

用法（在 ``docs/`` 目录下）::

    python gen_figures.py            # 只列出会生成哪些图
    python gen_figures.py --write    # 实际写入 docs/docs/assets/
    python gen_figures.py --write --only engines-compare   # 只生成一张

生成完请顺手跑一次 ``python benchmarks/check_docs.py``，确认文档站仍然
``--strict`` 无警告（图片缺失会被 mkdocs 当成断链）。
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "docs", "assets")
BENCH = os.path.join(REPO, "benchmarks")
DIAGRAMS = os.path.join(HERE, "diagrams")

#: 渲染流程图用的浏览器（mermaid-cli 走 Puppeteer，用系统已有的即可，
#: 不用额外下载 Chromium）
BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
)

# ---------------------------------------------------------------- 调色板
BG = "#f3f3f3"          # 画布底色（浅色 Fluent 背景）
CARD = "#ffffff"
LINE = "#e0e0e0"
TEXT = "#1b1b1b"
MUTED = "#616161"
ACCENT = "#005fb8"
WARN = "#c42b1c"

FONTS = (
    r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑（含中文）
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def _font(size: int):
    """取一个支持中文的字体；找不到就退回 Pillow 内置位图字体。"""
    from PIL import ImageFont

    for path in FONTS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- 规格样本
def _samples():
    """文档里统一使用的一组绘制规格（与 tkfluent 的实际参数接近）。"""
    from tkdeft.engines import RoundRectSpec, ThumbSpec, TrackSpec

    return [
        (
            "roundrect",
            "圆角矩形",
            RoundRectSpec(
                width=120, height=32, rx=6,
                fill="#ffffff", outline="#000000",
                outline_opacity=0.25, outline_width=1,
            ),
        ),
        (
            "pill",
            "胶囊（rx=16）",
            RoundRectSpec(width=96, height=32, rx=16, fill=ACCENT),
        ),
        (
            "gradient",
            "渐变描边",
            RoundRectSpec(
                width=120, height=32, rx=6,
                fill="#ffffff", outline="#f0f0f0", outline2="#9a9a9a",
                outline_opacity=1, outline2_opacity=1, outline_width=1,
                gradient_stop1=0.0, gradient_stop2=1.0,
            ),
        ),
        (
            "thumb",
            "滑块把手",
            ThumbSpec(
                width=28, height=28, r1=14, r2=8,
                fill="#ffffff", fill_opacity=1,
                outline="#d0d0d0", outline2="#8a8a8a",
                outline_opacity=1, outline2_opacity=1,
                inner_fill=ACCENT, inner_fill_opacity=1,
            ),
        ),
        (
            "track",
            "进度条槽",
            TrackSpec(
                width=120, height=6, width2=72, radius=3,
                track_fill=ACCENT, rail_fill="#d6d6d6",
            ),
        ),
    ]


# ---------------------------------------------------------------- 渲染
class _Renderer:
    """按引擎渲染规格样本；tksvg / wand 走真实的 SVG + 栅格化路径。"""

    def __init__(self) -> None:
        import tkinter

        from tkdeft.engines import get_engine, list_engines, set_engine
        from tkdeft.windows.draw import DSvgDraw

        self._get_engine = get_engine
        self._set_engine = set_engine
        self._available = list_engines()
        self._tmp = tempfile.mkdtemp(prefix="tkdeft-figures-")
        self._counter = 0

        # DSvgDraw 需要一个 master 才能建 PhotoImage；这里用隐藏的 Tk 根窗口
        self.root = tkinter.Tk()
        self.root.withdraw()
        self.draw = DSvgDraw()
        self.draw.master = self.root

    def close(self) -> None:
        try:
            self.draw.cleanup()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # -- 单张图 ---------------------------------------------------------
    def render(self, engine_name: str, sample) -> "object":
        """返回该引擎渲染该样本得到的 ``PIL.Image``（RGBA）。"""
        from PIL import Image

        self._set_engine(engine_name)
        _label, _title, spec = sample
        kind = spec.kind          # "roundrect" / "track" / "thumb"

        if engine_name in ("tksvg", "wand"):
            image = self._render_svg(kind, spec)
        else:
            image = self._get_engine().render(spec)

        image = image.convert("RGBA")
        # 统一成规格声明的尺寸：tksvg 偶发少 1px（119×31），
        # 直接拼图会让对照列大小不一，这里居中垫到目标尺寸
        canvas = Image.new("RGBA", (int(spec.width), int(spec.height)), (0, 0, 0, 0))
        canvas.alpha_composite(
            image,
            (
                max(0, (canvas.width - image.width) // 2),
                max(0, (canvas.height - image.height) // 2),
            ),
        )
        return canvas

    def _render_svg(self, kind, spec):
        """用 DSvgDraw 生成 SVG，再交给当前（SVG 系）引擎栅格化。"""
        from PIL import Image

        draw = self.draw
        if kind == "roundrect":
            path = draw.create_roundrect(
                0, 0, spec.width, spec.height, spec.rx, spec.effective_ry,
                fill=spec.fill,
                fill_opacity=spec.fill_opacity,
                outline=spec.outline,
                outline2=spec.outline2,
                outline_opacity=spec.outline_opacity,
                outline2_opacity=spec.outline2_opacity,
                width=spec.outline_width,
                gradient_stop1=spec.gradient_stop1,
                gradient_stop2=spec.gradient_stop2,
            )
        elif kind == "track":
            path = draw.create_track(
                spec.width, spec.height, spec.width2,
                radius=spec.radius,
                track_fill=spec.track_fill,
                track_opacity=spec.track_opacity,
                rail_fill=spec.rail_fill,
                rail_opacity=spec.rail_opacity,
            )
        else:
            path = draw.create_thumb(
                spec.width, spec.height, spec.r1, spec.r2,
                fill=spec.fill, fill_opacity=spec.fill_opacity,
                outline=spec.outline, outline_opacity=spec.outline_opacity,
                outline2=spec.outline2, outline2_opacity=spec.outline2_opacity,
                inner_fill=spec.inner_fill, inner_fill_opacity=spec.inner_fill_opacity,
            )

        self._counter += 1
        png = os.path.join(self._tmp, f"svg-{self._counter}.png")
        photo = draw.create_svg_image(path)
        photo.write(png, format="png")   # Tk 的 PhotoImage 直接落盘 PNG
        return Image.open(png)


# ---------------------------------------------------------------- 画布工具
def _new(width: int, height: int, color=BG):
    from PIL import Image

    return Image.new("RGB", (width, height), color)


def _draw_text(draw, xy, text, font, fill=TEXT, anchor="la"):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _centered(image, box_w, box_h):
    """把一张图居中贴到给定尺寸的透明画布上。"""
    from PIL import Image

    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    canvas.alpha_composite(
        image,
        (max(0, (box_w - image.width) // 2), max(0, (box_h - image.height) // 2)),
    )
    return canvas


def _zoom(image, factor: int):
    from PIL import Image

    return image.resize(
        (image.width * factor, image.height * factor), Image.NEAREST
    )


# ---------------------------------------------------------------- 图 1：引擎对照
def figure_engines_compare(renderer: _Renderer):
    """同一份 spec，各引擎渲染结果对照。"""
    from PIL import ImageDraw

    engines = [e for e in ("tksvg", "wand", "skia", "pillow", "cairo")
               if renderer._available.get(e)]
    samples = _samples()

    cell_w, cell_h = 168, 52
    label_w, head_h, pad = 116, 34, 14
    width = pad + label_w + len(engines) * cell_w + pad
    height = pad + head_h + len(samples) * cell_h + pad + 26

    canvas = _new(width, height)
    draw = ImageDraw.Draw(canvas)
    f_head = _font(15)
    f_label = _font(14)
    f_note = _font(12)

    for col, engine in enumerate(engines):
        x = pad + label_w + col * cell_w
        _draw_text(draw, (x + cell_w // 2, pad + 8), engine, f_head,
                   ACCENT if engine == "tksvg" else TEXT, anchor="ma")

    for row, sample in enumerate(samples):
        y = pad + head_h + row * cell_h
        if row % 2 == 0:
            draw.rectangle(
                (pad, y, width - pad, y + cell_h), fill="#fafafa"
            )
        _draw_text(draw, (pad + 4, y + cell_h // 2), sample[1], f_label,
                   MUTED, anchor="lm")
        for col, engine in enumerate(engines):
            x = pad + label_w + col * cell_w
            cell = _centered(renderer.render(engine, sample), cell_w - 20, cell_h - 14)
            canvas.paste(cell, (x + 10, y + 7), cell)

    _draw_text(
        draw,
        (pad, height - pad - 16),
        "同一份绘制规格（RoundRectSpec / ThumbSpec / TrackSpec）交给各引擎的结果"
        "　·　tksvg 是默认引擎，也是保真度比对里的参照",
        f_note, MUTED,
    )
    return canvas


# ---------------------------------------------------------------- 图 2：三种图元
def figure_three_primitives(renderer: _Renderer):
    """三种图元：真实渲染（放大）+ 关键字段，用来解释"绘制规格"。"""
    from PIL import ImageDraw

    engine = "skia" if renderer._available.get("skia") else "pillow"
    cards = [
        ("RoundRectSpec", "kind='roundrect'　按钮 / 面板 / 输入框背景",
         ("width=120  height=32  rx=6",
          "fill='#ffffff'",
          "outline='#000000'  outline_opacity=0.25"),
         renderer.render(engine, _samples()[0])),
        ("TrackSpec", "kind='track'　滑块、滚动条的进度条槽",
         ("width=120  height=6  width2=72",
          "radius=3",
          "track_fill='#005fb8'  rail_fill='#d6d6d6'"),
         renderer.render(engine, _samples()[4])),
        ("ThumbSpec", "kind='thumb'　滑块的圆形把手",
         ("width=28  height=28  r1=14  r2=8",
          "outline→outline2 竖直渐变（伪阴影）",
          "inner_fill='#005fb8'"),
         renderer.render(engine, _samples()[3])),
    ]

    card_w, card_h, gap, pad = 390, 246, 16, 16
    width = pad * 2 + card_w * 3 + gap * 2
    height = pad * 2 + card_h

    canvas = _new(width, height)
    draw = ImageDraw.Draw(canvas)
    f_title, f_sub = _font(17), _font(12)
    f_body = _font(12)

    stage_w, stage_h = card_w - 32, 96
    for index, (name, subtitle, lines, image) in enumerate(cards):
        x = pad + index * (card_w + gap)
        draw.rounded_rectangle(
            (x, pad, x + card_w, pad + card_h), radius=10,
            fill=CARD, outline=LINE, width=1,
        )
        _draw_text(draw, (x + 16, pad + 14), name, f_title, ACCENT)
        _draw_text(draw, (x + 16, pad + 42), subtitle, f_sub, MUTED)

        # 展示台：把真实渲染按"能放下就尽量放大"的整数倍贴上去
        stage = (x + 16, pad + 68, x + 16 + stage_w, pad + 68 + stage_h)
        draw.rounded_rectangle(stage, radius=8, fill="#fafafa", outline=LINE, width=1)
        zoom = max(1, min(3, stage_w // max(1, image.width),
                          stage_h // max(1, image.height)))
        preview = _centered(_zoom(image, zoom), stage_w - 12, stage_h - 12)
        canvas.paste(preview, (stage[0] + 6, stage[1] + 6), preview)

        for line_index, line in enumerate(lines):
            _draw_text(
                draw,
                (x + 16, pad + 176 + line_index * 19),
                line, f_body, MUTED if line_index else TEXT,
            )

    return canvas


# ---------------------------------------------------------------- 图 3：描边内缩
def figure_stroke_inset(renderer: _Renderer):
    """示意图：描边居中 ⇒ 几何必须内缩半个线宽。

    .. note::
       这里画的是**示意图**而不是"旧/新截图对比"。实测过：本机 tksvg 版本下
       旧写法（``translate(0.5,0.5)`` + 整宽整高）与新写法的边缘像素统计几乎
       一致，拿截图对比反而会误导读者。真正有用的是规则本身——
       SVG 的描边以路径为中心线，外半侧一旦越过画布边界就被裁掉。
       为了看得见，图里把 ``stroke_width`` 夸大成 16px（默认是 1px）。
    """
    from PIL import ImageDraw

    stroke = 16          # 夸大后的线宽（真实默认 1px，1px 在示意图里看不见）
    inset = stroke // 2
    box = 148
    band = inset + 4     # 画布外留出的"会被裁掉"的带
    panel = box + band * 2
    pad, head, gap = 26, 92, 66

    canvas_w = pad * 2 + panel * 2 + gap
    canvas_h = pad + head + panel + 92
    canvas = _new(canvas_w, canvas_h)
    draw = ImageDraw.Draw(canvas)
    f_title, f_body, f_note = _font(16), _font(12), _font(12)

    def _hatch(canvas_box):
        """在被裁掉的带子里画斜纹（只在画布之外那一圈，且不越过本面板）。"""
        from PIL import Image

        x0, y0, x1, y1 = canvas_box
        loose = (x0 - band, y0 - band, x1 + band, y1 + band)
        size = (loose[2] - loose[0], loose[3] - loose[1])
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        for start in range(-size[1], size[0], 9):
            layer_draw.line(
                (start, 0, start + size[1], size[1]),
                fill=(196, 43, 28, 110), width=1,
            )
        # 挖掉画布内部：斜纹只保留"落在画布之外"的那一圈
        layer_draw.rectangle(
            (band, band, band + box, band + box), fill=(0, 0, 0, 0)
        )
        canvas.paste(layer, (loose[0], loose[1]), layer)

    for index, wrong in enumerate((True, False)):
        left = pad + index * (panel + gap)
        top = pad + head
        canvas_box = (left + band, top + band, left + band + box, top + band + box)

        draw.rectangle(canvas_box, fill="#ffffff")

        radius = 18
        if wrong:
            # 只有"错误"这一侧才需要画出画布之外的区域（那正是被裁掉的部分）
            draw.rectangle(
                (canvas_box[0] - band, canvas_box[1] - band,
                 canvas_box[2] + band, canvas_box[3] + band),
                outline="#cfcfcf", width=1,
            )
            # 描边以画布边界为中心线：外侧那半个线宽落在画布之外
            draw.rounded_rectangle(canvas_box, radius=radius,
                                   outline="#f2b6ae", width=stroke)
            _hatch(canvas_box)
            draw.rounded_rectangle(canvas_box, radius=radius,
                                   outline=WARN, width=1)     # 路径中心线
        else:
            path_box = (canvas_box[0] + inset, canvas_box[1] + inset,
                        canvas_box[2] - inset, canvas_box[3] - inset)
            draw.rounded_rectangle(path_box, radius=radius, outline=ACCENT, width=stroke)
            draw.rounded_rectangle(canvas_box, radius=radius,
                                   outline="#b9d3ee", width=1)  # 画布边界

        _draw_text(draw, (left, pad + 4),
                   "未内缩（错误）" if wrong else "内缩半个线宽（正确）",
                   f_title, WARN if wrong else ACCENT)
        _draw_text(draw, (left, pad + 32),
                   "几何铺满 0..w / 0..h" if wrong else "insert += 8、size -= 16",
                   f_body, MUTED)
        _draw_text(draw, (left, pad + 52),
                   "中心线压在画布边界上" if wrong else "中心线内移 8px",
                   f_body, MUTED)
        _draw_text(draw,
                   (left, top + panel + 10),
                   "外侧半个线宽被裁掉（斜纹）" if wrong else "描边外沿正好贴边",
                   f_body, WARN if wrong else ACCENT)

    _draw_text(draw, (pad, canvas_h - 60),
               "SVG 的描边以路径为中心线，向两侧各画半个线宽。", f_note, MUTED)
    _draw_text(draw, (pad, canvas_h - 40),
               "tkdeft.svg.roundrect_geometry() 统一做这个内缩，", f_note, MUTED)
    _draw_text(draw, (pad, canvas_h - 20),
               "SVG 引擎与栅格引擎因此共用同一套几何（示意图，线宽已放大到 16px）",
               f_note, MUTED)
    return canvas


# ---------------------------------------------------------------- 图 4：性能
def figure_perf_bars():
    """从 benchmarks/result_r*.json 汇总各引擎的端到端耗时（对数坐标）。"""
    from PIL import ImageDraw

    from tkdeft.engines import RENDERER_INDEX

    files = sorted(glob.glob(os.path.join(BENCH, "result_r*.json")))
    runs = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        index = data.get("renderer")
        name = RENDERER_INDEX.get(index, data.get("label", str(index)))
        runs.append((name, data))
    if not runs:
        return None

    # 画布里最关心、差距最直观的四项
    metrics = [
        ("roundrect_same", "同规格圆角矩形（命中缓存）"),
        ("button_draw", "按钮重绘"),
        ("button_hover", "按钮 hover 往返"),
        ("batch_20", "20 个按钮批量重绘"),
    ]
    runs = [(name, data) for name, data in runs
            if all(m in data for m, _ in metrics)]
    if not runs:
        return None

    base = next((data for name, data in runs if name == "tksvg"), None)
    colors = [ACCENT, "#0f7b0f", "#8a5a00", "#7a3ea1", "#c42b1c"]

    bar_h, bar_gap = 9, 2
    block_head, block_gap = 22, 16
    pad, chart_w, value_w = 22, 470, 120
    head = 78
    block_h = block_head + len(runs) * (bar_h + bar_gap)
    width = pad * 2 + chart_w + value_w
    height = pad + head + len(metrics) * (block_h + block_gap) + 58

    canvas = _new(width, height)
    draw = ImageDraw.Draw(canvas)
    f_title, f_metric, f_val, f_leg = _font(16), _font(13), _font(12), _font(12)

    _draw_text(draw, (pad, pad), "各引擎端到端耗时（毫秒，对数坐标）", f_title)

    # 图例
    lx = pad
    for index, (name, _data) in enumerate(runs):
        col = colors[index % len(colors)]
        draw.rectangle((lx, pad + 32, lx + 10, pad + 42), fill=col)
        _draw_text(draw, (lx + 15, pad + 32), name, f_leg, MUTED)
        lx += 15 + int(draw.textlength(name, font=f_leg)) + 14

    values = [
        data[m]["mean_ms"] for _n, data in runs for m, _ in metrics if m in data
    ]
    low = max(0.005, min(values) / 1.6)
    high = max(values) * 1.6
    span = math.log10(high) - math.log10(low)

    def _x(value):
        ratio = (math.log10(max(value, low)) - math.log10(low)) / span
        return pad + int(ratio * chart_w)

    # 网格（1-2-5 刻度）
    ticks = []
    decade = 10 ** math.floor(math.log10(low))
    while decade <= high:
        for mult in (1, 2, 5):
            tick = decade * mult
            if low <= tick <= high:
                ticks.append(tick)
        decade *= 10

    chart_top = pad + head - 16
    chart_bottom = height - 52
    for tick in ticks:
        x = _x(tick)
        draw.line((x, chart_top, x, chart_bottom), fill="#e8e8e8")
        _draw_text(draw, (x, chart_bottom + 6), f"{tick:g}", f_leg, MUTED, anchor="ma")

    _draw_text(draw, (pad + chart_w + 14, pad + 32), "均值", f_leg, MUTED)

    for row, (metric, title) in enumerate(metrics):
        y = pad + head + row * (block_h + block_gap)
        _draw_text(draw, (pad, y), title, f_metric, TEXT)
        for index, (name, data) in enumerate(runs):
            value = (data.get(metric) or {}).get("mean_ms")
            if not value:
                continue
            bar_y = y + block_head + index * (bar_h + bar_gap)
            x0, x1 = _x(low), _x(value)
            draw.rectangle(
                (x0, bar_y, max(x1, x0 + 2), bar_y + bar_h - 2),
                fill=colors[index % len(colors)],
            )
            # 数值统一放在右侧一列，避免短柱的标签叠在一起
            _draw_text(
                draw, (pad + chart_w + 14 + value_w - 20, bar_y),
                f"{value:g} ms", f_val, MUTED, anchor="ra",
            )

    if base:
        _draw_text(
            draw, (pad, height - 22),
            "数据来自 benchmarks/result_r*.json（python benchmarks/bench_render.py --repeat 30）；"
            "柱长为对数刻度，用于比较量级",
            f_leg, MUTED,
        )
    return canvas


# ---------------------------------------------------------------- 图 5：画廊截图
def figure_gallery(mode: str, out_name: str):
    """整窗截图：复用 benchmarks/visual_demo.py 的 Win32 PrintWindow。"""
    if BENCH not in sys.path:
        sys.path.insert(0, BENCH)
    try:
        import tkflu
        from tkflu.__main__ import build_gallery
        from visual_demo import grab
    except Exception as exc:      # 没装 tkfluent 就跳过（图仍然留在仓库里）
        print(f"  跳过 {out_name}：{type(exc).__name__}: {exc}")
        return None

    tkflu.set_renderer("tksvg")
    root = tkflu.FluWindow(mode=mode)
    root.title(f"tkfluent 组件画廊 · {mode}")
    root.geometry("640x680+80+40")
    build_gallery(root, mode=mode)
    root.update()
    time.sleep(0.4)

    path = os.path.join(ASSETS, out_name)
    note = grab(root, path)
    root.destroy()
    print(f"  {note} -> assets/{out_name}")
    return path


# ---------------------------------------------------------------- 图 6：流程图
def figure_diagram(source: str, out_name: str, scale: int = 2):
    """把 ``docs/diagrams/<source>.mmd`` 渲染成 ``assets/<out_name>``。

    为什么预渲染而不是在页面里写 ```` ```mermaid ````：Material 的 mermaid 支持是
    **运行时从 unpkg CDN 拉取脚本**的，而本站启用了 ``offline`` 插件——
    离线打开时图就会消失。这里改成生成时渲染成图片，离线也能看。

    需要 Node（``npx``）与一个 Chromium 系浏览器；两者都没有时**跳过**，
    仓库里已提交的图片不受影响。

    :param source: ``docs/diagrams/`` 下的文件名（不含扩展名）
    :param out_name: 输出到 ``docs/docs/assets/`` 的文件名
    :param scale: 分辨率倍率
    """
    import shutil
    import subprocess

    src = os.path.join(DIAGRAMS, source + ".mmd")
    if not os.path.exists(src):
        print(f"  跳过 {out_name}：找不到 {src}")
        return None
    if shutil.which("npx") is None:
        print(f"  跳过 {out_name}：没有 npx（装了 Node 就能重新生成）")
        return None

    env = dict(os.environ)
    browser = next((path for path in BROWSERS if os.path.exists(path)), None)
    if browser:
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", browser)

    dst = os.path.join(ASSETS, out_name)
    cmd = ["npx", "--yes", "@mermaid-js/mermaid-cli@11",
           "-i", src, "-o", dst, "-b", "white", "-s", str(scale)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, shell=True)
    if result.returncode != 0 or not os.path.exists(dst):
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        print(f"  跳过 {out_name}：mermaid-cli 失败 {tail}")
        return None
    print(f"  {source}.mmd -> assets/{out_name}")
    return dst


# ---------------------------------------------------------------- 入口
FIGURES = {
    "engines-compare": "engines-compare.png · 同一份 spec 在各引擎下的结果",
    "three-primitives": "three-primitives.png · 三种图元与关键字段",
    "stroke-inset": "stroke-inset.png · 描边内缩前后（四边描边完整性）",
    "perf-bars": "perf-bars.png · 各引擎端到端耗时",
    "gallery-light": "gallery-light.png · 画廊截图（浅色）",
    "gallery-dark": "gallery-dark.png · 画廊截图（深色）",
    "architecture": "architecture.png · 架构总览（diagrams/architecture.mmd）",
    "engine-paths": "engine-paths.png · 两条绘制路径（diagrams/engine-paths.mmd）",
    "render-pipeline": "render-pipeline.png · 一次重绘的时序（diagrams/render-pipeline.mmd）",
    "cache": "cache.png · 缓存策略（diagrams/cache.mmd）",
    "click-flow": "click-flow.png · 点击事件的时序（diagrams/click-flow.mmd）",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成 tkdeft 文档站插图")
    parser.add_argument("--write", action="store_true", help="实际写入文件")
    parser.add_argument("--only", action="append", default=None,
                        help="只生成指定插图（可重复）")
    args = parser.parse_args(argv)

    wanted = args.only or list(FIGURES)
    unknown = [name for name in wanted if name not in FIGURES]
    if unknown:
        parser.error(f"未知的插图 {unknown}；可用：{sorted(FIGURES)}")

    print("将生成：")
    for name in wanted:
        print(f"  - {FIGURES[name]}")
    if not args.write:
        print("\n（加 --write 才会真正写入 docs/docs/assets/）")
        return 0

    os.makedirs(ASSETS, exist_ok=True)
    renderer = _Renderer()
    try:
        producers = {
            "engines-compare": lambda: _save(figure_engines_compare(renderer), "engines-compare.png"),
            "three-primitives": lambda: _save(figure_three_primitives(renderer), "three-primitives.png"),
            "stroke-inset": lambda: _save(figure_stroke_inset(renderer), "stroke-inset.png"),
            "perf-bars": lambda: _save(figure_perf_bars(), "perf-bars.png"),
            "gallery-light": lambda: figure_gallery("light", "gallery-light.png"),
            "gallery-dark": lambda: figure_gallery("dark", "gallery-dark.png"),
            "architecture": lambda: figure_diagram("architecture", "architecture.png"),
            "engine-paths": lambda: figure_diagram("engine-paths", "engine-paths.png"),
            "render-pipeline": lambda: figure_diagram("render-pipeline", "render-pipeline.png"),
            "cache": lambda: figure_diagram("cache", "cache.png"),
            "click-flow": lambda: figure_diagram("click-flow", "click-flow.png"),
        }
        for name in wanted:
            producers[name]()
    finally:
        renderer.close()
    return 0


def _save(image, name: str):
    if image is None:
        print(f"  跳过 {name}：缺少数据")
        return None
    path = os.path.join(ASSETS, name)
    image.save(path)
    print(f"  {image.width}x{image.height} -> assets/{name}")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
