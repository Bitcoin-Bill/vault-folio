"""Shared UI theme helpers for Vault Folio (presentation only — no security logic).

Centralizes the palette, fonts, ttk styling and the three canonical button
styles so every screen looks and behaves the same. Importing this module has
no side effects until init_style() is called with a live Tk root.
"""
import tkinter as tk
import folio_theme as _theme
from tkinter import ttk

INK, PAPER, PAPER2, LINE, FLAG, OK = "#0a0a0a", "#fafaf8", "#f2f1ec", "#c9c7bf", "#b3282d", "#2e6b4f"
WHITE = "#ffffff"
HINT = "#6b6b6b"
BODY_TEXT = "#2e2e2e"
WARN_BG, WARN_TEXT, DIM, INK_SOFT, TEST_BG = "#fff1f2", "#8a6408", "#555555", "#333333", "#ffe0dc"
F = _theme.F  # scale-aware literal font: ui.F_theme.F("Georgia", 22)

F_H2 = ("Georgia", 22)
F_H3 = ("Georgia", 16)
F_BODY = ("Helvetica", 14)
F_SMALL = ("Helvetica", 12)
F_MONO = ("Courier", 13)
F_MONO_B = ("Courier", 13, "bold")
F_BADGE = ("Courier", 11, "bold")


def install_scrolling(root):
    """Route the wheel to the list or sheet under the pointer. Bind once."""
    if getattr(root, "_folio_scroll_installed", False):
        return
    root._folio_scroll_installed = True

    def targets(widget):
        inner = None
        sheet = None
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                sheet = widget
            elif inner is None and isinstance(widget, (tk.Text, tk.Listbox)):
                inner = widget
            widget = getattr(widget, "master", None)
        return inner, sheet

    def roll(event, direction):
        inner, sheet = targets(event.widget)
        if inner is not None:
            first, last = map(float, inner.yview())
            can_scroll_inner = (direction < 0 and first > 0) or (direction > 0 and last < 1)
            if can_scroll_inner:
                inner.yview_scroll(direction, "units")
            elif sheet is not None:
                sheet.canvas.yview_scroll(direction, "units")
            else:
                inner.yview_scroll(direction, "units")
        elif sheet is not None:
            sheet.canvas.yview_scroll(direction, "units")
        if inner is not None or sheet is not None:
            return "break"

    root.bind_all("<MouseWheel>", lambda event: roll(event, -1 if event.delta > 0 else 1))
    root.bind_all("<Button-4>", lambda event: roll(event, -3))
    root.bind_all("<Button-5>", lambda event: roll(event, 3))


class ScrollFrame(tk.Frame):
    """A sheet that scrolls vertically without stealing the wheel from other screens."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=PAPER, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=PAPER)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._fit)
        self.canvas.bind("<Configure>", self._fit)

    def _fit(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig(self._win, width=self.canvas.winfo_width())

    def scroll_to_top(self):
        """Start at the beginning when a sheet's contents are replaced."""
        self.after_idle(lambda: self.canvas.yview_moveto(0))


def init_style(root):
    """One-time ttk theme setup; call after the root window exists."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass  # fall back to whatever theme is available; mappings still apply
    style.configure(".", background=PAPER, foreground=INK, font=F_BODY)
    style.configure("TEntry", fieldbackground=WHITE, foreground=INK,
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=4)
    style.map("TEntry", bordercolor=[("focus", OK)], lightcolor=[("focus", OK)],
              darkcolor=[("focus", OK)])
    style.configure("TCombobox", fieldbackground=WHITE, foreground=INK,
                    background=PAPER2, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, arrowcolor=INK, padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", WHITE)],
              foreground=[("readonly", INK)],
              bordercolor=[("focus", OK)],
              lightcolor=[("focus", OK)],
              darkcolor=[("focus", OK)])
    style.configure("TButton", background=PAPER2, foreground=INK, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, padding=(12, 6), font=F_BODY)
    style.map("TButton", background=[("active", LINE)])
    style.configure("TCheckbutton", background=PAPER, foreground=INK)
    style.map("TCheckbutton", background=[("active", PAPER)])
    style.configure("TRadiobutton", background=PAPER, foreground=INK)
    style.configure("Vertical.TScrollbar", background=PAPER2, troughcolor=PAPER,
                    bordercolor=PAPER, arrowcolor=INK)
    return style


def btn_primary(parent, text, command, **pack_kw):
    b = tk.Button(parent, text=text, font=F_MONO_B, bg=INK, fg=PAPER, relief="flat",
                  padx=14, pady=8, cursor="hand2", activebackground=INK_SOFT,
                  activeforeground=PAPER, command=command)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_secondary(parent, text, command, **pack_kw):
    b = tk.Button(parent, text=text, font=F_MONO, bg=PAPER, fg=INK, relief="solid", bd=1,
                  highlightthickness=0, padx=12, pady=6, cursor="hand2",
                  activebackground=PAPER2, activeforeground=INK, command=command)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_danger(parent, text, command, **pack_kw):
    b = tk.Button(parent, text=text, font=_theme.F("Courier", 8), bg=WHITE, fg=FLAG, relief="flat",
                  padx=8, pady=4, cursor="hand2", activebackground=TEST_BG,
                  activeforeground=FLAG, command=command)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def card(parent, bg=WHITE, border=LINE, **pack_kw):
    """White content card with a thin border, used for records and grouped settings."""
    f = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=border)
    defaults = {"fill": "x", "pady": 6}
    defaults.update(pack_kw)
    f.pack(**defaults)
    return f


def badge(parent, text, color, bg=WHITE):
    return tk.Label(parent, text=text.upper(), font=F_BADGE, fg=color, bg=bg, anchor="w")


def center_window(window, parent, width=None, height=None):
    """Center a Toplevel over its parent once it has sized itself."""
    window.update_idletasks()
    w = width or window.winfo_reqwidth()
    h = height or window.winfo_reqheight()
    pw = parent.winfo_width() or window.winfo_screenwidth()
    ph = parent.winfo_height() or window.winfo_screenheight()
    x = parent.winfo_rootx() + max(0, (pw - w) // 2)
    y = parent.winfo_rooty() + max(0, (ph - h) // 3)
    window.geometry(f"{w}x{h}+{x}+{y}")
    return window


def hint_label(parent, text, bg=PAPER, wrap=620):
    return tk.Label(parent, text=text, font=F_SMALL, fg=HINT, bg=bg, anchor="w",
                    justify="left", wraplength=wrap)


def focusable(entry_widget, ok=OK):
    """Give a classic tk Entry/Text a visible focus ring matching the ttk theme."""
    entry_widget.configure(highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ok)
    return entry_widget
