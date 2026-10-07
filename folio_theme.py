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

# --- interface scale -------------------------------------------------------
# Tk font sizes: POSITIVE numbers are points (rescaled by `tk scaling`),
# NEGATIVE numbers are pixels (fixed). This app uses positive sizes, so
# touching `tk scaling` on top of F() would double-scale every font; and the
# default named fonts are pixel-sized (negative), so `tk scaling` never moved
# them at all. Scaling is done entirely here, exactly once: every font in the
# app comes either from a registered module constant or from F(), and
# set_scaling() rewrites those sources plus everything already on screen.
MIN_SCALE, MAX_SCALE = 1.0, 2.4
_factor = 1.0
_font_bases = {}                 # F() key -> unscaled pixel size
_ns_font_bases = {}              # id(namespace) -> {name: (family, size, styles)}
_named_bases = {}                # named font -> unscaled pixel size
_NAMED_FONTS = ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
                "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
                "TkIconFont", "TkTooltipFont")
_FONT_STYLES = ("bold", "italic", "underline", "overstrike")


def _scaled(base):
    return max(6, int(round(base * _factor)))


def F(family, size, *styles):
    """A font tuple at the current interface scale. Use for literal fonts."""
    key = (family, int(size)) + tuple(styles)
    _font_bases.setdefault(key, int(size))
    return (family, _scaled(_font_bases[key])) + tuple(styles)


def _is_font_tuple(value):
    return (isinstance(value, tuple) and len(value) >= 2 and
            isinstance(value[0], str) and value[0][:1].isalpha() and
            isinstance(value[1], int) and value[1] > 0 and
            all(str(extra) in _FONT_STYLES + ("normal", "roman") for extra in value[2:]))


def _set_factor(value):
    """Pure factor update; exported for tests. Returns the clamped factor."""
    global _factor
    _factor = min(MAX_SCALE, max(MIN_SCALE, float(value)))
    return _factor


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
    bases = {}
    for name, value in namespace.items():
        if _is_font_tuple(value):
            bases[name] = (value[0], value[1], tuple(value[2:]))
    _ns_font_bases[id(namespace)] = bases
    if namespace not in _registered:
        _registered.append(namespace)


def _sync():
    for namespace in _registered:
        for role, constant in CONST_NAMES.items():
            namespace[constant] = get(role)
        for name, (family, size, styles) in _ns_font_bases.get(id(namespace), {}).items():
            namespace[name] = (family, _scaled(size)) + styles


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


def set_button_style(name, app):
    """Switch the button look for this session and rebuild the current screen.

    Session-only, like the theme and text size: nothing is written to disk."""
    import folio_ui as ui
    if name == ui.button_style():
        return
    ui.set_button_style(name)
    rebuild = getattr(app, "screen_rebuilder", None)
    if rebuild:
        rebuild()


def _rescale_font(spec, old, new, root):
    """Return a font spec rescaled from old factor to new, or None to skip.

    Parses the spec string directly: a tkfont.Font probe would resolve a
    missing family to its display fallback and bake that in permanently."""
    try:
        tokens = list(root.tk.splitlist(spec))
    except tk.TclError:
        return None
    size_index = None
    for index in range(len(tokens) - 1, -1, -1):
        try:
            int(tokens[index])
            size_index = index
            break
        except ValueError:
            continue
    if size_index is None or size_index == 0:
        return None  # named font or malformed: leave alone
    size = int(tokens[size_index])
    scaled = max(6, int(round(abs(size) / old * new)))
    if size < 0:
        scaled = -scaled  # pixel-sized spec: keep the negative sign
    family = " ".join(tokens[:size_index])
    styles = tokens[size_index + 1:]
    return (family, scaled) + tuple(styles)


def _rescale(widget, old, new):
    """Re-font every widget and canvas text item in the tree."""
    def walk(w):
        # Same boundary as _repaint: the lock overlay keeps its own look.
        if (w is not widget and isinstance(w, tk.Toplevel) and
                not getattr(w, "_folio_settings_dialog", False)):
            return
        try:
            spec = str(w.cget("font"))
        except tk.TclError:
            spec = ""
        if spec and spec not in _NAMED_FONTS:  # named fonts are scaled once, globally
            try:
                replacement = _rescale_font(spec, old, new, widget)
                if replacement:
                    w.configure(font=replacement)
            except tk.TclError:
                pass
        if isinstance(w, tk.Canvas):
            for item in w.find_all():
                try:
                    if w.type(item) != "text":
                        continue
                    spec = w.itemcget(item, "font")
                    if spec:
                        replacement = _rescale_font(str(spec), old, new, widget)
                        if replacement:
                            w.itemconfigure(item, font=replacement)
                except tk.TclError:
                    pass
        for child in w.winfo_children():
            walk(child)

    walk(widget)


def set_scaling(root, value):
    """Set the interface scale (1.0 = as designed). Returns the clamped value.

    Never touches `tk scaling`: every font is rescaled exactly once, here."""
    old = _factor
    new = _set_factor(value)
    if new == old:
        return new
    from tkinter import font as tkfont
    for name in _NAMED_FONTS:  # widgets created without an explicit font
        try:
            named = tkfont.nametofont(name, root=root)
        except tk.TclError:
            continue
        size = named.cget("size")
        if size == 0:
            continue
        _named_bases.setdefault(name, abs(size) / old)
        scaled = max(6, int(round(_named_bases[name] * new)))
        named.configure(size=scaled if size > 0 else -scaled)  # keep px/pt sign
    _sync()
    import folio_ui as ui
    ui.init_style(root)
    _rescale(root, old, new)
    return new


def get_scaling(root):
    return round(_factor, 1)


def open_settings(app):
    import folio_ui as ui
    dialog = tk.Toplevel(app)
    dialog._folio_settings_dialog = True
    dialog.title("Interface settings")
    dialog.transient(app)
    dialog.grab_set()
    dialog.configure(bg=ui.PAPER)
    # The dialog content (themes + button style + scale) can exceed a small
    # screen; put it in a scrolling sheet with a bounded window size.
    sheet = ui.ScrollFrame(dialog, bg=ui.PAPER)
    sheet.pack(fill="both", expand=True, padx=24, pady=20)
    pad = sheet.inner
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
    tk.Label(pad, text="BUTTONS", font=ui.F_MONO_B,
             bg=ui.PAPER, fg=ui.INK).pack(anchor="w", pady=(18, 2))
    tk.Label(pad, text="Browser style draws flat ink buttons inside the app — recommended: it looks the same "
             "on every computer, and macOS cannot draw the classic buttons correctly. Classic uses the "
             "operating system's own buttons. Applies for this session only.",
             font=ui.F_SMALL, bg=ui.PAPER, fg=ui.BODY_TEXT, wraplength=500,
             justify="left").pack(anchor="w", pady=(0, 6))
    style_var = tk.StringVar(value=ui.button_style())
    for key, label in (("flat", "Browser style — flat ink buttons (default)"),
                       ("classic", "Classic — operating system buttons")):
        ui.radio_row(pad, label, style_var, key, bg="paper", font=ui.F_BODY, wraplength=440,
                     command=lambda: set_button_style(style_var.get(), app)).pack(anchor="w", pady=2)
    tk.Label(pad, text="TEXT SIZE (INTERFACE SCALE)", font=ui.F_MONO_B,
             bg=ui.PAPER, fg=ui.INK).pack(anchor="w", pady=(18, 2))
    tk.Label(pad, text="Makes every word in the app larger or smaller. 1.0 is the designed size; "
             "2.4 is the largest. Applies for this session only.",
             font=ui.F_SMALL, bg=ui.PAPER, fg=ui.BODY_TEXT, wraplength=500,
             justify="left").pack(anchor="w", pady=(0, 6))
    scale_row = tk.Frame(pad, bg=ui.PAPER)
    scale_row.pack(anchor="w")
    tk.Label(scale_row, text="1.0", font=ui.F_SMALL, bg=ui.PAPER, fg=ui.HINT).pack(side="left")
    scale = tk.Scale(scale_row, from_=1.0, to=2.4, resolution=0.1, orient="horizontal",
                     bg=ui.PAPER, fg=ui.INK, troughcolor=ui.PAPER2,
                     highlightthickness=0, length=300, showvalue=True,
                     command=lambda value: set_scaling(app, value))
    scale.set(get_scaling(app))
    scale.pack(side="left", padx=6)
    tk.Label(scale_row, text="2.4", font=ui.F_SMALL, bg=ui.PAPER, fg=ui.HINT).pack(side="left")
    ttk.Button(pad, text="Close", command=dialog.destroy).pack(anchor="e", pady=(14, 0))
    width = min(720, dialog.winfo_screenwidth() - 60)
    height = min(660, dialog.winfo_screenheight() - 80)
    ui.center_window(dialog, app, width, height)
    return dialog


validate_themes()
