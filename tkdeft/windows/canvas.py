from tkinter import Canvas


class DCanvas(Canvas):
    from .draw import DSvgDraw

    draw = DSvgDraw

    def __init__(self, *args, border=0, highlightthickness=0, **kwargs):
        super().__init__(*args, border=border, highlightthickness=0, **kwargs)

        self.svgdraw = self.draw()

    """def create_cairo_icon(self, x1, y1, x2, y2):
        self.init_cairodraw()
        self._img = self.cairodraw.create_cairo(x2-x1, y2-y1)
        self._tkimg = self.cairodraw.create_tksvg_image(self._img)
        return self.create_image(x1, y1, anchor="nw", image=self._tkimg)
    """

    def create_round_rectangle(self, x1, y1, x2, y2, r1, r2=None, fill="transparent", outline="black", width=1):
        self._img = self.svgdraw.create_roundrect(x1, y1, x2, y2, r1, r2, fill=fill, outline=outline, width=width)
        self._tkimg = self.svgdraw.create_tksvg_image(self._img)
        return self.create_image(x1, y1, anchor="nw", image=self._tkimg)

    create_roundrect = create_round_rectangle
