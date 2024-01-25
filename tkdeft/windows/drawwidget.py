from .draw import DSvgDraw
from .canvas import DCanvas

from ..object import DObject


class DDrawWidgetDraw(DSvgDraw):
    pass


class DDrawWidgetCanvas(DCanvas):
    def init(self):
        if not hasattr(self, "svgdraw"):
            self.svgdraw = DDrawWidgetDraw()


class DDrawWidget(DDrawWidgetCanvas, DObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from tempfile import mkstemp
        _, self.temppath = mkstemp(suffix=".svg", prefix="tkdeft.temp.")

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

    def _draw(self, event=None):
        self.config(background=self.master.cget("background"))

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
            #self.focus_set()
            self.event_generate("<<Clicked>>")

    def _event_focus_in(self, event=None):
        self.isfocus = True

        self._draw(event)

    def _event_focus_out(self, event=None):
        self.isfocus = False

        self._draw(event)
