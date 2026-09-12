"""可交互的绘制控件基类。

``DDrawWidget`` 是一个"用画布画出来的控件"：它把自身四个临时文件路径
（``temppath`` / ``temppath2`` / ``temppath3`` / ``temppath4``）以 **惰性属性**
的形式暴露出来，兼容既有子类代码。

旧实现在 ``__init__`` 里对这四个路径一律 ``mkstemp()``，且从不关闭返回的 fd：

* 每个控件一创建就 **泄漏 4 个文件描述符**（20 个按钮 = 80 个），
  长跑程序会撞上 Windows 的句柄上限；
* 即使随后改用了 tksvg / skia 引擎，那 4 个临时文件依然躺在地盘上。

现在改为**按需创建**：只有在真正用到某个路径时才建文件，并且每个控件
的生命周期结束时由 :meth:`~tkdeft.windows.draw.DSvgDraw.cleanup` 回收。
"""

from .canvas import DCanvas
from .draw import DSvgDraw

from ..object import DObject


class DDrawWidgetDraw(DSvgDraw):
    pass


class DDrawWidgetCanvas(DCanvas):
    def init(self):
        if not hasattr(self, "svgdraw"):
            self.svgdraw = DDrawWidgetDraw()


class DDrawWidget(DDrawWidgetCanvas, DObject):
    #: 临时文件后缀，与旧实现的四个 mkstemp 调用一一对应
    _TEMP_SUFFIXES = (".svg", ".svg", ".png", ".png")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.enter = False
        self.button1 = False
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
        return self.svgdraw.scratch_path(self._TEMP_SUFFIXES[index - 1], slot=index)

    @property
    def temppath(self) -> str:
        return self._temp_path(1)

    @property
    def temppath2(self) -> str:
        return self._temp_path(2)

    @property
    def temppath3(self) -> str:
        return self._temp_path(3)

    @property
    def temppath4(self) -> str:
        return self._temp_path(4)

    # ------------------------------------------------------------------
    def _init(self):
        pass

    def _draw(self, event=None):
        self.config(background=self.master.cget("background"))
        if not self.winfo_ismapped():
            return

    def _event_configure(self, event=None):
        self._draw(event)

    def _event_enter(self, event=None):
        self.enter = True

        self._draw(event)

    def _event_leave(self, event=None):
        self.enter = False

        self._draw(event)

    def _event_on_button1(self, event=None):
        self.button1 = True

        self._draw(event)

    def _event_off_button1(self, event=None):
        self.button1 = False

        self._draw(event)

        if self.enter:
            # self.focus_set()
            self.event_generate("<<Clicked>>")

    def _event_focus_in(self, event=None):
        self.isfocus = True

        self._draw(event)

    def _event_focus_out(self, event=None):
        self.isfocus = False

        self._draw(event)
