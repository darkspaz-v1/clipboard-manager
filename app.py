import json
import msvcrt
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

import keyboard
import pyperclip
import pystray
from PIL import ImageTk

from history import History
from icon import app_icon
from popup import ClipPopup

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"
LOCK_PATH = APP_DIR / ".singleton.lock"
SHOW_SIGNAL_PATH = APP_DIR / ".show_signal"
_lock_file = None


def _acquire_single_instance_lock():
    """Best-effort single-instance guard via an exclusive OS file lock (stdlib
    msvcrt, Windows-only, no extra dependency). Held for the process's lifetime;
    a second launch fails to acquire it and exits immediately instead of spawning
    a duplicate tray icon, hotkey registration, and clipboard poll loop. Before
    exiting, it drops a signal file so the already-running instance shows its
    popup - otherwise launching an already-running app (e.g. from the Launcher)
    silently does nothing, which is indistinguishable from being broken."""
    global _lock_file
    f = open(LOCK_PATH, "a+b")
    if f.tell() == 0:
        f.write(b"0")
        f.flush()
    f.seek(0)
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        try:
            SHOW_SIGNAL_PATH.touch()
        except OSError:
            pass
        return False
    _lock_file = f
    return True

DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+shift+v",
    "max_history": 500,
    "poll_interval_seconds": 0.5,
    "popup_max_results": 200,
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except FileNotFoundError:
        pass
    return config


class ClipboardManagerApp:
    def __init__(self):
        self.config = load_config()
        self.history = History(max_entries=self.config["max_history"])
        self.root = tk.Tk()
        self.root.withdraw()
        self._icon_photo = ImageTk.PhotoImage(app_icon())
        self.root.iconphoto(True, self._icon_photo)
        self.popup = ClipPopup(self.root, self.history, self.on_select, self.config["popup_max_results"])
        self._last_seen = None
        self._stop = threading.Event()
        self.icon = None

        # The clipboard poller, the global-hotkey callback, and the tray icon all run
        # on their own threads and must never touch Tk directly. They post callables
        # here instead; only this queue drain (scheduled via after(), so it always
        # runs on the Tk main thread) actually calls into Tk.
        self._ui_queue = queue.Queue()
        self.root.after(50, self._drain_ui_queue)

    def _drain_ui_queue(self):
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        if SHOW_SIGNAL_PATH.exists():
            try:
                SHOW_SIGNAL_PATH.unlink()
            except OSError:
                pass
            self.popup.show()
        self.root.after(50, self._drain_ui_queue)

    def _post(self, fn):
        self._ui_queue.put(fn)

    def on_select(self, text):
        pyperclip.copy(text)
        self._last_seen = text

    def poll_clipboard(self):
        try:
            self._last_seen = pyperclip.paste()
        except Exception:
            self._last_seen = None
        while not self._stop.is_set():
            time.sleep(self.config["poll_interval_seconds"])
            try:
                current = pyperclip.paste()
            except Exception:
                continue
            if current and current != self._last_seen:
                self._last_seen = current
                self.history.add(current)

    def show_popup(self):
        self._post(self.popup.show)

    def clear_history(self, icon=None, item=None):
        self.history.clear()

    def quit_app(self, icon=None, item=None):
        self._stop.set()
        try:
            keyboard.remove_hotkey(self.config["hotkey"])
        except Exception:
            pass
        if self.icon:
            self.icon.stop()
        self._post(self.root.quit)

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem(
                f"Open History  ({self.config['hotkey']})",
                lambda icon, item: self.show_popup(),
                default=True,
            ),
            pystray.MenuItem("Clear History", self.clear_history),
            pystray.MenuItem("Quit", self.quit_app),
        )
        self.icon = pystray.Icon("clipboard-manager", app_icon(), "Clipboard Manager", menu)

        threading.Thread(target=self.poll_clipboard, daemon=True).start()
        threading.Thread(target=self.icon.run, daemon=True).start()

        try:
            keyboard.add_hotkey(self.config["hotkey"], self.show_popup)
        except Exception as e:
            print(f"Warning: could not register hotkey {self.config['hotkey']}: {e}")

        self.root.mainloop()


def main():
    if not _acquire_single_instance_lock():
        return
    app = ClipboardManagerApp()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        with open(APP_DIR / "app_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.ctime()} ---\n")
            f.write(traceback.format_exc())
        raise
