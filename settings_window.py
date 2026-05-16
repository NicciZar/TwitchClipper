import os
import sys
import threading
import json
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
import ctypes
from PIL import ImageTk
from tkinter import filedialog, messagebox, ttk

import app_logs
import app_version
import auth
import config
import hotkey_listener
import i18n
import popup_notify
import tray
import twitch_api

_window: tk.Toplevel | None = None
_lock = threading.Lock()


def _apply_windows_window_icon(window: tk.Toplevel, icon_path: str) -> None:
    if os.name != "nt" or not os.path.exists(icon_path):
        return
    try:
        window.update_idletasks()
        hwnd = window.winfo_id()
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        user32 = ctypes.windll.user32
        icon_handle = user32.LoadImageW(
            None,
            icon_path,
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if icon_handle:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon_handle)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon_handle)
            window._icon_handle = icon_handle
    except Exception:
        pass


def _icon_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "twitchclipper.ico")


def open_settings(root: tk.Tk, on_saved=None, on_exit_app=None) -> None:
    global _window
    with _lock:
        if _window is not None:
            try:
                _window.lift()
                _window.focus_force()
                return
            except tk.TclError:
                _window = None
        _window = _build(root, on_saved, on_exit_app)


def _build(root: tk.Tk, on_saved, on_exit_app) -> tk.Toplevel:
    win = tk.Toplevel(root)
    cfg = config.load()
    lang = i18n.get_language(cfg)

    def _t(key: str, **kwargs) -> str:
        return i18n.t(lang, key, **kwargs)

    win.title(_t("settings_title"))
    win.resizable(False, False)
    win.grab_set()
    try:
        icon_path = _icon_path()
        if os.path.exists(icon_path):
            win.iconbitmap(icon_path)
        win._app_icon = ImageTk.PhotoImage(tray.make_icon_image())
        win.iconphoto(True, win._app_icon)
        _apply_windows_window_icon(win, icon_path)
    except Exception:
        pass

    pad = {"padx": 10, "pady": 4}
    label_w = 22

    def _export_log_file(source_path: str, suggested_name: str, file_type_label: str):
        if not os.path.exists(source_path):
            messagebox.showinfo(_t("no_log"), _t("log_file_not_exists"), parent=win)
            return
        target_path = filedialog.asksaveasfilename(
            parent=win,
            title=f"Export {file_type_label}",
            initialfile=suggested_name,
            defaultextension=os.path.splitext(suggested_name)[1],
            filetypes=[
                (f"{file_type_label} {_t('files_label')}", f"*{os.path.splitext(suggested_name)[1]}"),
                (_t("all_files"), "*.*"),
            ],
        )
        if not target_path:
            return
        try:
            with open(source_path, "r", encoding="utf-8") as src, open(target_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            messagebox.showinfo(_t("export"), _t("export_to", path=target_path), parent=win)
        except OSError as exc:
            messagebox.showerror(_t("save_failed"), str(exc), parent=win)

    def _row(parent, label_text, widget_factory, row):
        tk.Label(parent, text=label_text, anchor="w", width=label_w).grid(
            row=row, column=0, sticky="w", **pad
        )
        widget = widget_factory(parent)
        widget.grid(row=row, column=1, sticky="ew", **pad)
        return widget

    # ── Tabs ────────────────────────────────────────────────────────────────
    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    tab_auth = ttk.Frame(notebook)
    tab_clip = ttk.Frame(notebook)
    tab_notify = ttk.Frame(notebook)
    tab_import_export = ttk.Frame(notebook)
    tab_session_log = ttk.Frame(notebook)
    tab_library = ttk.Frame(notebook)
    tab_twitch_clips = ttk.Frame(notebook)
    tab_about = ttk.Frame(notebook)
    notebook.add(tab_auth, text=f"  {_t('tab_auth')}  ")
    notebook.add(tab_clip, text=f"  {_t('tab_clip')}  ")
    notebook.add(tab_notify, text=f"  {_t('tab_notify')}  ")
    notebook.add(tab_library, text=f"  {_t('tab_clip_library')}  ")
    notebook.add(tab_twitch_clips, text=f"  {_t('tab_twitch_clips')}  ")
    notebook.add(tab_session_log, text=f"  {_t('tab_session_log')}  ")
    notebook.add(tab_import_export, text=f"  {_t('tab_import_export')}  ")
    notebook.add(tab_about, text=f"  {_t('tab_about')}  ")

    # ── About tab ───────────────────────────────────────────────────────────
    tk.Label(
        tab_about,
        text=_t("about_desc"),
        fg="gray",
        anchor="w",
        justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 6))

    tk.Label(tab_about, text=_t("about_version"), anchor="w", width=label_w).grid(
        row=1, column=0, sticky="w", **pad
    )
    tk.Label(tab_about, text=app_version.APP_VERSION, anchor="w").grid(
        row=1, column=1, sticky="w", **pad
    )

    tk.Label(tab_about, text=_t("about_build_date"), anchor="w", width=label_w).grid(
        row=2, column=0, sticky="w", **pad
    )
    tk.Label(tab_about, text=app_version.APP_BUILD_DATE, anchor="w").grid(
        row=2, column=1, sticky="w", **pad
    )

    tk.Label(tab_about, text=_t("about_repository"), anchor="w", width=label_w).grid(
        row=3, column=0, sticky="w", **pad
    )
    repo_link = tk.Label(
        tab_about,
        text=app_version.APP_REPO_URL,
        fg="#1a73e8",
        cursor="hand2",
        anchor="w",
    )
    repo_link.grid(row=3, column=1, sticky="w", **pad)
    repo_link.bind("<Button-1>", lambda _e: webbrowser.open_new(app_version.APP_REPO_URL))

    def _copy_repo_url():
        win.clipboard_clear()
        win.clipboard_append(app_version.APP_REPO_URL)
        messagebox.showinfo(_t("copied"), _t("copied_repo_url"), parent=win)

    tk.Button(tab_about, text=_t("copy"), command=_copy_repo_url, width=8).grid(
        row=3, column=2, sticky="w", padx=4, pady=4
    )
    tab_about.columnconfigure(1, weight=1)

    # ── Notifications tab ───────────────────────────────────────────────────
    tk.Label(
        tab_notify,
        text=_t("notify_customize"),
        fg="gray",
        anchor="w",
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 4))

    detected_lang = i18n.detect_system_language()
    detected_lang_label = i18n.t(lang, f"lang_{detected_lang}")
    auto_lang_label = _t("lang_auto_detected", language=detected_lang_label)

    language_map = {
        auto_lang_label: "auto",
        _t("lang_en"): "en",
        _t("lang_de"): "de",
    }
    reverse_language_map = {v: k for k, v in language_map.items()}
    current_lang_setting = str(cfg.get("language", "auto")).strip().lower()
    if current_lang_setting not in reverse_language_map:
        current_lang_setting = "auto"
    var_language = tk.StringVar(value=reverse_language_map[current_lang_setting])

    var_popup_enabled = tk.BooleanVar(value=bool(cfg.get("popup_enabled", True)))
    var_popup_position = tk.StringVar(value=str(cfg.get("popup_position", "bottom-right")))
    var_popup_opacity_pct = tk.IntVar(value=int(round(float(cfg.get("popup_opacity", 0.95)) * 100)))
    var_popup_info_sec = tk.IntVar(value=max(1, int(cfg.get("popup_info_duration_ms", 3000)) // 1000))
    var_popup_error_sec = tk.IntVar(value=max(1, int(cfg.get("popup_error_duration_ms", 6000)) // 1000))

    displays = popup_notify.list_displays()
    display_labels = [d["label"] for d in displays]
    saved_display_idx = int(cfg.get("popup_display", 0)) if str(cfg.get("popup_display", "")).isdigit() else 0
    if saved_display_idx < 0 or saved_display_idx >= len(displays):
        saved_display_idx = 0
    var_popup_display_label = tk.StringVar(value=display_labels[saved_display_idx] if display_labels else "Display 1")

    _row(
        tab_notify,
        _t("lang_label"),
        lambda p: ttk.Combobox(p, textvariable=var_language, values=list(language_map.keys()), state="readonly", width=22),
        1,
    )
    _row(tab_notify, _t("enable_popups"), lambda p: tk.Checkbutton(p, variable=var_popup_enabled), 2)
    _row(
        tab_notify,
        _t("screen"),
        lambda p: ttk.Combobox(p, textvariable=var_popup_display_label, values=display_labels, state="readonly", width=44),
        3,
    )
    _row(
        tab_notify,
        _t("position"),
        lambda p: ttk.Combobox(
            p,
            textvariable=var_popup_position,
            values=["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"],
            state="readonly",
            width=22,
        ),
        4,
    )

    opacity_frame = tk.Frame(tab_notify)
    tk.Scale(opacity_frame, from_=20, to=100, orient="horizontal", variable=var_popup_opacity_pct, length=230).pack(side="left")
    tk.Label(opacity_frame, text="%", fg="gray").pack(side="left", padx=4)
    opacity_frame.grid(row=5, column=1, sticky="w", padx=10, pady=4)
    tk.Label(tab_notify, text=_t("opacity"), anchor="w", width=label_w).grid(row=5, column=0, sticky="w", padx=10, pady=4)

    info_duration_frame = tk.Frame(tab_notify)
    tk.Spinbox(info_duration_frame, from_=1, to=60, textvariable=var_popup_info_sec, width=5).pack(side="left")
    tk.Label(info_duration_frame, text=_t("seconds")).pack(side="left", padx=4)
    info_duration_frame.grid(row=6, column=1, sticky="w", padx=10, pady=4)
    tk.Label(tab_notify, text=_t("info_duration"), anchor="w", width=label_w).grid(row=6, column=0, sticky="w", padx=10, pady=4)

    error_duration_frame = tk.Frame(tab_notify)
    tk.Spinbox(error_duration_frame, from_=1, to=60, textvariable=var_popup_error_sec, width=5).pack(side="left")
    tk.Label(error_duration_frame, text=_t("seconds")).pack(side="left", padx=4)
    error_duration_frame.grid(row=7, column=1, sticky="w", padx=10, pady=4)
    tk.Label(tab_notify, text=_t("error_duration"), anchor="w", width=label_w).grid(row=7, column=0, sticky="w", padx=10, pady=4)

    preview_frame = tk.Frame(tab_notify)
    preview_frame.grid(row=8, column=1, sticky="w", padx=10, pady=(8, 4))

    def _test_info_popup():
        tray.notify(_t("app_name"), _t("test_info_msg"))

    def _test_error_popup():
        tray.notify(_t("error_title"), _t("test_error_msg"))

    tk.Button(preview_frame, text=_t("test_info"), command=_test_info_popup, width=12).pack(side="left")
    tk.Button(preview_frame, text=_t("test_error"), command=_test_error_popup, width=12).pack(side="left", padx=6)
    tk.Label(tab_notify, text=_t("preview"), anchor="w", width=label_w).grid(row=8, column=0, sticky="w", padx=10, pady=(8, 4))

    tab_notify.columnconfigure(1, weight=1)

    # ── Session Log tab ──────────────────────────────────────────────────────
    tk.Label(
        tab_session_log,
        text=_t("session_actions"),
        fg="gray",
        anchor="w",
    ).pack(fill="x", padx=10, pady=(8, 4))

    session_text = tk.Text(tab_session_log, height=16, wrap="none")
    session_text.pack(fill="both", expand=True, padx=10, pady=4)
    session_scroll_y = tk.Scrollbar(tab_session_log, orient="vertical", command=session_text.yview)
    session_scroll_y.pack(side="right", fill="y")
    session_scroll_x = tk.Scrollbar(tab_session_log, orient="horizontal", command=session_text.xview)
    session_scroll_x.pack(fill="x", padx=10)
    session_text.configure(yscrollcommand=session_scroll_y.set, xscrollcommand=session_scroll_x.set)

    session_sig = [None]
    library_sig = [None]

    def _file_sig(path: str):
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _load_session_log(force: bool = False):
        path = app_logs.action_log_path()
        sig = _file_sig(path)
        if not force and sig == session_sig[0]:
            return
        session_sig[0] = sig
        session_text.config(state="normal")
        session_text.delete("1.0", tk.END)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    session_text.insert("1.0", f.read())
            except OSError as exc:
                session_text.insert("1.0", _t("session_log_read_failed", error=exc))
        else:
            session_text.insert("1.0", _t("no_session_log_yet"))
        session_text.config(state="disabled")

    session_btns = tk.Frame(tab_session_log)
    session_btns.pack(fill="x", padx=10, pady=(0, 8))
    tk.Button(session_btns, text=_t("refresh"), command=lambda: _load_session_log(force=True), width=10).pack(side="left")
    tk.Button(
        session_btns,
        text=_t("open_file"),
        width=10,
        command=lambda: os.startfile(app_logs.action_log_path()) if os.path.exists(app_logs.action_log_path()) else messagebox.showinfo(_t("no_log"), _t("session_log_file_not_exists"), parent=win),
    ).pack(side="left", padx=6)
    tk.Button(
        session_btns,
        text=_t("export"),
        width=10,
        command=lambda: _export_log_file(app_logs.action_log_path(), "session_actions_export.log", _t("tab_session_log")),
    ).pack(side="left")

    # ── Clip Library tab ─────────────────────────────────────────────────────
    tk.Label(
        tab_library,
        text=_t("saved_clips_library"),
        fg="gray",
        anchor="w",
    ).pack(fill="x", padx=10, pady=(8, 4))

    library_columns = ("status", "saved_at", "title", "broadcaster", "clip_url", "file_path")
    library_tree = ttk.Treeview(tab_library, columns=library_columns, show="headings", height=12, selectmode="extended")
    library_tree.heading("status", text=_t("column_status"))
    library_tree.heading("saved_at", text=_t("column_saved_at"))
    library_tree.heading("title", text=_t("column_title"))
    library_tree.heading("broadcaster", text=_t("column_broadcaster"))
    library_tree.heading("clip_url", text=_t("column_twitch_link"))
    library_tree.heading("file_path", text=_t("column_file_path"))
    library_tree.column("status", width=95, anchor="w", stretch=False)
    library_tree.column("saved_at", width=135, anchor="w", stretch=False)
    library_tree.column("title", width=170, anchor="w", stretch=False)
    library_tree.column("broadcaster", width=100, anchor="w", stretch=False)
    library_tree.column("clip_url", width=180, anchor="w", stretch=False)
    library_tree.column("file_path", width=240, anchor="w", stretch=False)
    library_tree.pack(fill="both", expand=True, padx=10, pady=4)

    library_scroll_y = tk.Scrollbar(tab_library, orient="vertical", command=library_tree.yview)
    library_scroll_y.pack(side="right", fill="y")
    library_scroll_x = tk.Scrollbar(tab_library, orient="horizontal", command=library_tree.xview)
    library_scroll_x.pack(fill="x", padx=10)
    library_tree.configure(yscrollcommand=library_scroll_y.set, xscrollcommand=library_scroll_x.set)

    library_item_data = {}
    library_item_by_clip_id = {}
    library_download_running = [False]
    var_library_progress = tk.StringVar(value="")
    var_library_progress_value = tk.DoubleVar(value=0.0)

    def _status_text(status: str) -> str:
        key = f"status_{(status or '').strip().lower()}"
        translated = _t(key)
        return translated if translated != key else (status or "")

    def _selected_library_entries():
        item_ids = library_tree.selection()
        rows = [library_item_data[iid] for iid in item_ids if iid in library_item_data]
        return rows

    def _set_row_status_by_clip_id(clip_id: str, status: str):
        item_id = library_item_by_clip_id.get(str(clip_id or "").strip())
        if not item_id:
            return
        values = list(library_tree.item(item_id, "values"))
        if not values:
            return
        values[0] = _status_text(status)
        library_tree.item(item_id, values=tuple(values))
        if item_id in library_item_data:
            library_item_data[item_id]["status"] = status

    def _open_selected_clip_link():
        rows = _selected_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return
        row = rows[0]
        clip_url = row.get("clip_url", "")
        if clip_url:
            webbrowser.open_new(clip_url)

    def _open_selected_clip_file():
        rows = _selected_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return
        row = rows[0]
        file_path = row.get("file_path", "")
        if file_path and os.path.exists(file_path):
            folder_path = os.path.dirname(file_path)
            if os.path.exists(folder_path):
                os.startfile(folder_path)
            else:
                messagebox.showerror(_t("missing_file"), _t("saved_file_missing"), parent=win)
        else:
            messagebox.showerror(_t("missing_file"), _t("saved_file_missing"), parent=win)

    def _download_entries(entries: list[dict]):
        if not entries:
            return

        if library_download_running[0]:
            messagebox.showinfo(_t("download_in_progress_title"), _t("download_in_progress_msg"), parent=win)
            return

        total = len(entries)
        library_download_running[0] = True
        btn_library_refresh.config(state="disabled")
        btn_download_selected.config(state="disabled")
        btn_download_missing.config(state="disabled")
        btn_delete_selected_twitch.config(state="disabled")
        btn_delete_file_purge.config(state="disabled")
        progress_bar.configure(maximum=max(1, total))
        var_library_progress_value.set(0)
        var_library_progress.set(_t("download_progress", current=0, total=total, ok=0, failed=0))

        def _worker():
            ok = 0
            failed = 0
            errors = []
            for idx, entry in enumerate(entries, start=1):
                clip_id = str(entry.get("clip_id", "")).strip()

                def _mark_downloading(cid=clip_id):
                    _set_row_status_by_clip_id(cid, "downloading")

                win.after(0, _mark_downloading)

                success, _msg = hotkey_listener.download_library_entry(entry)
                if success:
                    ok += 1
                else:
                    failed += 1
                    errors.append(_msg)

                def _progress_update(current=idx, total_count=total, ok_count=ok, failed_count=failed, cid=clip_id, was_success=success):
                    _set_row_status_by_clip_id(cid, "downloaded" if was_success else "failed")
                    var_library_progress_value.set(current)
                    var_library_progress.set(
                        _t(
                            "download_progress",
                            current=current,
                            total=total_count,
                            ok=ok_count,
                            failed=failed_count,
                        )
                    )

                win.after(0, _progress_update)

            def _done_ui():
                library_download_running[0] = False
                btn_library_refresh.config(state="normal")
                btn_download_selected.config(state="normal")
                btn_download_missing.config(state="normal")
                btn_delete_selected_twitch.config(state="normal")
                btn_delete_file_purge.config(state="normal")
                _load_clip_library(force=True)

                # Include error messages if there are failures
                error_details = "\n".join(errors) if errors else ""
                messagebox.showinfo(
                    _t("saved"),
                    _t("download_done") + "\n" + _t("downloaded_count", ok=ok, failed=failed) + (f"\n\n{error_details}" if failed > 0 else ""),
                    parent=win,
                )
                var_library_progress_value.set(0)
                var_library_progress.set("")

            win.after(0, _done_ui)

        threading.Thread(target=_worker, daemon=True, name="library-download-worker").start()

    def _download_selected():
        rows = _selected_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return
        _download_entries(rows)

    def _download_missing():
        lib_path = app_logs.clip_library_path()
        if not os.path.exists(lib_path):
            messagebox.showinfo(_t("no_library"), _t("clip_library_file_not_exists"), parent=win)
            return
        rows = app_logs.get_clip_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_library"), _t("clip_library_empty"), parent=win)
            return
        missing = [r for r in rows if str(r.get("status", "")).lower() in ("missing", "failed")]
        if not missing:
            messagebox.showinfo(_t("download_missing"), _t("no_missing_clips"), parent=win)
            return
        _download_entries(missing)

    def _delete_selected_on_twitch():
        rows = _selected_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return

        if library_download_running[0]:
            messagebox.showinfo(_t("operation_in_progress_title"), _t("operation_in_progress_msg"), parent=win)
            return

        if not messagebox.askyesno(
            _t("delete_on_twitch_title"),
            _t("delete_on_twitch_confirm", count=len(rows)),
            parent=win,
        ):
            return

        total = len(rows)
        library_download_running[0] = True
        btn_library_refresh.config(state="disabled")
        btn_download_selected.config(state="disabled")
        btn_download_missing.config(state="disabled")
        btn_delete_selected_twitch.config(state="disabled")
        btn_delete_file_purge.config(state="disabled")
        progress_bar.configure(maximum=max(1, total))
        var_library_progress_value.set(0)
        var_library_progress.set(_t("delete_progress", current=0, total=total, ok=0, failed=0))

        def _worker():
            ok = 0
            failed = 0
            for idx, entry in enumerate(rows, start=1):
                clip_id = str(entry.get("clip_id", "")).strip()

                def _mark_deleting(cid=clip_id):
                    _set_row_status_by_clip_id(cid, "deleting")

                win.after(0, _mark_deleting)

                success, _msg = hotkey_listener.delete_library_entry_on_twitch(entry)
                if success:
                    ok += 1
                else:
                    failed += 1

                def _progress_update(current=idx, total_count=total, ok_count=ok, failed_count=failed, cid=clip_id, was_success=success):
                    _set_row_status_by_clip_id(cid, "deleted" if was_success else "failed")
                    var_library_progress_value.set(current)
                    var_library_progress.set(
                        _t(
                            "delete_progress",
                            current=current,
                            total=total_count,
                            ok=ok_count,
                            failed=failed_count,
                        )
                    )

                win.after(0, _progress_update)

            def _done_ui():
                library_download_running[0] = False
                btn_library_refresh.config(state="normal")
                btn_download_selected.config(state="normal")
                btn_download_missing.config(state="normal")
                btn_delete_selected_twitch.config(state="normal")
                btn_delete_file_purge.config(state="normal")
                _load_clip_library(force=True)
                messagebox.showinfo(
                    _t("delete_on_twitch_title"),
                    _t("delete_done") + "\n" + _t("deleted_count", ok=ok, failed=failed),
                    parent=win,
                )
                var_library_progress_value.set(0)
                var_library_progress.set("")

            win.after(0, _done_ui)

        threading.Thread(target=_worker, daemon=True, name="library-delete-worker").start()

    def _delete_file_and_purge_selected():
        rows = _selected_library_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return

        if library_download_running[0]:
            messagebox.showinfo(_t("operation_in_progress_title"), _t("operation_in_progress_msg"), parent=win)
            return

        if not messagebox.askyesno(
            _t("purge_library_title"),
            _t("purge_library_confirm", count=len(rows)),
            parent=win,
        ):
            return

        total = len(rows)
        library_download_running[0] = True
        btn_library_refresh.config(state="disabled")
        btn_download_selected.config(state="disabled")
        btn_download_missing.config(state="disabled")
        btn_delete_selected_twitch.config(state="disabled")
        btn_delete_file_purge.config(state="disabled")
        progress_bar.configure(maximum=max(1, total))
        var_library_progress_value.set(0)
        var_library_progress.set(_t("purge_progress", current=0, total=total, ok=0, failed=0))

        def _worker():
            ok = 0
            failed = 0
            errors = []

            for idx, entry in enumerate(rows, start=1):
                clip_id = str(entry.get("clip_id", "")).strip()
                title = str(entry.get("title", clip_id)).strip() or clip_id
                file_path = str(entry.get("file_path", "")).strip()

                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                    if not app_logs.purge_clip_library_entry(clip_id):
                        raise RuntimeError(_t("purge_library_entry_not_found", clip_id=clip_id))
                    app_logs.log_action(_t("log_clip_file_purged"), f"{clip_id} | {file_path}")
                    ok += 1
                except Exception as exc:
                    failed += 1
                    errors.append(f"{title}: {exc}")

                def _progress_update(current=idx, total_count=total, ok_count=ok, failed_count=failed):
                    var_library_progress_value.set(current)
                    var_library_progress.set(
                        _t(
                            "purge_progress",
                            current=current,
                            total=total_count,
                            ok=ok_count,
                            failed=failed_count,
                        )
                    )

                win.after(0, _progress_update)

            def _done_ui():
                library_download_running[0] = False
                btn_library_refresh.config(state="normal")
                btn_download_selected.config(state="normal")
                btn_download_missing.config(state="normal")
                btn_delete_selected_twitch.config(state="normal")
                btn_delete_file_purge.config(state="normal")
                _load_clip_library(force=True)
                _load_twitch_clips(force=True)

                error_details = "\n".join(errors) if errors else ""
                messagebox.showinfo(
                    _t("purge_library_title"),
                    _t("purge_done") + "\n" + _t("purged_count", ok=ok, failed=failed) + (f"\n\n{error_details}" if failed > 0 else ""),
                    parent=win,
                )
                var_library_progress_value.set(0)
                var_library_progress.set("")

            win.after(0, _done_ui)

        threading.Thread(target=_worker, daemon=True, name="library-purge-worker").start()

    def _auto_resize_columns(tree: ttk.Treeview, max_col_width: int = 280) -> None:
        """Resize each column to fit the widest content, capped at max_col_width."""
        font = tkfont.nametofont("TkDefaultFont")
        for col in tree["columns"]:
            heading = str(tree.heading(col, "text") or col)
            col_width = font.measure(heading) + 20  # padding
            for iid in tree.get_children():
                cell = str(tree.set(iid, col))
                w = font.measure(cell) + 20
                if w > col_width:
                    col_width = w
            tree.column(col, width=min(col_width, max_col_width))

    def _load_clip_library(force: bool = False):
        path = app_logs.clip_library_path()
        sig = _file_sig(path)
        if not force and sig == library_sig[0]:
            return
        library_sig[0] = sig
        library_item_data.clear()
        library_item_by_clip_id.clear()
        for item in library_tree.get_children():
            library_tree.delete(item)
        try:
            rows = app_logs.get_clip_library_entries()
        except Exception as exc:
            messagebox.showerror(_t("error_title"), _t("clip_library_read_failed", error=exc), parent=win)
            return

        for row in rows:
            item_id = library_tree.insert(
                "",
                "end",
                values=(
                    _status_text(str(row.get("status", "missing"))),
                    row.get("saved_at", ""),
                    row.get("title", ""),
                    row.get("broadcaster", ""),
                    row.get("clip_url", ""),
                    row.get("file_path", ""),
                ),
            )
            library_item_data[item_id] = row
            clip_id = str(row.get("clip_id", "")).strip()
            if clip_id:
                library_item_by_clip_id[clip_id] = item_id

        _auto_resize_columns(library_tree)

    library_btns_top = tk.Frame(tab_library)
    library_btns_top.pack(fill="x", padx=10, pady=(0, 4))
    btn_library_refresh = tk.Button(library_btns_top, text=_t("refresh"), command=lambda: _load_clip_library(force=True))
    btn_library_refresh.pack(side="left")
    btn_download_selected = tk.Button(library_btns_top, text=_t("download_selected"), command=_download_selected)
    btn_download_selected.pack(side="left", padx=6)
    btn_download_missing = tk.Button(library_btns_top, text=_t("download_missing"), command=_download_missing)
    btn_download_missing.pack(side="left")
    btn_delete_selected_twitch = tk.Button(library_btns_top, text=_t("delete_selected_twitch"), command=_delete_selected_on_twitch)
    btn_delete_selected_twitch.pack(side="left", padx=6)
    btn_delete_file_purge = tk.Button(library_btns_top, text=_t("delete_file_purge"), command=_delete_file_and_purge_selected)
    btn_delete_file_purge.pack(side="left")

    library_btns_mid = tk.Frame(tab_library)
    library_btns_mid.pack(fill="x", padx=10, pady=(0, 4))
    tk.Button(library_btns_mid, text=_t("open_twitch_link"), command=_open_selected_clip_link).pack(side="left")
    tk.Button(library_btns_mid, text=_t("open_file"), command=_open_selected_clip_file).pack(side="left", padx=6)

    library_btns_bottom = tk.Frame(tab_library)
    library_btns_bottom.pack(fill="x", padx=10, pady=(0, 8))
    tk.Button(
        library_btns_bottom,
        text=_t("open_library_file"),
        command=lambda: os.startfile(app_logs.clip_library_path()) if os.path.exists(app_logs.clip_library_path()) else messagebox.showinfo(_t("no_library"), _t("clip_library_file_not_exists"), parent=win),
    ).pack(side="left")
    tk.Button(
        library_btns_bottom,
        text=_t("export"),
        command=lambda: _export_log_file(app_logs.clip_library_path(), "clip_library_export.jsonl", _t("tab_clip_library")),
    ).pack(side="left", padx=6)

    library_progress_frame = tk.Frame(tab_library)
    library_progress_frame.pack(fill="x", padx=10, pady=(0, 8))
    progress_bar = ttk.Progressbar(
        library_progress_frame,
        orient="horizontal",
        mode="determinate",
        maximum=1,
        variable=var_library_progress_value,
    )
    progress_bar.pack(fill="x")
    tk.Label(library_progress_frame, textvariable=var_library_progress, anchor="w", fg="gray").pack(fill="x", pady=(2, 0))

    # ── Twitch Clips tab ────────────────────────────────────────────────────
    tk.Label(
        tab_twitch_clips,
        text=_t("twitch_clips_desc"),
        fg="gray",
        anchor="w",
    ).pack(fill="x", padx=10, pady=(8, 4))

    twitch_columns = ("creator", "title", "created_at", "view_count", "url")
    twitch_tree = ttk.Treeview(tab_twitch_clips, columns=twitch_columns, show="headings", height=12, selectmode="extended")
    twitch_tree.heading("creator", text=_t("column_creator"))
    twitch_tree.heading("title", text=_t("column_title"))
    twitch_tree.heading("created_at", text=_t("column_created"))
    twitch_tree.heading("view_count", text=_t("column_views"))
    twitch_tree.heading("url", text=_t("column_twitch_link"))
    twitch_tree.column("creator", width=120, anchor="w", stretch=False)
    twitch_tree.column("title", width=170, anchor="w", stretch=False)
    twitch_tree.column("created_at", width=120, anchor="w", stretch=False)
    twitch_tree.column("view_count", width=80, anchor="w", stretch=False)
    twitch_tree.column("url", width=180, anchor="w", stretch=False)
    twitch_tree.pack(fill="both", expand=True, padx=10, pady=4)

    twitch_scroll_y = tk.Scrollbar(tab_twitch_clips, orient="vertical", command=twitch_tree.yview)
    twitch_scroll_y.pack(side="right", fill="y")
    twitch_scroll_x = tk.Scrollbar(tab_twitch_clips, orient="horizontal", command=twitch_tree.xview)
    twitch_scroll_x.pack(fill="x", padx=10)
    twitch_tree.configure(yscrollcommand=twitch_scroll_y.set, xscrollcommand=twitch_scroll_x.set)

    twitch_item_data = {}
    twitch_item_by_clip_id = {}
    twitch_fetch_running = [False]
    var_twitch_progress = tk.StringVar(value="")
    var_twitch_progress_value = tk.DoubleVar(value=0.0)

    def _selected_twitch_entries():
        item_ids = twitch_tree.selection()
        rows = [twitch_item_data[iid] for iid in item_ids if iid in twitch_item_data]
        return rows

    def _open_twitch_link():
        rows = _selected_twitch_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return
        row = rows[0]
        clip_url = row.get("url", "")
        if clip_url:
            webbrowser.open_new(clip_url)

    def _download_twitch_clips():
        rows = _selected_twitch_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return

        if twitch_fetch_running[0]:
            messagebox.showinfo(_t("operation_in_progress_title"), _t("operation_in_progress_msg"), parent=win)
            return

        total = len(rows)
        twitch_fetch_running[0] = True
        btn_twitch_refresh.config(state="disabled")
        btn_twitch_download.config(state="disabled")
        btn_twitch_rename.config(state="disabled")
        btn_twitch_delete.config(state="disabled")
        var_twitch_progress_value.set(0)
        var_twitch_progress.set(_t("download_progress", current=0, total=total, ok=0, failed=0))

        def _worker():
            ok = 0
            failed = 0
            for idx, entry in enumerate(rows, start=1):
                clip_id = str(entry.get("clip_id", "")).strip()
                
                def _mark_downloading():
                    pass  # No status update UI for Twitch clips yet

                win.after(0, _mark_downloading)

                success, _msg = hotkey_listener.download_library_entry(entry)
                if success:
                    ok += 1
                else:
                    failed += 1

                def _progress_update(current=idx, total_count=total, ok_count=ok, failed_count=failed):
                    var_twitch_progress_value.set(current)
                    var_twitch_progress.set(
                        _t(
                            "download_progress",
                            current=current,
                            total=total_count,
                            ok=ok_count,
                            failed=failed_count,
                        )
                    )

                win.after(0, _progress_update)

            def _done_ui():
                twitch_fetch_running[0] = False
                btn_twitch_refresh.config(state="normal")
                btn_twitch_download.config(state="normal")
                btn_twitch_rename.config(state="normal")
                btn_twitch_delete.config(state="normal")
                _load_twitch_clips(force=True)
                messagebox.showinfo(
                    _t("saved"),
                    _t("download_done") + "\n" + _t("downloaded_count", ok=ok, failed=failed),
                    parent=win,
                )
                var_twitch_progress_value.set(0)
                var_twitch_progress.set("")

            win.after(0, _done_ui)

        threading.Thread(target=_worker, daemon=True, name="twitch-clips-download-worker").start()

    def _rename_twitch_clips():
        rows = _selected_twitch_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return

        if len(rows) > 1:
            messagebox.showinfo(_t("too_many"), _t("select_one_clip"), parent=win)
            return

        if twitch_fetch_running[0]:
            messagebox.showinfo(_t("operation_in_progress_title"), _t("operation_in_progress_msg"), parent=win)
            return

        row = rows[0]
        clip_id = str(row.get("clip_id", "")).strip()

        if messagebox.askyesno(
            _t("rename_clip_title"),
            _t("rename_clip_info"),
            parent=win,
        ):
            twitch_fetch_running[0] = True
            btn_twitch_refresh.config(state="disabled")
            btn_twitch_download.config(state="disabled")
            btn_twitch_rename.config(state="disabled")
            btn_twitch_delete.config(state="disabled")
            var_twitch_progress_value.set(0)
            var_twitch_progress.set(_t("opening_clip_editor"))

            def _worker():
                success, msg = hotkey_listener.rename_library_entry_on_twitch(row, "")

                def _done_ui():
                    twitch_fetch_running[0] = False
                    btn_twitch_refresh.config(state="normal")
                    btn_twitch_download.config(state="normal")
                    btn_twitch_rename.config(state="normal")
                    btn_twitch_delete.config(state="normal")
                    if success:
                        messagebox.showinfo(_t("success"), _t("clip_editor_opened"), parent=win)
                    else:
                        messagebox.showerror(_t("rename_failed"), msg, parent=win)
                    var_twitch_progress_value.set(0)
                    var_twitch_progress.set("")

                win.after(0, _done_ui)

            threading.Thread(target=_worker, daemon=True, name="twitch-clips-rename-worker").start()

    def _delete_twitch_clips():
        rows = _selected_twitch_entries()
        if not rows:
            messagebox.showinfo(_t("no_selection"), _t("select_clip_first"), parent=win)
            return

        if twitch_fetch_running[0]:
            messagebox.showinfo(_t("operation_in_progress_title"), _t("operation_in_progress_msg"), parent=win)
            return

        if not messagebox.askyesno(
            _t("delete_on_twitch_title"),
            _t("delete_on_twitch_confirm", count=len(rows)),
            parent=win,
        ):
            return

        total = len(rows)
        twitch_fetch_running[0] = True
        btn_twitch_refresh.config(state="disabled")
        btn_twitch_download.config(state="disabled")
        btn_twitch_rename.config(state="disabled")
        btn_twitch_delete.config(state="disabled")
        var_twitch_progress_value.set(0)
        var_twitch_progress.set(_t("delete_progress", current=0, total=total, ok=0, failed=0))

        def _worker():
            ok = 0
            failed = 0
            for idx, entry in enumerate(rows, start=1):
                success, _msg = hotkey_listener.delete_library_entry_on_twitch(entry)
                if success:
                    ok += 1
                else:
                    failed += 1

                def _progress_update(current=idx, total_count=total, ok_count=ok, failed_count=failed):
                    var_twitch_progress_value.set(current)
                    var_twitch_progress.set(
                        _t(
                            "delete_progress",
                            current=current,
                            total=total_count,
                            ok=ok_count,
                            failed=failed_count,
                        )
                    )

                win.after(0, _progress_update)

            def _done_ui():
                twitch_fetch_running[0] = False
                btn_twitch_refresh.config(state="normal")
                btn_twitch_download.config(state="normal")
                btn_twitch_rename.config(state="normal")
                btn_twitch_delete.config(state="normal")
                _load_twitch_clips(force=True)
                messagebox.showinfo(
                    _t("delete_on_twitch_title"),
                    _t("delete_done") + "\n" + _t("deleted_count", ok=ok, failed=failed),
                    parent=win,
                )
                var_twitch_progress_value.set(0)
                var_twitch_progress.set("")

            win.after(0, _done_ui)

        threading.Thread(target=_worker, daemon=True, name="twitch-clips-delete-worker").start()

    def _load_twitch_clips(force: bool = False):
        if twitch_fetch_running[0]:
            return

        token = cfg.get("access_token", "").strip()
        client_id = cfg.get("client_id", "").strip()
        broadcaster_id = cfg.get("broadcaster_id", "").strip()

        if not all([token, client_id, broadcaster_id]):
            twitch_item_data.clear()
            twitch_item_by_clip_id.clear()
            for item in twitch_tree.get_children():
                twitch_tree.delete(item)
            messagebox.showinfo(_t("missing"), _t("missing_test_connection"), parent=win)
            return

        twitch_fetch_running[0] = True
        btn_twitch_refresh.config(state="disabled")
        btn_twitch_download.config(state="disabled")
        btn_twitch_delete.config(state="disabled")
        var_twitch_progress.set(_t("fetch_clips_from_twitch"))
        var_twitch_progress_value.set(0)

        def _worker():
            try:
                # Fetch all clips from Twitch, refreshing token once on 401.
                token_in_use = token
                try:
                    all_twitch_clips = twitch_api.get_broadcaster_clips(broadcaster_id, token_in_use, client_id)
                except PermissionError as exc:
                    is_unauthorized = "401" in str(exc)
                    client_secret = str(cfg.get("client_secret", "")).strip()
                    refresh_token = str(cfg.get("refresh_token", "")).strip()
                    if not (is_unauthorized and client_secret and refresh_token):
                        raise

                    try:
                        new_tokens = twitch_api.refresh_access_token(client_id, client_secret, refresh_token)
                    except Exception as refresh_exc:
                        raise PermissionError(f"Token refresh failed: {refresh_exc}") from refresh_exc

                    token_in_use = str(new_tokens.get("access_token", "")).strip()
                    if not token_in_use:
                        raise PermissionError("Token refresh failed: empty access token returned.")

                    cfg["access_token"] = token_in_use
                    if new_tokens.get("refresh_token"):
                        cfg["refresh_token"] = str(new_tokens.get("refresh_token", "")).strip()
                    expires_in = int(new_tokens.get("expires_in", 0) or 0)
                    cfg["token_expires_at"] = int(time.time()) + expires_in if expires_in > 0 else 0
                    config.save(cfg)
                    app_logs.log_action(_t("log_access_token_refreshed"))

                    # Retry once with fresh token.
                    all_twitch_clips = twitch_api.get_broadcaster_clips(broadcaster_id, token_in_use, client_id)
                
                # Get local library clips to filter
                local_library_clip_ids = set()
                try:
                    lib_entries = app_logs.get_clip_library_entries()
                    local_library_clip_ids = {str(e.get("clip_id", "")).strip() for e in lib_entries if e.get("clip_id")}
                except Exception:
                    pass

                # Filter out clips already in library
                filtered_clips = [
                    clip for clip in all_twitch_clips
                    if str(clip.get("clip_id", "")).strip() not in local_library_clip_ids
                ]

                def _update_ui():
                    twitch_item_data.clear()
                    twitch_item_by_clip_id.clear()
                    for item in twitch_tree.get_children():
                        twitch_tree.delete(item)

                    if not filtered_clips:
                        if all_twitch_clips:
                            messagebox.showinfo(_t("no_selection"), _t("twitch_clips_are_new"), parent=win)
                        else:
                            messagebox.showinfo(_t("no_library"), _t("no_clips_available"), parent=win)
                    else:
                        for clip in filtered_clips:
                            # Format the created_at timestamp
                            created_at_str = clip.get("created_at", "")
                            try:
                                # Parse ISO format and extract date
                                created_dt = created_at_str.split("T")[0] if created_at_str else ""
                            except Exception:
                                created_dt = created_at_str

                            item_id = twitch_tree.insert(
                                "",
                                "end",
                                values=(
                                    clip.get("creator_name", ""),
                                    clip.get("title", ""),
                                    created_dt,
                                    clip.get("view_count", 0),
                                    clip.get("url", ""),
                                ),
                            )
                            # Store full clip data for download/delete operations
                            clip_data = {
                                "clip_id": clip.get("clip_id", ""),
                                "title": clip.get("title", ""),
                                "creator_name": clip.get("creator_name", ""),
                                "clip_url": clip.get("url", ""),
                                "url": clip.get("url", ""),
                                "game_name": clip.get("game_name", ""),
                                "broadcaster_id": broadcaster_id,
                                "broadcaster": cfg.get("broadcaster_name", ""),  # Use actual broadcaster, not clip creator
                                "editor_id": broadcaster_id,
                            }
                            twitch_item_data[item_id] = clip_data
                            clip_id = str(clip.get("clip_id", "")).strip()
                            if clip_id:
                                twitch_item_by_clip_id[clip_id] = item_id

                        _auto_resize_columns(twitch_tree)

                    var_twitch_progress.set("")
                    var_twitch_progress_value.set(0)

                win.after(0, _update_ui)

            except Exception as exc:
                # Exception variables are cleared after the except block in Python 3,
                # so capture the message before scheduling the deferred UI callback.
                err_text = str(exc)

                def _error_ui(error_text=err_text):
                    messagebox.showerror(_t("error_title"), _t("fetch_clips_failed", error=error_text), parent=win)
                    var_twitch_progress.set("")
                    var_twitch_progress_value.set(0)
                    twitch_item_data.clear()
                    twitch_item_by_clip_id.clear()
                    for item in twitch_tree.get_children():
                        twitch_tree.delete(item)
                    app_logs.log_error(_t("tab_twitch_clips"), error_text)

                win.after(0, _error_ui)

            finally:
                twitch_fetch_running[0] = False
                btn_twitch_refresh.config(state="normal")
                btn_twitch_download.config(state="normal")
                btn_twitch_delete.config(state="normal")

        threading.Thread(target=_worker, daemon=True, name="twitch-clips-fetch-worker").start()

    twitch_btns_top = tk.Frame(tab_twitch_clips)
    twitch_btns_top.pack(fill="x", padx=10, pady=(0, 4))
    btn_twitch_refresh = tk.Button(twitch_btns_top, text=_t("refresh"), command=lambda: _load_twitch_clips(force=True))
    btn_twitch_refresh.pack(side="left")
    btn_twitch_download = tk.Button(twitch_btns_top, text=_t("download_selected"), command=_download_twitch_clips)
    btn_twitch_download.pack(side="left", padx=6)
    btn_twitch_rename = tk.Button(twitch_btns_top, text=_t("rename_selected"), command=lambda: _rename_twitch_clips())
    btn_twitch_rename.pack(side="left", padx=6)
    btn_twitch_delete = tk.Button(twitch_btns_top, text=_t("delete_selected_twitch"), command=_delete_twitch_clips)
    btn_twitch_delete.pack(side="left")

    twitch_btns_link = tk.Frame(tab_twitch_clips)
    twitch_btns_link.pack(fill="x", padx=10, pady=(0, 4))
    tk.Button(twitch_btns_link, text=_t("open_twitch_link"), command=_open_twitch_link).pack(side="left")

    twitch_progress_frame = tk.Frame(tab_twitch_clips)
    twitch_progress_frame.pack(fill="x", padx=10, pady=(0, 8))
    twitch_progress_bar = ttk.Progressbar(
        twitch_progress_frame,
        orient="horizontal",
        mode="determinate",
        maximum=1,
        variable=var_twitch_progress_value,
    )
    twitch_progress_bar.pack(fill="x")
    tk.Label(twitch_progress_frame, textvariable=var_twitch_progress, anchor="w", fg="gray").pack(fill="x", pady=(2, 0))

    def _on_tab_changed(_event=None):
        selected_tab = notebook.nametowidget(notebook.select())
        if selected_tab == tab_session_log:
            _load_session_log(force=True)
        elif selected_tab == tab_library:
            _load_clip_library(force=True)
        elif selected_tab == tab_twitch_clips:
            _load_twitch_clips(force=True)

    notebook.bind("<<NotebookTabChanged>>", _on_tab_changed)

    def _on_log_event(event_type: str):
        def _apply_update():
            try:
                if event_type == "session":
                    _load_session_log()
                elif event_type == "clip_library":
                    _load_clip_library()
            except tk.TclError:
                return
        try:
            win.after(0, _apply_update)
        except tk.TclError:
            return

    app_logs.register_listener(_on_log_event)

    _load_session_log(force=True)
    _load_clip_library(force=True)

    # ── Import / Export tab ────────────────────────────────────────────────
    tk.Label(
        tab_import_export,
        text=_t("settings_import_export_desc"),
        fg="gray",
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=10, pady=(10, 6))

    def _selected_popup_display_index() -> int:
        selected_display_label = var_popup_display_label.get().strip()
        for i, label in enumerate(display_labels):
            if label == selected_display_label:
                return i
        return 0

    def _build_form_settings_dict() -> dict:
        parsed_duration = _parse_duration_or_none()
        return {
            "client_id": var_client_id.get().strip(),
            "client_secret": var_client_secret.get().strip(),
            "access_token": var_token.get().strip(),
            "broadcaster_name": var_broadcaster.get().strip(),
            "hotkey": var_hotkey.get().strip(),
            "clip_duration": parsed_duration if parsed_duration is not None else int(cfg.get("clip_duration", 30)),
            "clip_title_template": var_template.get().strip() or "{datetime}_{game}-{title}",
            "download_folder": var_folder.get().strip(),
            "auto_download": bool(var_auto_download.get()),
            "popup_enabled": bool(var_popup_enabled.get()),
            "popup_display": int(_selected_popup_display_index()),
            "popup_position": var_popup_position.get().strip() or "bottom-right",
            "popup_opacity": max(0.2, min(1.0, float(var_popup_opacity_pct.get()) / 100.0)),
            "popup_info_duration_ms": max(1000, int(var_popup_info_sec.get()) * 1000),
            "popup_error_duration_ms": max(1000, int(var_popup_error_sec.get()) * 1000),
            "language": language_map.get(var_language.get(), "auto"),
            "refresh_token": cfg.get("refresh_token", ""),
            "broadcaster_id": cfg.get("broadcaster_id", ""),
        }

    def _export_settings_file():
        data = dict(config.DEFAULTS)
        data.update(_build_form_settings_dict())
        # Never export sensitive fields.
        for key in ("client_id", "client_secret", "access_token", "refresh_token"):
            data.pop(key, None)
        target_path = filedialog.asksaveasfilename(
            parent=win,
            title=_t("export_settings_title"),
            initialfile="twitchclipper_settings.json",
            defaultextension=".json",
            filetypes=[
                (_t("settings_json_files"), "*.json"),
                (_t("all_files"), "*.*"),
            ],
        )
        if not target_path:
            return
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo(_t("export"), _t("export_to", path=target_path), parent=win)
            app_logs.log_action(_t("log_settings_exported"), target_path)
        except OSError as exc:
            messagebox.showerror(_t("save_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_settings_export"), str(exc))

    def _normalize_imported_settings(raw: dict, current: dict) -> dict:
        # Start from current settings so imports without sensitive keys do not wipe auth.
        data = dict(config.DEFAULTS)
        data.update(current)
        for key, value in raw.items():
            if key in data:
                data[key] = value

        try:
            data["clip_duration"] = int(data.get("clip_duration", 30))
        except Exception:
            data["clip_duration"] = 30
        data["clip_duration"] = max(5, min(60, data["clip_duration"]))

        try:
            data["popup_display"] = int(data.get("popup_display", 0))
        except Exception:
            data["popup_display"] = 0

        try:
            data["popup_opacity"] = float(data.get("popup_opacity", 0.95))
        except Exception:
            data["popup_opacity"] = 0.95
        data["popup_opacity"] = max(0.2, min(1.0, data["popup_opacity"]))

        try:
            data["popup_info_duration_ms"] = int(data.get("popup_info_duration_ms", 3000))
        except Exception:
            data["popup_info_duration_ms"] = 3000
        try:
            data["popup_error_duration_ms"] = int(data.get("popup_error_duration_ms", 6000))
        except Exception:
            data["popup_error_duration_ms"] = 6000
        data["popup_info_duration_ms"] = max(1000, data["popup_info_duration_ms"])
        data["popup_error_duration_ms"] = max(1000, data["popup_error_duration_ms"])

        data["auto_download"] = bool(data.get("auto_download", True))
        data["popup_enabled"] = bool(data.get("popup_enabled", True))

        data["language"] = str(data.get("language", "auto")).strip().lower()
        if data["language"] not in ("auto", "en", "de"):
            data["language"] = "auto"

        data["hotkey"] = str(data.get("hotkey", "ctrl+shift+c")).strip()
        data["broadcaster_name"] = str(data.get("broadcaster_name", "")).strip()
        data["client_id"] = str(data.get("client_id", "")).strip()
        data["client_secret"] = str(data.get("client_secret", "")).strip()
        data["access_token"] = str(data.get("access_token", "")).strip()
        data["refresh_token"] = str(data.get("refresh_token", "")).strip()
        data["clip_title_template"] = str(data.get("clip_title_template", "{datetime}_{game}-{title}")).strip() or "{datetime}_{game}-{title}"
        data["download_folder"] = str(data.get("download_folder", "")).strip()
        data["popup_position"] = str(data.get("popup_position", "bottom-right")).strip() or "bottom-right"
        data["broadcaster_id"] = str(data.get("broadcaster_id", "")).strip()

        return data

    def _import_settings_file():
        source_path = filedialog.askopenfilename(
            parent=win,
            title=_t("import_settings_title"),
            filetypes=[
                (_t("settings_json_files"), "*.json"),
                (_t("all_files"), "*.*"),
            ],
        )
        if not source_path:
            return

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            messagebox.showerror(_t("import_settings_title"), _t("import_invalid_json", error=exc), parent=win)
            app_logs.log_error(_t("log_settings_import"), str(exc))
            return
        except OSError as exc:
            messagebox.showerror(_t("import_settings_title"), str(exc), parent=win)
            app_logs.log_error(_t("log_settings_import"), str(exc))
            return

        if not isinstance(raw, dict):
            messagebox.showerror(_t("import_settings_title"), _t("import_not_object"), parent=win)
            return

        imported_cfg = _normalize_imported_settings(raw, cfg)

        try:
            config.save(imported_cfg)
        except RuntimeError as exc:
            messagebox.showerror(_t("save_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_settings_import"), str(exc))
            return

        app_logs.log_action(_t("log_settings_imported"), source_path)
        hotkey_listener.register(imported_cfg)
        if on_saved:
            on_saved(imported_cfg)
        tray.refresh_menu_labels()
        messagebox.showinfo(_t("saved"), _t("import_settings_done"), parent=win)

        app_logs.unregister_listener(_on_log_event)
        global _window
        _window = None
        win.destroy()
        root.after(0, lambda: open_settings(root, on_saved=on_saved, on_exit_app=on_exit_app))

    io_buttons = tk.Frame(tab_import_export)
    io_buttons.pack(fill="x", padx=10, pady=(2, 10))
    tk.Button(io_buttons, text=_t("export_settings"), command=_export_settings_file, width=16).pack(side="left")
    tk.Button(io_buttons, text=_t("import_settings"), command=_import_settings_file, width=16).pack(side="left", padx=8)

    # ── Auth tab ─────────────────────────────────────────────────────────────
    tk.Label(
        tab_auth,
        text=_t("register_app_at"),
        justify="left",
        fg="gray",
    ).grid(row=0, column=0, sticky="w", **pad)

    app_link = tk.Label(
        tab_auth,
        text="dev.twitch.tv",
        fg="#1a73e8",
        cursor="hand2",
    )
    app_link.grid(row=0, column=1, sticky="w", **pad)
    app_link.bind("<Button-1>", lambda _e: webbrowser.open_new("https://dev.twitch.tv/console/apps/create"))

    tk.Label(tab_auth, text=_t("oauth_redirect_url"), anchor="w", width=label_w).grid(
        row=1, column=0, sticky="w", **pad
    )
    redirect_var = tk.StringVar(value=auth.REDIRECT_URI)
    redirect_entry = tk.Entry(tab_auth, textvariable=redirect_var, width=40, state="readonly")
    redirect_entry.grid(row=1, column=1, sticky="ew", **pad)

    def _copy_redirect_url():
        win.clipboard_clear()
        win.clipboard_append(redirect_var.get())
        messagebox.showinfo(_t("copied"), _t("copied_redirect"), parent=win)

    tk.Button(tab_auth, text=_t("copy"), command=_copy_redirect_url, width=8).grid(
        row=1, column=2, sticky="w", padx=4, pady=4
    )

    var_client_id = tk.StringVar(value=cfg.get("client_id", ""))
    var_client_secret = tk.StringVar(value=cfg.get("client_secret", ""))
    var_token = tk.StringVar(value=cfg.get("access_token", ""))
    auth_status = tk.StringVar(value="")
    auth_expiry_status = tk.StringVar(value="")

    def _format_duration(seconds: int) -> str:
        seconds = max(0, int(seconds))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def _format_local_timestamp(epoch_seconds: int) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(epoch_seconds)))
        except Exception:
            return "?"

    def _set_token_expiry_from_expires_in(expires_in: int | str | None) -> None:
        try:
            expires = int(expires_in or 0)
        except Exception:
            expires = 0
        cfg["token_expires_at"] = int(time.time()) + expires if expires > 0 else 0

    def _update_auth_expiry_label() -> None:
        expires_at = int(cfg.get("token_expires_at", 0) or 0)
        if not expires_at:
            auth_expiry_status.set(_t("token_expiry_unknown"))
            return
        now = int(time.time())
        if expires_at <= now:
            auth_expiry_status.set(_t("token_expired_at", when=_format_local_timestamp(expires_at)))
            return
        remaining = expires_at - now
        auth_expiry_status.set(
            _t(
                "token_expires_at",
                when=_format_local_timestamp(expires_at),
                remaining=_format_duration(remaining),
            )
        )

    login_flow_frame = tk.Frame(tab_auth)
    login_flow_frame.grid(row=2, column=0, columnspan=3, sticky="ew")

    logged_in_frame = tk.Frame(tab_auth)
    tk.Label(logged_in_frame, textvariable=auth_status, fg="green", anchor="w").grid(
        row=0, column=0, sticky="w", **pad
    )
    tk.Label(logged_in_frame, textvariable=auth_expiry_status, fg="gray", anchor="w").grid(
        row=1, column=0, sticky="w", **pad
    )

    def _logout():
        var_token.set("")
        cfg["access_token"] = ""
        cfg["refresh_token"] = ""
        cfg["token_expires_at"] = 0
        auth_status.set(_t("not_logged_in"))
        _update_auth_expiry_label()
        logged_in_frame.grid_remove()
        login_flow_frame.grid()
        try:
            config.save(cfg)
        except RuntimeError as exc:
            messagebox.showerror(_t("save_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_logged_out"), str(exc))
        app_logs.log_action(_t("log_logged_out"))

    def _check_token_status():
        token = str(cfg.get("access_token", "")).strip()
        client_id = var_client_id.get().strip() or str(cfg.get("client_id", "")).strip()
        if not token or not client_id:
            messagebox.showerror(_t("missing"), _t("missing_id_token"), parent=win)
            return
        try:
            info = auth.validate_manual_token(token, client_id)
            _set_token_expiry_from_expires_in(info.get("expires_in", 0))
            _update_auth_expiry_label()
            config.save(cfg)
            messagebox.showinfo(_t("success"), _t("token_status_updated"), parent=win)
        except Exception as exc:
            messagebox.showerror(_t("invalid_token"), str(exc), parent=win)

    def _refresh_token_manual():
        client_id = var_client_id.get().strip() or str(cfg.get("client_id", "")).strip()
        client_secret = var_client_secret.get().strip() or str(cfg.get("client_secret", "")).strip()
        refresh_token = str(cfg.get("refresh_token", "")).strip()

        if not refresh_token:
            messagebox.showerror(_t("invalid_token"), _t("missing_refresh_token"), parent=win)
            return
        if not client_id or not client_secret:
            messagebox.showerror(_t("missing"), _t("missing_id_secret"), parent=win)
            return

        try:
            new_tokens = twitch_api.refresh_access_token(client_id, client_secret, refresh_token)
            new_access_token = str(new_tokens.get("access_token", "")).strip()
            if not new_access_token:
                raise RuntimeError(_t("token_refresh_empty_access"))

            cfg["access_token"] = new_access_token
            if new_tokens.get("refresh_token"):
                cfg["refresh_token"] = str(new_tokens.get("refresh_token", "")).strip()
            _set_token_expiry_from_expires_in(new_tokens.get("expires_in", 0))
            var_token.set(new_access_token)

            try:
                info = auth.validate_manual_token(new_access_token, client_id)
                auth_status.set(_t("logged_in_as", user=info.get("login", "?")))
            except Exception:
                auth_status.set(_t("logged_in"))

            _update_auth_expiry_label()
            config.save(cfg)
            app_logs.log_action(_t("log_access_token_refreshed"))
            messagebox.showinfo(_t("success"), _t("token_refreshed_success"), parent=win)
        except Exception as exc:
            messagebox.showerror(_t("invalid_token"), _t("token_refresh_failed", error=exc), parent=win)
            app_logs.log_error(_t("log_token_refresh"), str(exc))

    tk.Button(logged_in_frame, text=_t("check_token_status"), command=_check_token_status, width=18).grid(
        row=2, column=0, sticky="w", padx=10, pady=(0, 4)
    )

    tk.Button(logged_in_frame, text=_t("refresh_token_now"), command=_refresh_token_manual, width=18).grid(
        row=3, column=0, sticky="w", padx=10, pady=(0, 4)
    )

    tk.Button(logged_in_frame, text=_t("logout"), command=_logout, width=12).grid(
        row=4, column=0, sticky="w", padx=10, pady=4
    )

    _row(login_flow_frame, _t("client_id"), lambda p: tk.Entry(p, textvariable=var_client_id, width=40), 0)
    _row(login_flow_frame, _t("client_secret"), lambda p: tk.Entry(p, textvariable=var_client_secret, show="*", width=40), 1)

    def _browser_login():
        cid = var_client_id.get().strip()
        csec = var_client_secret.get().strip()
        if not cid or not csec:
            messagebox.showerror(_t("missing"), _t("missing_id_secret"), parent=win)
            app_logs.log_error(_t("log_browser_login"), _t("log_browser_login_missing"))
            return
        try:
            tokens = auth.start_oauth_browser_flow(cid, csec)
            var_token.set(tokens["access_token"])
            cfg["access_token"] = tokens["access_token"]
            cfg["refresh_token"] = tokens.get("refresh_token", "")
            _set_token_expiry_from_expires_in(tokens.get("expires_in", 0))
            auth_status.set(_t("logged_in"))
            _update_auth_expiry_label()
            login_flow_frame.grid_remove()
            logged_in_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
            try:
                config.save(cfg)
            except RuntimeError as save_exc:
                messagebox.showerror(_t("save_failed"), str(save_exc), parent=win)
                app_logs.log_error(_t("log_browser_login"), str(save_exc))
            app_logs.log_action(_t("log_logged_in"), _t("log_logged_in_browser"))
        except Exception as exc:
            messagebox.showerror(_t("login_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_browser_login"), str(exc))

    tk.Button(login_flow_frame, text=_t("login_via_browser"), command=_browser_login).grid(
        row=2, column=0, columnspan=2, pady=6
    )

    tk.Label(login_flow_frame, text=f"- {_t('paste_token_manual')} -", fg="gray").grid(
        row=3, column=0, columnspan=2
    )
    _row(login_flow_frame, _t("access_token"), lambda p: tk.Entry(p, textvariable=var_token, show="*", width=40), 4)

    def _validate_token():
        tok = var_token.get().strip()
        cid = var_client_id.get().strip()
        if not tok or not cid:
            messagebox.showerror(_t("missing"), _t("missing_id_token"), parent=win)
            app_logs.log_error(_t("log_token_validation"), _t("log_token_validation_missing"))
            return
        try:
            info = auth.validate_manual_token(tok, cid)
            cfg["access_token"] = tok
            _set_token_expiry_from_expires_in(info.get("expires_in", 0))
            auth_status.set(_t("logged_in_as", user=info.get("login", "?")))
            _update_auth_expiry_label()
            login_flow_frame.grid_remove()
            logged_in_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
            try:
                config.save(cfg)
            except RuntimeError as save_exc:
                messagebox.showerror(_t("save_failed"), str(save_exc), parent=win)
                app_logs.log_error(_t("log_token_validation"), str(save_exc))
            app_logs.log_action(_t("log_logged_in"), _t("log_logged_in_manual", user=info.get('login', '?')))
        except PermissionError as exc:
            if "401" in str(exc) or "invalid or expired" in str(exc).lower():
                # Token is expired/invalid, try to refresh if we have a refresh token
                if cfg.get("refresh_token") and var_client_secret.get().strip():
                    if hotkey_listener.try_refresh_token(cfg):
                        # Update UI with refreshed token
                        var_token.set(cfg.get("access_token", ""))
                        try:
                            info = auth.validate_manual_token(cfg["access_token"], cid)
                            _set_token_expiry_from_expires_in(info.get("expires_in", 0))
                            auth_status.set(_t("logged_in_as", user=info.get("login", "?")))
                            _update_auth_expiry_label()
                            login_flow_frame.grid_remove()
                            logged_in_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
                            config.save(cfg)
                            messagebox.showinfo(_t("success"), _t("token_refreshed_success"), parent=win)
                            app_logs.log_action(_t("log_logged_in"), _t("log_logged_in_manual", user=info.get('login', '?')))
                            return
                        except Exception as validate_exc:
                            messagebox.showerror(_t("invalid_token"), str(validate_exc), parent=win)
                            app_logs.log_error(_t("log_token_validation"), str(validate_exc))
                            return
                    else:
                        messagebox.showerror(_t("invalid_token"), "Token expired and refresh failed. Please get a new token.", parent=win)
                        app_logs.log_error(_t("log_token_validation"), "Token expired, refresh failed")
                        return
                else:
                    messagebox.showerror(_t("invalid_token"), str(exc), parent=win)
                    app_logs.log_error(_t("log_token_validation"), str(exc))
            else:
                messagebox.showerror(_t("invalid_token"), str(exc), parent=win)
                app_logs.log_error(_t("log_token_validation"), str(exc))
        except Exception as exc:
            messagebox.showerror(_t("invalid_token"), str(exc), parent=win)
            app_logs.log_error(_t("log_token_validation"), str(exc))

    tk.Button(login_flow_frame, text=_t("validate_token"), command=_validate_token).grid(
        row=5, column=0, columnspan=2, pady=4
    )

    if var_token.get().strip():
        auth_status.set(_t("logged_in"))
        _update_auth_expiry_label()
        login_flow_frame.grid_remove()
        logged_in_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
    tab_auth.columnconfigure(1, weight=1)

    # ── Clip tab ──────────────────────────────────────────────────────────────
    var_broadcaster = tk.StringVar(value=cfg.get("broadcaster_name", ""))
    var_hotkey = tk.StringVar(value=cfg.get("hotkey", "ctrl+shift+c"))
    try:
        _initial_duration = int(cfg.get("clip_duration", 30))
    except Exception:
        _initial_duration = 30
    var_duration = tk.StringVar(value=str(_initial_duration))
    var_template = tk.StringVar(value=cfg.get("clip_title_template", "{datetime}_{game}-{title}"))
    var_folder = tk.StringVar(value=cfg.get("download_folder", ""))
    var_auto_download = tk.BooleanVar(value=bool(cfg.get("auto_download", True)))

    def _parse_duration_or_none() -> int | None:
        raw = str(var_duration.get()).strip()
        if not raw or not raw.isdigit():
            return None
        return int(raw)

    def _validate_duration_input(proposed: str) -> bool:
        # Allow only digits while typing; final range is validated on save.
        return proposed == "" or proposed.isdigit()

    _row(tab_clip, _t("broadcaster_name"), lambda p: tk.Entry(p, textvariable=var_broadcaster, width=30), 0)

    def _test_connection():
        tok = var_token.get().strip()
        cid = var_client_id.get().strip()
        name = var_broadcaster.get().strip()
        if not all([tok, cid, name]):
            messagebox.showerror(_t("missing"), _t("missing_test_connection"), parent=win)
            app_logs.log_error(_t("log_test_connection"), _t("log_test_connection_missing"))
            return
        try:
            bid = twitch_api.get_broadcaster_id(name, tok, cid)
            cfg["broadcaster_id"] = bid
            messagebox.showinfo(_t("connected"), _t("connected_msg", name=name, bid=bid), parent=win)
            app_logs.log_action(_t("log_connection_test_success"), _t("connected_msg", name=name, bid=bid))
        except PermissionError as exc:
            if "401" in str(exc):
                # Token might be expired, try to refresh
                if hotkey_listener.try_refresh_token(cfg):
                    try:
                        # Retry with refreshed token
                        bid = twitch_api.get_broadcaster_id(name, cfg.get("access_token", ""), cid)
                        cfg["broadcaster_id"] = bid
                        messagebox.showinfo(_t("connected"), _t("connected_msg", name=name, bid=bid), parent=win)
                        app_logs.log_action(_t("log_connection_test_success"), _t("connected_msg", name=name, bid=bid))
                        return
                    except Exception as retry_exc:
                        messagebox.showerror(_t("connection_failed"), str(retry_exc), parent=win)
                        app_logs.log_error(_t("log_test_connection"), str(retry_exc))
                        return
                else:
                    messagebox.showerror(_t("connection_failed"), str(exc), parent=win)
                    app_logs.log_error(_t("log_test_connection"), str(exc))
            else:
                messagebox.showerror(_t("connection_failed"), str(exc), parent=win)
                app_logs.log_error(_t("log_test_connection"), str(exc))
        except Exception as exc:
            messagebox.showerror(_t("connection_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_test_connection"), str(exc))

    tk.Button(tab_clip, text=_t("test_connection"), command=_test_connection).grid(
        row=1, column=0, columnspan=2, pady=4
    )

    # Hotkey capture
    hotkey_frame = tk.Frame(tab_clip)
    hotkey_entry = tk.Entry(hotkey_frame, textvariable=var_hotkey, width=20, state="readonly")
    hotkey_entry.pack(side="left", padx=(0, 4))

    _capturing = [False]
    _pressed = [set()]
    _capture_btn = [None]

    def _start_capture():
        _capturing[0] = True
        _pressed[0] = set()
        var_hotkey.set(_t("press_keys"))
        hotkey_entry.config(state="normal")
        _capture_btn[0].config(text=_t("cancel"), command=_cancel_capture)
        win.bind("<KeyPress>", _on_key_press)
        win.bind("<KeyRelease>", _on_key_release)

    def _cancel_capture():
        _capturing[0] = False
        var_hotkey.set(cfg.get("hotkey", "ctrl+shift+c"))
        hotkey_entry.config(state="readonly")
        _capture_btn[0].config(text=_t("capture"), command=_start_capture)
        win.unbind("<KeyPress>")
        win.unbind("<KeyRelease>")

    def _on_key_press(event):
        if not _capturing[0]:
            return
        key = event.keysym.lower()
        _pressed[0].add(key)

    def _on_key_release(event):
        if not _capturing[0] or not _pressed[0]:
            return
        _capturing[0] = False
        mods = []
        main = []
        for k in sorted(_pressed[0]):
            if k in ("control_l", "control_r", "ctrl"):
                mods.insert(0, "ctrl")
            elif k in ("shift_l", "shift_r", "shift"):
                mods.append("shift")
            elif k in ("alt_l", "alt_r", "alt"):
                mods.append("alt")
            else:
                main.append(k)
        combo = "+".join(mods + main)
        var_hotkey.set(combo)
        hotkey_entry.config(state="readonly")
        _capture_btn[0].config(text=_t("capture"), command=_start_capture)
        win.unbind("<KeyPress>")
        win.unbind("<KeyRelease>")

    btn_capture = tk.Button(hotkey_frame, text=_t("capture"), command=_start_capture)
    btn_capture.pack(side="left")
    _capture_btn[0] = btn_capture
    hotkey_frame.grid(row=2, column=1, sticky="w", **{"padx": 10, "pady": 4})
    tk.Label(tab_clip, text=_t("hotkey"), anchor="w", width=label_w).grid(
        row=2, column=0, sticky="w", **{"padx": 10, "pady": 4}
    )

    # Duration
    dur_frame = tk.Frame(tab_clip)
    _dur_validate_cmd = (win.register(_validate_duration_input), "%P")
    tk.Spinbox(
        dur_frame,
        from_=5,
        to=60,
        textvariable=var_duration,
        width=5,
        validate="key",
        validatecommand=_dur_validate_cmd,
    ).pack(side="left")
    tk.Label(dur_frame, text=_t("duration_hint")).pack(side="left", padx=4)
    dur_frame.grid(row=3, column=1, sticky="w", **{"padx": 10, "pady": 4})
    tk.Label(tab_clip, text=_t("clip_duration"), anchor="w", width=label_w).grid(
        row=3, column=0, sticky="w", **{"padx": 10, "pady": 4}
    )

    # Title template
    _row(tab_clip, _t("title_template"), lambda p: tk.Entry(p, textvariable=var_template, width=40), 4)
    tk.Label(
        tab_clip,
        text=_t("tokens_hint"),
        fg="gray",
        font=("TkDefaultFont", 8),
    ).grid(row=5, column=0, columnspan=2, sticky="w", padx=10)

    # Download folder
    def _browse_folder():
        folder = filedialog.askdirectory(parent=win, title=_t("select_download_folder"))
        if folder:
            var_folder.set(folder)

    folder_frame = tk.Frame(tab_clip)
    tk.Entry(folder_frame, textvariable=var_folder, width=28).pack(side="left")
    tk.Button(folder_frame, text=_t("browse"), command=_browse_folder).pack(side="left", padx=4)
    folder_frame.grid(row=6, column=1, sticky="w", **{"padx": 10, "pady": 4})
    tk.Label(tab_clip, text=_t("download_folder"), anchor="w", width=label_w).grid(
        row=6, column=0, sticky="w", **{"padx": 10, "pady": 4}
    )

    _row(tab_clip, _t("auto_download"), lambda p: tk.Checkbutton(p, variable=var_auto_download), 7)

    tab_clip.columnconfigure(1, weight=1)

    # ── Save button ───────────────────────────────────────────────────────────
    def _save():
        dur = _parse_duration_or_none()
        if dur is None or not (5 <= dur <= 60):
            messagebox.showerror(_t("invalid"), _t("invalid_duration"), parent=win)
            return
        old_cfg = dict(cfg)
        old_lang_setting = str(cfg.get("language", "auto")).strip().lower()
        new_values = _build_form_settings_dict()
        new_values["clip_duration"] = dur
        new_lang_setting = str(new_values.get("language", "auto")).strip().lower()
        cfg.update(new_values)
        try:
            config.save(cfg)
        except RuntimeError as exc:
            messagebox.showerror(_t("save_failed"), str(exc), parent=win)
            app_logs.log_error(_t("log_save_settings"), str(exc))
            return

        def _value_for_log(key: str, value):
            if key == "language":
                lang_value = str(value).strip().lower()
                if lang_value == "auto":
                    return _t("lang_auto_detected", language=detected_lang_label)
                return reverse_language_map.get(lang_value, str(value))
            if key == "popup_display":
                idx = int(value) if str(value).isdigit() else -1
                if 0 <= idx < len(display_labels):
                    return display_labels[idx]
                return str(value)
            if key == "popup_opacity":
                try:
                    return f"{int(round(float(value) * 100))}%"
                except Exception:
                    return str(value)
            if key in ("popup_info_duration_ms", "popup_error_duration_ms"):
                try:
                    return f"{int(value) // 1000}s"
                except Exception:
                    return str(value)
            if isinstance(value, bool):
                return "on" if value else "off"
            return str(value)

        setting_labels = {
            "broadcaster_name": _t("broadcaster_name").rstrip(":"),
            "hotkey": _t("hotkey").rstrip(":"),
            "clip_duration": _t("clip_duration").rstrip(":"),
            "clip_title_template": _t("title_template").rstrip(":"),
            "download_folder": _t("download_folder").rstrip(":"),
            "auto_download": _t("auto_download").rstrip(":"),
            "popup_enabled": _t("enable_popups").rstrip(":"),
            "popup_display": _t("screen").rstrip(":"),
            "popup_position": _t("position").rstrip(":"),
            "popup_opacity": _t("opacity").rstrip(":"),
            "popup_info_duration_ms": _t("info_duration").rstrip(":"),
            "popup_error_duration_ms": _t("error_duration").rstrip(":"),
            "language": _t("lang_label").rstrip(":"),
        }
        for key in setting_labels:
            old_val = old_cfg.get(key)
            new_val = cfg.get(key)
            if old_val != new_val:
                app_logs.log_action(
                    _t("log_setting_changed"),
                    f'{setting_labels[key]}: "{_value_for_log(key, old_val)}" -> "{_value_for_log(key, new_val)}"',
                )

        app_logs.log_action(_t("log_settings_saved"))
        hotkey_listener.register(cfg)
        if on_saved:
            on_saved(cfg)
        tray.refresh_menu_labels()
        messagebox.showinfo(_t("saved"), _t("saved_msg"), parent=win)

        # Rebuild settings immediately so language switch applies without app restart.
        if old_lang_setting != new_lang_setting:
            app_logs.unregister_listener(_on_log_event)
            global _window
            _window = None
            win.destroy()
            root.after(0, lambda: open_settings(root, on_saved=on_saved, on_exit_app=on_exit_app))
            return

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill="x", padx=8, pady=8)
    def _close_app():
        app_logs.unregister_listener(_on_log_event)
        if on_exit_app:
            on_exit_app()
        else:
            win.destroy()

    tk.Button(btn_frame, text=_t("close_app"), command=_close_app, width=12).pack(side="left", padx=4)
    tk.Button(btn_frame, text=_t("save"), command=_save, width=12).pack(side="right", padx=4)
    tk.Button(btn_frame, text=_t("cancel"), command=win.destroy, width=8).pack(side="right")

    def _on_close():
        global _window
        app_logs.unregister_listener(_on_log_event)
        _window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.after(1, lambda: win.update())
    return win
