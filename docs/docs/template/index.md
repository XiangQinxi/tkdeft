# 什么是模板？

## 一句话

`tkdeft` 是**零件**，不是主题。

我们都知道矢量作图能做出许多高级的效果；但一旦想把它做成"换套配色就能用的主题库"，
就得为每一种组合预先实现一遍，效果实现单一、扩展性差。
所以这里选择另一条路：**只提供把矢量图变成控件的零件**，具体长什么样由你的组件决定。

## 那"模板"指什么

指**照着抄的参考实现**。仓库里这些零件怎么组合成一个真正的组件库，
有一个现成的答案：[tkfluent](https://pypi.org/project/tkfluent) ——
按钮、徽标、输入框、滑块、面板、菜单……都是用 `tkdeft` 的零件搭出来的：

<figure markdown>
  ![组件画廊](../assets/gallery-light.png)
  <figcaption>tkfluent 的组件画廊：每个组件都是"画布 + 绘制规格 + 主题字典"的组合</figcaption>
</figure>

## 从模板到自己的库：四步

### 1. 把设计稿拆成"配色字典"

设计稿里的每个状态（rest / hover / pressed / disabled）都是一组颜色与几何。
把它们写成纯 `dict`，与绘制代码彻底分开：

```python
BUTTON = {
    "light": {
        "rest":  {"back_color": "#ffffff", "border_color": "#000000",
                  "border_opacity": 0.08, "radius": 6,
                  "text_color": "#1b1b1b"},
        "hover": {"back_color": "#f9f9f9", "border_color": "#000000",
                  "border_opacity": 0.12, "radius": 6,
                  "text_color": "#1b1b1b"},
    },
    "dark": { ... },
}
```

### 2. 用绘制规格画出来

组件不再拼 SVG，只描述规格；SVG / 栅格两条路交给引擎：

```python
class MyButtonCanvas(DCanvas):
    def _draw(self, event=None):
        super()._draw(event)
        if not self.winfo_ismapped():
            return
        self.delete("all")
        style = self.attributes[self.interaction_state()]
        self.draw_roundrect(
            0, 0, self.winfo_width(), self.winfo_height(), style["radius"],
            fill=style["back_color"],
            outline=style["border_color"], outline_opacity=style["border_opacity"],
        )
```

### 3. 用 `DDrawWidget` 接事件

`enter` / `button1` / `isfocus` 三个状态位由基类维护，`interaction_state()`
直接给出 `rest` / `hover` / `pressed` / `disabled`，你只管查字典。

### 4. 换主题 = 换字典 + 重绘

把"当前主题"存成一份字典，切换时改指针再 `_draw()` 一遍即可——
绘制层一行都不用动。tkfluent 的 `FluThemeManager` 做的就是这件事。

## 为什么不做成主题库

因为 `svg` 能实现很多漂亮的组件，而我套的模板可能对其它设计起不了太大作用。
所以我把这套设计当作**模板**放在这里，供其它设计者参考使用。
设计来源：<https://pixso.cn/community/file/ItC5JH1TOwj15EeOPcY7LQ?from_share>

## 相关阅读

* [自定义组件](../usage/custom-widget.md) —— 从零写一个组件的完整步骤
* [概念与架构](../getstarted/concepts.md) —— 规格 / 引擎 / 画布的关系
* [tkfluent](https://pypi.org/project/tkfluent) —— 照抄用的参考实现
