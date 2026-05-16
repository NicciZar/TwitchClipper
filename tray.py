import threading

from PIL import Image, ImageDraw
import pystray

import config
import i18n

_icon: pystray.Icon | None = None
_open_settings_cb = None
_clip_now_cb = None
_exit_cb = None
_custom_notify_cb = None


def make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#9146FF")
    draw.polygon([(22, 18), (22, 46), (46, 32)], fill="white")
    return img


def _build_menu(cfg: dict):
    return pystray.Menu(
        pystray.MenuItem(i18n.t(cfg, "tray_create_clip"), lambda icon, item: _clip_now_cb()),
        # On Windows, double-click triggers the default menu item.
        pystray.MenuItem(i18n.t(cfg, "tray_settings"), lambda icon, item: _open_settings_cb(), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(i18n.t(cfg, "tray_exit"), lambda icon, item: _do_exit(_exit_cb)),
    )


def setup(open_settings_cb, clip_now_cb, exit_cb) -> None:
    global _icon, _open_settings_cb, _clip_now_cb, _exit_cb
    _open_settings_cb = open_settings_cb
    _clip_now_cb = clip_now_cb
    _exit_cb = exit_cb
    cfg = config.load()

    _icon = pystray.Icon(
        name="TwitchClipper",
        icon=make_icon_image(),
        title="TwitchClipper",
        menu=_build_menu(cfg),
    )


def refresh_menu_labels() -> None:
    if _icon is None or _open_settings_cb is None or _clip_now_cb is None or _exit_cb is None:
        return
    try:
        _icon.menu = _build_menu(config.load())
        _icon.update_menu()
    except Exception:
        pass


def run() -> None:
    if _icon:
        _icon.run()


def run_detached() -> threading.Thread:
    t = threading.Thread(target=run, daemon=True, name="tray")
    t.start()
    return t


def set_notify_handler(callback) -> None:
    global _custom_notify_cb
    _custom_notify_cb = callback


def notify(title: str, message: str) -> None:
    if _custom_notify_cb is not None:
        try:
            _custom_notify_cb(title, message)
            return
        except Exception:
            pass
    if _icon:
        try:
            _icon.notify(message, title)
        except Exception:
            pass


def stop() -> None:
    if _icon:
        try:
            _icon.stop()
        except Exception:
            pass


def _do_exit(exit_cb) -> None:
    stop()
    exit_cb()
