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
    style.map("TEntry", bordercolor=[("focus", INK)], lightcolor=[("focus", INK)],
              darkcolor=[("focus", INK)])
    style.configure("TCombobox", fieldbackground=WHITE, foreground=INK,
                    background=PAPER2, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, arrowcolor=INK, padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", WHITE)],
              foreground=[("readonly", INK)],
              bordercolor=[("focus", INK)],
              lightcolor=[("focus", INK)],
              darkcolor=[("focus", INK)])
    style.configure("TButton", background=PAPER2, foreground=INK, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, padding=(12, 6), font=F_BODY)
    style.map("TButton", background=[("active", LINE)])
    style.configure("TCheckbutton", background=PAPER, foreground=INK)
    style.map("TCheckbutton", background=[("active", PAPER)])
    style.configure("TRadiobutton", background=PAPER, foreground=INK)
    style.configure("Vertical.TScrollbar", background=PAPER2, troughcolor=PAPER,
                    bordercolor=PAPER, arrowcolor=INK)
    return style


class FlatButton(tk.Frame):
    """A button drawn as a frame plus a label, so it renders identically on
    every platform. (macOS Aqua ignores tk.Button backgrounds, which is why
    plain tk.Buttons displayed there as white slabs.)

    Colors are theme role names ("ink", "paper", ...) resolved live from
    folio_theme, or literal hex strings. Hover inverts the colors like the
    browser edition. The API mirrors the slice of tk.Button the app uses:
    invoke(), cget/configure for "text" and "state", "bg"/"fg"/"font"/
    "command" in configure, and the usual pack/grid geometry methods.
    """

    def __init__(self, parent, text="", command=None, font=None,
                 bg="paper", fg="ink", hover_bg=None, hover_fg=None,
                 border="ink", focus="ok", padx=14, pady=8,
                 anchor="center", justify="center", wraplength=0,
                 cursor="hand2"):
        super().__init__(parent, highlightthickness=1, takefocus=1)
        self._command = command
        self._state = "normal"
        self._cursor = cursor
        self._roles = {
            "bg": bg, "fg": fg,
            "hover_bg": hover_bg if hover_bg is not None else fg,
            "hover_fg": hover_fg if hover_fg is not None else bg,
            "border": border,
            "focus": focus,
        }
        self._label = tk.Label(self, text=text, font=font, padx=padx, pady=pady,
                               anchor=anchor, justify=justify, wraplength=wraplength)
        self._label.pack(fill="both", expand=True)
        self._armed = None
        self._key_release_job = None
        for widget in (self, self._label):
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
            widget.bind("<Button-1>", self._press)
            widget.bind("<ButtonRelease-1>", self._release)
        for key in ("Return", "space"):
            self.bind("<KeyPress-" + key + ">", self._key_press)
            self.bind("<KeyRelease-" + key + ">", self._key_release)
        self.bind("<FocusOut>", self._cancel)
        self.bind("<Destroy>", self._cancel)
        self._paint()

    # -- tk.Button-compatible surface --------------------------------------
    def invoke(self):
        if self._state == "normal" and self._command is not None:
            return self._command()
        return None

    def cget(self, key):
        if key == "text":
            return self._label.cget("text")
        if key == "state":
            return self._state
        return super().cget(key)

    def configure(self, cnf=None, **kw):
        if cnf is None and not kw:
            return super().configure()
        if isinstance(cnf, str):
            return super().configure(cnf)
        if cnf:
            merged = dict(cnf)
            merged.update(kw)
            kw = merged
        repaint = False
        for key in ("bg", "fg", "hover_bg", "hover_fg", "border"):
            if key in kw:
                self._roles[key] = kw.pop(key)
                repaint = True
        if "text" in kw:
            self._label.configure(text=kw.pop("text"))
        if "font" in kw:
            self._label.configure(font=kw.pop("font"))
        if "command" in kw:
            self._command = kw.pop("command")
        if "state" in kw:
            self._state = "disabled" if kw.pop("state") == "disabled" else "normal"
            if self._state == "disabled":
                self._cancel()
            repaint = True
        if kw:
            super().configure(kw)
        if repaint:
            self._paint()
        return None

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _color(value):
        if isinstance(value, str) and value in _theme.ROLES:
            return _theme.get(value)
        return value

    def _enter(self, _event):
        self._paint(hovered=True)

    def _leave(self, _event):
        self._paint(hovered=False)

    def _cancel(self, _event=None):
        self._armed = None
        if self._key_release_job is not None:
            self.after_cancel(self._key_release_job)
            self._key_release_job = None

    def _press(self, _event):
        self._cancel()
        if self._state == "normal":
            self.focus_set()
            self._armed = "mouse"
        return "break"

    def _release(self, event):
        armed = self._armed == "mouse"
        self._cancel()
        target = self.winfo_containing(event.x_root, event.y_root)
        if armed and target in (self, self._label):
            self.invoke()
        return "break"

    def _key_press(self, event):
        # X11 autorepeat emits release/press pairs; cancel the pending release.
        if self._key_release_job is not None:
            self.after_cancel(self._key_release_job)
            self._key_release_job = None
        if self._state == "normal" and self._armed is None:
            self._armed = event.keysym
        return "break"

    def _key_release(self, event):
        if self._armed == event.keysym and self._key_release_job is None:
            def finish():
                armed = self._armed == event.keysym
                self._key_release_job = None
                self._armed = None
                if armed and self.focus_get() == self:
                    self.invoke()
            self._key_release_job = self.after_idle(finish)
        return "break"

    def _paint(self, hovered=False):
        roles = self._roles
        if self._state != "normal":
            bg, fg = self._color(roles["bg"]), _theme.get("hint")
        elif hovered:
            bg = self._color(roles["hover_bg"])
            fg = self._color(roles["hover_fg"])
        else:
            bg = self._color(roles["bg"])
            fg = self._color(roles["fg"])
        if roles["border"]:
            edge = self._color(roles["border"])
            if self._state != "normal":
                edge = _theme.get("line")
        else:
            edge = bg  # borderless: the highlight ring shows only on focus
        cursor = self._cursor if self._state == "normal" else ""
        tk.Frame.configure(self, bg=bg, highlightbackground=edge,
                           highlightcolor=self._color(roles["focus"]), cursor=cursor)
        self._label.configure(bg=bg, fg=fg, cursor=cursor)


class _ChoiceRow(tk.Frame):
    """Base for drawn radio/checkbox rows, identical on every platform.

    macOS Aqua renders native radiobuttons/checkbuttons itself and drops the
    customized label text (blank options), so here the indicator is a small
    canvas drawing and the text a plain label — like the browser edition.
    Colors are theme role names or hex strings.
    """

    SHAPE = "radio"

    def __init__(self, parent, text, variable, value=None, command=None,
                 font=None, bg="card", fg="ink", wraplength=620):
        super().__init__(parent, highlightthickness=1, takefocus=1)
        self._bg_role = bg
        self._fg_role = fg
        self._variable = variable  # keep a reference so the Tcl var is never GC'd
        self._value = value
        self._command = command
        self._canvas = tk.Canvas(self, width=16, height=16, bd=0,
                                 highlightthickness=0, cursor="hand2")
        self._canvas.pack(side="left", anchor="n", padx=(0, 8), pady=2)
        self._label = tk.Label(self, text=text, font=font, anchor="w",
                               justify="left", wraplength=wraplength, cursor="hand2")
        self._label.pack(side="left", anchor="n")
        self._pressed = False
        for widget in (self, self._canvas, self._label):
            widget.bind("<Button-1>", self._press)
            widget.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", self._click)
        self.bind("<space>", self._click)
        self._trace = variable.trace_add("write", lambda *_: self._repaint_selection())
        self.bind("<Destroy>", self._untrace)
        self._paint()

    # -- behavior -----------------------------------------------------------
    def _selected(self):
        try:
            current = self._variable.get()
        except tk.TclError:
            return False
        if self.SHAPE == "radio":
            return str(current) == str(self._value)
        return current is True or current == 1 or str(current) in ("1", "true")

    def invoke(self):
        if self.SHAPE == "radio":
            self._variable.set(self._value)
        else:
            self._variable.set(not self._selected())
        if self._command is not None:
            return self._command()
        return None

    def _click(self, _event):
        self.focus_set()
        self.invoke()
        return "break"

    def _press(self, _event):
        self._pressed = True
        self.focus_set()
        return "break"

    def _release(self, event):
        was_pressed = self._pressed
        self._pressed = False
        target = self.winfo_containing(event.x_root, event.y_root)
        if was_pressed and target in (self, self._canvas, self._label):
            self.invoke()
        return "break"

    # -- tk-compatible shims (widget walks in tests) -------------------------
    def cget(self, key):
        if key == "text":
            return self._label.cget("text")
        if key == "variable":
            return str(self._variable)
        return super().cget(key)

    def getvar(self, name):
        return self._variable.get()

    # -- painting -------------------------------------------------------------
    def _untrace(self, _event=None):
        try:
            self._variable.trace_remove("write", self._trace)
        except (tk.TclError, AttributeError):
            pass

    def _repaint_selection(self):
        if self.winfo_exists():
            self._paint()

    def _paint(self):
        bg = FlatButton._color(self._bg_role)
        fg = FlatButton._color(self._fg_role)
        ink = FlatButton._color("ink")
        tk.Frame.configure(self, bg=bg, highlightbackground=bg, highlightcolor=ink)
        self._label.configure(bg=bg, fg=fg)
        self._canvas.configure(bg=bg)
        self._canvas.delete("all")
        if self.SHAPE == "radio":
            self._canvas.create_oval(1, 1, 15, 15, outline=ink, width=1)
            if self._selected():
                self._canvas.create_oval(5, 5, 11, 11, fill=ink, outline=ink)
        else:
            self._canvas.create_rectangle(1, 1, 15, 15, outline=ink, width=1)
            if self._selected():
                self._canvas.create_rectangle(4, 4, 12, 12, fill=ink, outline=ink)


class RadioRow(_ChoiceRow):
    """One option of a radio group, drawn in-app (see _ChoiceRow)."""
    SHAPE = "radio"


class CheckRow(_ChoiceRow):
    """A checkbox row, drawn in-app (see _ChoiceRow)."""
    SHAPE = "check"


def radio_row(parent, text, variable, value, command=None, bg="card", fg="ink",
              font=None, wraplength=620, **pack_kw):
    row = RadioRow(parent, text, variable, value, command=command,
                   font=font or F_BODY, bg=bg, fg=fg, wraplength=wraplength)
    if pack_kw:
        row.pack(**pack_kw)
    return row


def check_row(parent, text, variable, command=None, bg="paper", fg="ink",
              font=None, wraplength=620, **pack_kw):
    row = CheckRow(parent, text, variable, command=command,
                   font=font or F_BODY, bg=bg, fg=fg, wraplength=wraplength)
    if pack_kw:
        row.pack(**pack_kw)
    return row


# --- button style (session-only) --------------------------------------------
# "flat" (default) draws buttons in-app: identical on every platform and the
# only style macOS renders correctly. "classic" uses native tk.Button widgets
# (the original build). Session-only; nothing is ever written to disk.
BUTTON_STYLES = ("flat", "classic")
_button_style = "flat"


def button_style():
    return _button_style


def set_button_style(name):
    global _button_style
    if name not in BUTTON_STYLES:
        raise ValueError("Unknown button style: " + str(name))
    _button_style = name
    return _button_style


def btn_primary(parent, text, command, ipadx=14, ipady=8, **pack_kw):
    """ipadx/ipady pad the button itself; padx/pady in pack_kw space it in the layout."""
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=F_MONO_B, bg=INK, fg=PAPER, relief="flat",
                      padx=ipadx, pady=ipady, cursor="hand2", activebackground=INK_SOFT,
                      activeforeground=PAPER, command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=F_MONO_B,
                       bg="ink", fg="paper", border="ink", padx=ipadx, pady=ipady)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_secondary(parent, text, command, ipadx=12, ipady=6, **pack_kw):
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=F_MONO, bg=PAPER, fg=INK, relief="solid", bd=1,
                      highlightthickness=0, padx=ipadx, pady=ipady, cursor="hand2",
                      activebackground=PAPER2, activeforeground=INK, command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=F_MONO,
                       bg="paper", fg="ink", border="ink", padx=ipadx, pady=ipady)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_danger(parent, text, command, bg="card", font=None, ipadx=8, ipady=4, **pack_kw):
    font = font or _theme.F("Courier", 8)
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=font, bg=FlatButton._color(bg), fg=FLAG,
                      relief="flat", padx=ipadx, pady=ipady, cursor="hand2",
                      activebackground=TEST_BG, activeforeground=FLAG, command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=font,
                       bg=bg, fg="flag", hover_bg="testbg", hover_fg="flag",
                       border=None, padx=ipadx, pady=ipady)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_quiet(parent, text, command, font=None, **pack_kw):
    """A borderless text button (header links); hover inverts to ink."""
    font = font or _theme.F("Courier", 8)
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=font, command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=font,
                       bg="paper", fg="ink", border=None, padx=8, pady=2)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_home_action(parent, text, command, primary, **pack_kw):
    """One of the two big home-screen actions; primary is solid ink."""
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=F_MONO_B, relief="flat",
                      padx=16, pady=10, cursor="hand2",
                      bg=(INK if primary else PAPER2), fg=(PAPER if primary else INK),
                      highlightthickness=1, highlightbackground=LINE, command=command)
    else:
        b = FlatButton(parent, text=text, font=F_MONO_B, padx=16, pady=10, command=command,
                       bg=("ink" if primary else "paper"), fg=("paper" if primary else "ink"))
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_flag(parent, text, command, **pack_kw):
    """A warning-outlined button (EDITOR VIEW on a saved guide)."""
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=F_MONO_B, bg=PAPER, fg=FLAG, relief="flat",
                      highlightthickness=1, highlightbackground=FLAG, padx=12, pady=8,
                      cursor="hand2", command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=F_MONO_B,
                       bg="paper", fg="flag", border="flag", padx=12, pady=8)
    if pack_kw:
        b.pack(**pack_kw)
    return b


def btn_step(parent, text, command):
    """A wizard sidebar step entry."""
    if _button_style == "classic":
        b = tk.Button(parent, text=text, font=_theme.F("Courier", 9),
                      anchor="w", justify="left", wraplength=205,
                      relief="flat", padx=14, pady=8, cursor="hand2", bg=PAPER2, fg=HINT,
                      activebackground=INK, activeforeground=PAPER, command=command)
    else:
        b = FlatButton(parent, text=text, command=command, font=_theme.F("Courier", 9),
                       anchor="w", justify="left", wraplength=205, padx=14, pady=8,
                       border=None, bg="paper2", fg="hint", hover_bg="ink", hover_fg="paper")
    b.pack(fill="x")
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


def focusable(entry_widget, ring=INK):
    """Give a classic tk Entry/Text a visible focus ring matching the ttk theme."""
    entry_widget.configure(highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ring)
    return entry_widget
