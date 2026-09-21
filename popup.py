import tkinter as tk
from datetime import datetime, timezone

from history import filter_clips

INK = "#12131C"
PANEL_SELECTED = "#20263E"
HAIRLINE = "#2E3044"
TEXT = "#EDEEF7"
MUTED = "#8688A6"
ACCENT = "#5B8DEF"
DANGER = "#F0576B"

RENDER_CAP = 40  # cap rendered rows for snappy re-filtering; DB fetch cap is separate


def _relative_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d")


def _preview(text, limit=140):
    p = text.replace("\n", " ")
    p = " ".join(p.split())
    return p[:limit] + "…" if len(p) > limit else p


class ClipPopup:
    """Simple dark popup listing recent clips. Enter/click copies and closes."""

    WIDTH = 560
    HEIGHT = 460

    def __init__(self, root, history, on_select, max_results=200):
        self.root = root
        self.history = history
        self.on_select = on_select
        self.max_results = max_results
        self.win = None
        self._all_items = []
        self._filtered = []
        self._selected = 0
        self._row_widgets = []
        self._drag_x = 0
        self._drag_y = 0

    def show(self):
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=INK, highlightthickness=1, highlightbackground=HAIRLINE)
        self.win.bind("<Escape>", lambda e: self._close())
        self.win.bind("<MouseWheel>", self._on_mousewheel)

        self._build_chrome()
        self._all_items = self.history.recent(self.max_results)
        self._refresh()
        self._position()

        self.win.deiconify()
        self.win.focus_force()
        self.entry.focus_set()

    def _build_chrome(self):
        header = tk.Frame(self.win, bg=INK)
        header.pack(fill="x", padx=16, pady=(14, 8))
        header.bind("<ButtonPress-1>", self._start_drag)
        header.bind("<B1-Motion>", self._do_drag)

        title = tk.Label(header, text="Clipboard History", bg=INK, fg=TEXT, font=("Segoe UI", 12, "bold"))
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._do_drag)

        close_btn = tk.Label(header, text="×", bg=INK, fg=MUTED, font=("Segoe UI", 14), cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._close())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=DANGER))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=MUTED))

        self.count_label = tk.Label(header, text="", bg=INK, fg=MUTED, font=("Segoe UI", 9))
        self.count_label.pack(side="right", padx=(0, 10))

        entry_wrap = tk.Frame(self.win, bg=INK)
        entry_wrap.pack(fill="x", padx=16, pady=(0, 10))

        self.entry = tk.Entry(
            entry_wrap,
            bg=INK,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 14),
            highlightthickness=0,
            bd=0,
        )
        self.entry.pack(fill="x", ipady=4)

        self._underline = tk.Frame(entry_wrap, bg=HAIRLINE, height=2)
        self._underline.pack(fill="x", pady=(4, 0))
        self.entry.bind("<FocusIn>", lambda e: self._underline.config(bg=ACCENT))
        self.entry.bind("<FocusOut>", lambda e: self._underline.config(bg=HAIRLINE))

        results_wrap = tk.Frame(self.win, bg=INK)
        results_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self.canvas = tk.Canvas(results_wrap, bg=INK, highlightthickness=0)
        scrollbar = tk.Scrollbar(results_wrap, orient="vertical", command=self.canvas.yview)
        self.rows_frame = tk.Frame(self.canvas, bg=INK)
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw", width=self.WIDTH - 40)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", lambda e: self._select_index(self._selected))
        self.entry.bind("<Down>", self._on_down)
        self.entry.bind("<Up>", self._on_up)

    def _on_down(self, event):
        self._move(1)
        return "break"

    def _on_up(self, event):
        self._move(-1)
        return "break"

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self._refresh()

    def _refresh(self):
        items = filter_clips(self._all_items, self.entry.get())
        self._filtered = items[:RENDER_CAP]
        self._selected = 0
        shown = len(self._filtered)
        total = len(items)
        suffix = f" of {total}" if total > shown else ""
        self.count_label.config(text=f"{shown}{suffix} clip{'s' if total != 1 else ''}")
        self.canvas.yview_moveto(0)
        self._render_rows()

    def _move(self, delta):
        if not self._filtered:
            return
        new_index = max(0, min(self._selected + delta, len(self._filtered) - 1))
        self._set_selected(new_index)
        self._ensure_visible()

    def _hover(self, index):
        self._set_selected(index)

    def _set_selected(self, index):
        """Restyle only the previously- and newly-selected rows in place, rather
        than destroying/rebuilding the whole list - full rebuilds on every mouse
        move or arrow key caused visible flicker."""
        if index == self._selected or not (0 <= index < len(self._row_widgets)):
            return
        old_index = self._selected
        self._selected = index
        if 0 <= old_index < len(self._row_widgets):
            self._style_row(self._row_widgets[old_index], False)
        self._style_row(self._row_widgets[index], True)

    def _style_row(self, row, selected):
        bg = PANEL_SELECTED if selected else INK
        for w in row.bg_widgets:
            w.config(bg=bg)

    def _render_rows(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets = []

        if not self._filtered:
            empty = tk.Label(self.rows_frame, text="No matches", bg=INK, fg=MUTED, font=("Segoe UI", 10), pady=20)
            empty.pack(fill="x")
            self._row_widgets.append(empty)
            return

        for i, item in enumerate(self._filtered):
            row = self._build_row(i, item)
            row.pack(fill="x")
            self._row_widgets.append(row)

    def _build_row(self, index, item):
        selected = index == self._selected
        bg = PANEL_SELECTED if selected else INK

        row = tk.Frame(self.rows_frame, bg=bg)
        inner = tk.Frame(row, bg=bg)
        inner.pack(fill="both", expand=True, padx=12, pady=8)

        when = tk.Label(inner, text=_relative_time(item["updated_at"]), bg=bg, fg=MUTED, font=("Segoe UI", 8), anchor="e")
        when.pack(side="right")

        text = tk.Label(inner, text=_preview(item["text"]), bg=bg, fg=TEXT, font=("Segoe UI", 10), anchor="w", justify="left")
        text.pack(side="left", fill="x", expand=True)

        row.bg_widgets = [row, inner, text, when]

        for widget in (row, inner, text, when):
            widget.bind("<Button-1>", lambda e, i=index: self._select_index(i))
            widget.bind("<Enter>", lambda e, i=index: self._hover(i))

        return row

    def _ensure_visible(self):
        if not self._row_widgets or self._selected >= len(self._row_widgets):
            return
        self.canvas.update_idletasks()
        row = self._row_widgets[self._selected]
        row_top = row.winfo_y()
        row_bottom = row_top + row.winfo_height()
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + self.canvas.winfo_height()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        total_height = bbox[3] - bbox[1]
        if total_height <= 0:
            return
        if row_top < view_top:
            self.canvas.yview_moveto(row_top / total_height)
        elif row_bottom > view_bottom:
            self.canvas.yview_moveto((row_bottom - self.canvas.winfo_height()) / total_height)

    def _select_index(self, index):
        if 0 <= index < len(self._filtered):
            text = self._filtered[index]["text"]
            self._close()
            self.on_select(text)

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.win.winfo_x()
        self._drag_y = event.y_root - self.win.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")

    def _position(self):
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - self.WIDTH) // 2
        y = (sh - self.HEIGHT) // 3
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _close(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None
