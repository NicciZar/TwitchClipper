import os
import sys
import tkinter as tk
import ctypes
from PIL import ImageTk

import app_logs
import app_version
import config
import hotkey_listener
import i18n
import popup_notify
import settings_window
import tray


def _icon_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "twitchclipper.ico")


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TwitchClipper.App")
    except Exception:
        pass


def main() -> None:
    _set_windows_app_id()
    app_logs.start_session()
    cfg = config.load()
    app_logs.log_action(i18n.t(cfg, "log_app_started"))

    # Ensure download folder exists
    folder = cfg.get("download_folder", "")
    if folder:
        os.makedirs(folder, exist_ok=True)

    # Hidden tkinter root — keeps the process alive and owns dialog windows
    root = tk.Tk()
    root.withdraw()
    root.title(f"{i18n.t(cfg, 'app_name')} v{app_version.APP_VERSION}")
    try:
        icon_path = _icon_path()
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
        root._app_icon = ImageTk.PhotoImage(tray.make_icon_image())
        root.iconphoto(True, root._app_icon)
    except Exception:
        pass

    popup_notifier = popup_notify.PopupNotifier(root, settings_provider=config.load)

    def _custom_notify(title: str, message: str):
        try:
            root.after(0, lambda: popup_notifier.show(title, message))
        except tk.TclError:
            pass

    tray.set_notify_handler(_custom_notify)

    def open_settings():
        root.after(0, lambda: settings_window.open_settings(root, on_saved=_on_saved, on_exit_app=exit_app))

    def _on_saved(new_cfg):
        pass  # hotkey_listener.register is called inside settings_window on save

    def clip_now():
        import hotkey_listener as hl
        import threading
        threading.Thread(target=hl._do_clip, daemon=True, name="clip-manual").start()

    def exit_app():
        app_logs.log_action(i18n.t(cfg, "log_app_exiting"))
        hotkey_listener._unregister_current()
        try:
            popup_notifier.close()
        except Exception:
            pass
        root.after(0, root.destroy)

    # Setup tray
    tray.setup(
        open_settings_cb=open_settings,
        clip_now_cb=clip_now,
        exit_cb=exit_app,
    )
    tray.run_detached()

    # Register hotkey
    if cfg.get("access_token") and cfg.get("hotkey"):
        hotkey_listener.register(cfg)

    # First run — open settings automatically
    first_run = not cfg.get("client_id") or not cfg.get("access_token")
    if first_run:
        root.after(300, open_settings)

    root.mainloop()


if __name__ == "__main__":
    main()
