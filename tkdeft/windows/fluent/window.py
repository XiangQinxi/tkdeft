from tkinter import Tk


class DWindow(Tk):
    def __init__(self, *args, className="tkdeft", **kwargs):
        super().__init__(*args, className=className, **kwargs)
