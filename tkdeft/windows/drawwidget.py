"""可交互的绘制控件基类。

``DDrawWidget`` 是"用画布画出来的控件"的骨架：它把鼠标与焦点事件翻译成
三个状态位，然后调用 :meth:`DDrawWidget._draw` 重绘。

状态位
------
=========== ==================================================
属性         含义
=========== ==================================================
``enter``   鼠标是否停在控件上（``<Enter>`` / ``<Leave>``）
``button1`` 左键是否按下（``<Button-1>`` / ``<ButtonRelease-1>``）
``isfocus`` 是否拥有键盘焦点（``<FocusIn>`` / ``<FocusOut>``）
=========== ==================================================

子类通常只需要覆盖 :meth:`DDrawWidget._draw`，根据这三个状态位选择配色，
然后把图元画到 :class:`~tkdeft.windows.canvas.DCanvas` 上。

事件时序
--------
::

    <Enter>   -> enter=True    -> _draw()
    <Button-1>-> button1=True  -> _draw()
    <ButtonRelease-1> -> button1=False -> _draw() -> 若鼠标仍在控件内，产生 <<Clicked>>
    <Leave>   -> enter=False   -> _draw()
    <Configure>（尺寸变化）    -> _draw()

``<<Clicked>>`` 是"按下并在控件内松开"才会发出的虚拟事件，
常见的接法是::

    widget.bind("<<Clicked>>", lambda event: widget.attributes.command())

临时文件
--------
``DDrawWidget`` 把自身四个临时文件路径（``temppath`` / ``temppath2`` /
``temppath3`` / ``temppath4``）以 **惰性属性** 的形式暴露出来，兼容既有子类代码。

旧实现在 ``__init__`` 里对这四个路径一律 ``mkstemp()``，且从不关闭返回的 fd：

* 每个控件一创建就 **泄漏 4 个文件描述符**（20 个按钮 = 80 个），
  长跑程序会撞上 Windows 的句柄上限；
* 即使随后改用了 tksvg / skia 引擎，那 4 个临时文件依然躺在地盘上。

现在改为**按需创建**：只有在真正用到某个路径时才建文件，并且每个控件
的生命周期结束时由 :meth:`~tkdeft.windows.draw.DSvgDraw.cleanup` 回收。
"""

from __future__ import annotations

from .canvas import DCanvas
from .draw import DSvgDraw

from ..object import DObject

__all__ = ["DDrawWidgetDraw", "DDrawWidgetCanvas", "DDrawWidget"]


class DDrawWidgetDraw(DSvgDraw):
    """交互控件的绘制后端。

    默认与 :class:`~tkdeft.windows.draw.DSvgDraw` 完全一致；留出这个类型
    是为了让子类有一个"控件自己的绘制器"可以挂载（历史上各组件正是这么做的）。
    """


class DDrawWidgetCanvas(DCanvas):
    """交互控件的画布基类。

    比 :class:`~tkdeft.windows.canvas.DCanvas` 多提供 :meth:`init` 钩子，
    用于在子类里替换 :attr:`svgdraw`（绘制后端）。
    """

    def init(self):
        """替换绘制后端（可选钩子）。"""
        if not hasattr(self, "svgdraw"):
            self.svgdraw = DDrawWidgetDraw()


class DDrawWidget(DDrawWidgetCanvas, DObject):
    """带交互状态的画布控件基类。

    继承它就能得到一个"能被点、能 hover、能获得焦点"的画布控件。
    子类需要实现 :meth:`_draw`，并按需读取 :attr:`enter` / :attr:`button1` /
    :attr:`isfocus` 三个状态位。
    """

    #: 临时文件后缀，与旧实现的四个 mkstemp 调用一一对应
    _TEMP_SUFFIXES = (".svg", ".svg", ".png", ".png")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        #: 鼠标是否在控件内
        self.enter = False
        #: 左键是否按下
        self.button1 = False
        #: 是否拥有键盘焦点
        self.isfocus = False

        self._draw(None)

        self.bind("<Configure>", self._event_configure, add="+")
        self.bind("<Enter>", self._event_enter, add="+")
        self.bind("<Leave>", self._event_leave, add="+")
        self.bind("<Button-1>", self._event_on_button1, add="+")
        self.bind("<ButtonRelease-1>", self._event_off_button1, add="+")
        self.bind("<FocusIn>", self._event_focus_in, add="+")
        self.bind("<FocusOut>", self._event_focus_out, add="+")

    # ------------------------------------------------------------------
    # 惰性临时文件路径（兼容旧属性名）
    # ------------------------------------------------------------------
    def _temp_path(self, index: int) -> str:
        """取第 ``index`` 个 scratch 文件路径（按需创建）。"""
        return self.svgdraw.scratch_path(self._TEMP_SUFFIXES[index - 1], slot=index)

    @property
    def temppath(self) -> str:
        """第 1 个临时文件路径（``.svg``）。"""
        return self._temp_path(1)

    @property
    def temppath2(self) -> str:
        """第 2 个临时文件路径（``.svg``）。"""
        return self._temp_path(2)

    @property
    def temppath3(self) -> str:
        """第 3 个临时文件路径（Wand 用的 ``.png``）。"""
        return self._temp_path(3)

    @property
    def temppath4(self) -> str:
        """第 4 个临时文件路径（Wand 用的 ``.png``）。"""
        return self._temp_path(4)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _init(self):
        """初始化钩子（历史 API，子类可覆盖）。"""

    def _draw(self, event=None):
        """把控件画出来。

        :param event: 触发本次重绘的事件；构造与尺寸变化时为 ``None``

        基类的实现只同步一次背景色，并且**在控件还没被映射时直接返回**
        （未映射时 ``winfo_width()`` 恒为 1，画出来也是错的）。
        子类应当先调 ``super()._draw(event)`` 再画自己的内容。
        """
        self.config(background=self.master.cget("background"))
        if not self.winfo_ismapped():
            return

    # ------------------------------------------------------------------
    # 事件 → 状态 → 重绘
    # ------------------------------------------------------------------
    def _event_configure(self, event=None):
        """尺寸/位置变化 → 重绘。"""
        self._draw(event)

    def _event_enter(self, event=None):
        """鼠标进入 → ``enter=True`` → 重绘。"""
        self.enter = True

        self._draw(event)

    def _event_leave(self, event=None):
        """鼠标离开 → ``enter=False`` → 重绘。"""
        self.enter = False

        self._draw(event)

    def _event_on_button1(self, event=None):
        """左键按下 → ``button1=True`` → 重绘。"""
        self.button1 = True

        self._draw(event)

    def _event_off_button1(self, event=None):
        """左键松开 → ``button1=False`` → 重绘 → 在控件内则发出 ``<<Clicked>>``。"""
        self.button1 = False

        self._draw(event)

        if self.enter:
            # self.focus_set()
            self.event_generate("<<Clicked>>")

    def _event_focus_in(self, event=None):
        """获得焦点 → ``isfocus=True`` → 重绘。"""
        self.isfocus = True

        self._draw(event)

    def _event_focus_out(self, event=None):
        """失去焦点 → ``isfocus=False`` → 重绘。"""
        self.isfocus = False

        self._draw(event)

    # ------------------------------------------------------------------
    # 便捷查询
    # ------------------------------------------------------------------
    def interaction_state(self, enabled: bool = True) -> str:
        """把三个状态位归并成一个字符串，便于挑配色。

        :param enabled: 控件是否处于可用状态（``False`` 直接返回 ``"disabled"``）
        :returns: ``"disabled"`` / ``"pressed"`` / ``"hover"`` / ``"rest"``
        """
        if not enabled:
            return "disabled"
        if not self.enter:
            return "rest"
        return "pressed" if self.button1 else "hover"
