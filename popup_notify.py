import os
import ctypes
from ctypes import wintypes
import tkinter as tk


def _clamp(value, low, high):
    return max(low, min(high, value))


def list_displays() -> list[dict]:
    if os.name != "nt":
        return [{"index": 0, "label": "Display 1 (Primary)", "left": 0, "top": 0, "right": 0, "bottom": 0}]

    displays = []
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(RECT),
        ctypes.c_double,
    )

    def _enum_proc(_hmonitor, _hdc, lprect, _lparam):
        rect = lprect.contents
        displays.append(
            {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
            }
        )
        return 1

    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_enum_proc), 0)

    if not displays:
        return [{"index": 0, "label": "Display 1 (Primary)", "left": 0, "top": 0, "right": 0, "bottom": 0}]

    result = []
    for i, d in enumerate(displays):
        w = d["right"] - d["left"]
        h = d["bottom"] - d["top"]
        label = f"Display {i + 1} ({w}x{h} at {d['left']},{d['top']})"
        result.append({"index": i, "label": label, **d})
    return result


class PopupNotifier:
    def __init__(self, root: tk.Tk, settings_provider=None) -> None:
        self.root = root
        self._settings_provider = settings_provider
        self._window: tk.Toplevel | None = None
        self._hide_after_id = None

    def _settings(self) -> dict:
        if callable(self._settings_provider):
            try:
                return dict(self._settings_provider() or {})
            except Exception:
                pass
        return {}

    def _target_display(self) -> dict:
        displays = list_displays()
        cfg = self._settings()
        try:
            idx = int(cfg.get("popup_display", 0))
        except Exception:
            idx = 0
        idx = _clamp(idx, 0, max(0, len(displays) - 1))
        return displays[idx]

    def _apply_windows_popup_style(self, win: tk.Toplevel, opacity: float) -> None:
        if os.name != "nt":
            return
        try:
            hwnd = win.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            LWA_ALPHA = 0x00000002

            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020

            user32 = ctypes.windll.user32
            user32.GetWindowLongPtrW.restype = ctypes.c_longlong
            user32.SetWindowLongPtrW.restype = ctypes.c_longlong
            user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
            user32.GetParent.restype = ctypes.c_void_p

            def _apply_to_handle(handle: int) -> None:
                if not handle:
                    return
                ex_style = user32.GetWindowLongPtrW(handle, GWL_EXSTYLE)
                ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                user32.SetWindowLongPtrW(handle, GWL_EXSTYLE, ex_style)

                alpha = int(_clamp(opacity, 0.2, 1.0) * 255)
                user32.SetLayeredWindowAttributes(handle, 0, alpha, LWA_ALPHA)
                user32.SetWindowPos(
                    handle,
                    0,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )

            _apply_to_handle(hwnd)
            parent = user32.GetParent(hwnd)
            if parent and parent != hwnd:
                _apply_to_handle(parent)
        except Exception:
            pass

    def show(self, title: str, message: str) -> None:
        cfg = self._settings()
        if not bool(cfg.get("popup_enabled", True)):
            return

        # Replace any active popup immediately so new errors are never delayed.
        self._close_current()

        title_l = title.lower()
        is_error = (
            "error" in title_l
            or "timeout" in title_l
            or "fehler" in title_l
            or "zeit" in title_l
        )
        bg = "#3a1115" if is_error else "#1f1f1f"
        fg = "#ffd7d7" if is_error else "#f3f3f3"
        accent = "#d84a4a" if is_error else "#6f56c9"

        win = tk.Toplevel(self.root)
        self._window = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            opacity = float(cfg.get("popup_opacity", 0.95))
        except Exception:
            opacity = 0.95
        if os.name != "nt":
            win.attributes("-alpha", _clamp(opacity, 0.2, 1.0))
        win.configure(bg=accent)

        frame = tk.Frame(win, bg=bg, bd=0)
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(
            frame,
            text=title,
            bg=bg,
            fg=fg,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))

        tk.Label(
            frame,
            text=message,
            bg=bg,
            fg=fg,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=300,
        ).pack(fill="x", padx=10, pady=(0, 8))

        win.update_idletasks()
        width = max(300, frame.winfo_reqwidth() + 4)
        height = frame.winfo_reqheight() + 4
        display = self._target_display()
        left = int(display.get("left", 0))
        top = int(display.get("top", 0))
        right = int(display.get("right", left + win.winfo_screenwidth()))
        bottom = int(display.get("bottom", top + win.winfo_screenheight()))
        screen_w = right - left
        screen_h = bottom - top

        pos = str(cfg.get("popup_position", "bottom-right")).strip().lower()
        margin = 20
        if pos == "top-left":
            x = left + margin
            y = top + margin
        elif pos == "top-right":
            x = right - width - margin
            y = top + margin
        elif pos == "bottom-left":
            x = left + margin
            y = bottom - height - margin
        elif pos == "top-center":
            x = left + (screen_w - width) // 2
            y = top + margin
        elif pos == "bottom-center":
            x = left + (screen_w - width) // 2
            y = bottom - height - margin
        else:
            x = right - width - margin
            y = bottom - height - margin
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.update_idletasks()
        self._apply_windows_popup_style(win, opacity)

        if is_error:
            duration_ms = int(cfg.get("popup_error_duration_ms", 6000))
        else:
            duration_ms = int(cfg.get("popup_info_duration_ms", 3000))
        duration_ms = _clamp(duration_ms, 1000, 60000)
        self._hide_after_id = win.after(duration_ms, self._close_current)

    def _close_current(self) -> None:
        if self._window is None:
            return
        try:
            if self._hide_after_id is not None:
                self._window.after_cancel(self._hide_after_id)
        except Exception:
            pass
        self._hide_after_id = None
        try:
            self._window.destroy()
        except Exception:
            pass
        self._window = None

    def close(self) -> None:
        self._close_current()
