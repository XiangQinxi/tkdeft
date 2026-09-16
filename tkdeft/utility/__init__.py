"""tkdeft 的通用工具（目前主要是字体）。

::

    from tkdeft.utility import SegoeFont

    font = SegoeFont()          # Segoe UI / 10pt / bold
"""

from .fonts import SEGOE_FONT_FILE, SegoeFont, segoe_font, segue_font_file

__all__ = ["SegoeFont", "segue_font_file", "SEGOE_FONT_FILE", "segoe_font"]
