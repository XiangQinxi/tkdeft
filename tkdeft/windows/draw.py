class DDraw(object):
    def create_tksvg_image(self, path):
        from tksvg import SvgImage
        tkimage = SvgImage(file=path)
        return tkimage

    def create_tk_image(self, path):
        from PIL.Image import open
        from PIL.ImageTk import PhotoImage
        image = open(path)
        self.tkimage = PhotoImage(image=image)
        return self.tkimage


class DSvgDraw(DDraw):
    def temppath(self, path=None):
        if not path:
            from tempfile import mkstemp
            _, path = mkstemp(suffix=".svg", prefix="tkdeft.temp.")
        return path

    def create_drawing(self, width, height, temppath=None, **kwargs):
        path = self.temppath(temppath)
        import svgwrite
        dwg = svgwrite.Drawing(path, width=width, height=height, **kwargs)

        return path, dwg
