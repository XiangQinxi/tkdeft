class DDraw(object):
    def create_tksvg_image(self, path):
        from tksvg import SvgImage
        tkimage = SvgImage(file=path)
        return tkimage

    def create_tk_image(self, path):
        from PIL.Image import open
        from PIL.ImageTk import PhotoImage
        image = open(path)
        tkimage = PhotoImage(image=image)
        return tkimage

    """def svg_to_png(self, svgpath):
        import cairosvg
        from tempfile import mkstemp
        _, path = mkstemp(suffix=".png", prefix="tkdeft.temp.")
        cairosvg.svg2png(file_obj=open(svgpath), write_to=path)
        return path
    """


class DSvgDraw(DDraw):
    def create_drawing(self, width, height, temppath=None):
        if temppath:
            path = temppath
        else:
            from tempfile import mkstemp
            _, path = mkstemp(suffix=".svg", prefix="tkdeft.temp.")
        import svgwrite
        dwg = svgwrite.Drawing(path, width=width, height=height)

        return path, dwg
