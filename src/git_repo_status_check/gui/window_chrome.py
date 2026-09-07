"""The native title bar and frame (Windows DWM), themed to match the palette.

Qt styles the client area only; the caption bar and the 1px frame belong to the window
manager and otherwise render in the user's accent colour. This is a platform API, not Qt,
so it is quarantined here behind one call that is a silent no-op anywhere it cannot work --
a caption in the wrong colour is cosmetic, never a reason to fail to open a window.
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QWidget

from .palette import Palette

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_BORDER_COLOR = 34  # without this the frame keeps the OS accent colour
_DWMWA_CAPTION_COLOR = 35


def apply_dark_titlebar(widget: QWidget, tokens: Palette) -> None:
    """Dark caption and border for ``widget``; call from ``showEvent`` (needs a native handle)."""
    if sys.platform != "win32":
        return
    handle = int(widget.winId())
    if not handle:
        return
    _set_attribute(handle, _DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    _set_attribute(handle, _DWMWA_CAPTION_COLOR, colorref(tokens.window))
    _set_attribute(handle, _DWMWA_BORDER_COLOR, colorref(tokens.border))


def colorref(hex_color: str) -> int:
    """``#RRGGBB`` -> COLORREF, which is ``0x00BBGGRR`` -- byte order reversed."""
    red, green, blue = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    return (blue << 16) | (green << 8) | red


def _set_attribute(handle: int, attribute: int, value: int) -> None:
    try:
        dwmapi = ctypes.windll.dwmapi
        data = ctypes.c_int(value)
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(handle), attribute, ctypes.byref(data), ctypes.sizeof(data)
        )
    except (AttributeError, OSError):
        return  # older Windows, or no DWM: leave the default chrome
