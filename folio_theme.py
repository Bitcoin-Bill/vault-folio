"""Session-only appearance controls for the desktop interface."""
import re
import tkinter as tk
from tkinter import ttk

ROLES = ("ink", "paper", "paper2", "line", "flag", "ok", "card", "hint",
         "body", "warnbg", "warntext", "dim", "inksoft", "testbg")
CONST_NAMES = {"ink": "INK", "paper": "PAPER", "paper2": "PAPER2", "line": "LINE",
               "flag": "FLAG", "ok": "OK", "card": "WHITE", "hint": "HINT",
               "body": "BODY_TEXT", "warnbg": "WARN_BG", "warntext": "WARN_TEXT",
               "dim": "DIM", "inksoft": "INK_SOFT", "testbg": "TEST_BG"}

THEMES = {
    "archival-light": {"title": "Archival Light", "about": "Paper and ink.", "colors": {
        "ink": "#0a0a0a", "paper": "#fafaf8", "paper2": "#f2f1ec", "line": "#c9c7bf",
        "flag": "#b3282d", "ok": "#2e6b4f", "card": "#ffffff", "hint": "#6b6b6b",
        "body": "#2e2e2e", "warnbg": "#fff1f2", "warntext": "#8a6408", "dim": "#555555",
        "inksoft": "#333333", "testbg": "#ffe0dc"}},
    "ledger-dark": {"title": "Ledger Dark", "about": "A low-light dark palette.", "colors": {
        "ink": "#eceae4", "paper": "#141519", "paper2": "#1c1e24", "line": "#3a3d46",
        "flag": "#e0606a", "ok": "#5fb98c", "card": "#22242b", "hint": "#9a9da8",
        "body": "#d6d4cc", "warnbg": "#2b1d1f", "warntext": "#d9a05b", "dim": "#8f929c",
        "inksoft": "#cfcdc6", "testbg": "#33201f"}},
    "high-contrast": {"title": "High Contrast", "about": "Black and white with stronger contrast.", "colors": {
        "ink": "#000000", "paper": "#ffffff", "paper2": "#efefef", "line": "#404040",
        "flag": "#b00020", "ok": "#005a32", "card": "#fdfdfd", "hint": "#3d3d3d",
        "body": "#0d0d0d", "warnbg": "#ffe9ec", "warntext": "#6b4e00", "dim": "#2b2b2b",
        "inksoft": "#1a1a1a", "testbg": "#ffd9d5"}},
    "sepia-print": {"title": "Sepia Print", "about": "Warm archival paper tones.", "colors": {
        "ink": "#3b2f1e", "paper": "#f4ecd8", "paper2": "#eadfc6", "line": "#c8b98f",
        "flag": "#9c3a2b", "ok": "#4a6b3a", "card": "#fbf6e9", "hint": "#7a6a4f",
        "body": "#4a3f2c", "warnbg": "#f3dcc8", "warntext": "#8a5a08", "dim": "#8a7a5f",
        "inksoft": "#5a4c36", "testbg": "#f0d2bd"}},
}
DEFAULT_THEME = "archival-light"
_current = DEFAULT_THEME
_registered = []
_HEX = re.compile(r"^#[0-9a-f]{6}$")
_COLOR_OPTIONS = ("bg", "background", "fg", "foreground", "activebackground",
                  "activeforeground", "selectcolor", "highlightbackground",
                  "highlightcolor", "insertbackground", "disabledforeground")


def validate_themes():
    for name, theme in THEMES.items():
        colors = theme["colors"]
        if set(colors) != set(ROLES) or len(set(colors.values())) != len(ROLES):
            raise ValueError("Incomplete or ambiguous palette: " + name)
        if any(not _HEX.fullmatch(value) for value in colors.values()):
            raise ValueError("Invalid color in palette: " + name)
    return True


def get(role):
    return THEMES[_current]["colors"][role]


def install(namespace):
    for role, constant in CONST_NAMES.items():
        namespace[constant] = get(role)
    if namespace not in _registered:
        _registered.append(namespace)


def _sync():
    for namespace in _registered:
        for role, constant in CONST_NAMES.items():
            namespace[constant] = get(role)


def _repaint(widget, source):
    old = {color: role for role, color in THEMES[source]["colors"].items()}
    new = THEMES[_current]["colors"]

    def color_for(value):
        role = old.get(str(value).lower())
        return new.get(role) if role else None

    def walk(w):
        # Top-level dialogs include the environment lock overlay. Keep those
        # dialogs outside appearance changes so the security boundary stays fixed.
        if (w is not widget and isinstance(w, tk.Toplevel) and
                not getattr(w, "_folio_settings_dialog", False)):
            return
        for option in _COLOR_OPTIONS:
            try:
                replacement = color_for(w.cget(option))
                if replacement:
                    w.configure({option: replacement})
            except tk.TclError:
                pass
        if isinstance(w, tk.Canvas):
            for item in w.find_all():
                for option in ("fill", "outline"):
                    try:
                        replacement = color_for(w.itemcget(item, option))
                        if replacement:
                            w.itemconfigure(item, {option: replacement})
                    except tk.TclError:
                        pass
        for child in w.winfo_children():
            walk(child)

    walk(widget)


def apply_theme(name, root):
    global _current
    if name not in THEMES:
        raise ValueError("Unknown theme: " + str(name))
    if name == _current:
        return
    previous = _current
    _current = name
    _sync()
    import folio_ui as ui
    ui.init_style(root)
    _repaint(root, previous)


def current_theme():
    return _current


def set_scaling(root, value):
    value = min(2.4, max(1.0, float(value)))
    root.tk.call("tk", "scaling", value)
    return value


def get_scaling(root):
    try:
        return round(float(root.tk.call("tk", "scaling")), 1)
    except (tk.TclError, ValueError):
        return 1.0


def open_settings(app):
    import folio_ui as ui
    dialog = tk.Toplevel(app)
    dialog._folio_settings_dialog = True
    dialog.title("Interface settings")
    dialog.transient(app)
    dialog.grab_set()
    dialog.configure(bg=ui.PAPER)
    pad = tk.Frame(dialog, bg=ui.PAPER)
    pad.pack(fill="both", expand=True, padx=24, pady=20)
    tk.Label(pad, text="INTERFACE SETTINGS", font=ui.F_MONO_B,
             bg=ui.PAPER, fg=ui.INK).pack(anchor="w")
    tk.Label(pad, text="Changes apply for this session only. Nothing is saved. The gate and lock screen keep their fixed appearance.",
             font=ui.F_SMALL, bg=ui.PAPER, fg=ui.BODY_TEXT, wraplength=500,
             justify="left").pack(anchor="w", pady=(6, 14))
    selected = tk.StringVar(value=_current)
    for name, theme in THEMES.items():
        row = tk.Frame(pad, bg=ui.PAPER)
        row.pack(fill="x", pady=3)
        tk.Radiobutton(row, variable=selected, value=name, bg=ui.PAPER,
                       activebackground=ui.PAPER, selectcolor=ui.WHITE,
                       command=lambda key=name: (selected.set(key), apply_theme(key, app))).pack(side="left")
        tk.Label(row, text=theme["title"], font=ui.F_MONO_B,
                 bg=ui.PAPER, fg=ui.INK).pack(side="left", padx=(4, 10))
        tk.Label(row, text=theme["about"], font=ui.F_SMALL,
                 bg=ui.PAPER, fg=ui.HINT).pack(side="left")
        swatches = tk.Frame(row, bg=ui.PAPER)
        swatches.pack(side="right")
        for role in ("paper", "card", "ink", "flag", "ok"):
            tk.Frame(swatches, bg=theme["colors"][role], width=16, height=16,
                     highlightthickness=1, highlightbackground=theme["colors"]["line"]).pack(side="left", padx=1)
    tk.Label(pad, text="INTERFACE SCALE", font=ui.F_MONO_B,
             bg=ui.PAPER, fg=ui.INK).pack(anchor="w", pady=(18, 2))
    scale = tk.Scale(pad, from_=1.0, to=2.4, resolution=0.1, orient="horizontal",
                     bg=ui.PAPER, fg=ui.INK, troughcolor=ui.PAPER2,
                     highlightthickness=0, length=300,
                     command=lambda value: set_scaling(app, value))
    scale.set(get_scaling(app))
    scale.pack(anchor="w")
    ttk.Button(pad, text="Close", command=dialog.destroy).pack(anchor="e", pady=(14, 0))
    return dialog


validate_themes()
