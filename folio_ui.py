"""Shared UI theme helpers for Vault Folio (presentation only — no security logic).

Centralizes the palette, fonts, ttk styling and the three canonical button
styles so every screen looks and behaves the same. Importing this module has
no side effects until init_style() is called with a live Tk root.
"""
import tkinter as tk
from tkinter import ttk

INK, PAPER, PAPER2, LINE, FLAG, OK = "#0a0a0a", "#fafaf8", "#f2f1ec", "#c9c7bf", "#b3282d", "#2e6b4f"
WHITE = "#ffffff"
HINT = "#6b6b6b"
BODY_TEXT = "#2e2e2e"

F_H2 = ("Georgia", 22)
F_H3 = ("Georgia", 16)
F_BODY = ("Helvetica", 14)
F_SMALL = ("Helvetica", 12)
F_MONO = ("Courier", 13)
F_MONO_B = ("Courier", 13, "bold")
F_BADGE = ("Courier", 11, "bold")


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
                  padx=14, pady=8, cursor="hand2", activebackground="#333333",
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
    b = tk.Button(parent, text=text, font=("Courier", 8), bg=WHITE, fg=FLAG, relief="flat",
                  padx=8, pady=4, cursor="hand2", activebackground="#ffe0dc",
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


def hint_label(parent, text, bg=PAPER, wrap=620):
    return tk.Label(parent, text=text, font=F_SMALL, fg=HINT, bg=bg, anchor="w",
                    justify="left", wraplength=wrap)


def focusable(entry_widget, ok=OK):
    """Give a classic tk Entry/Text a visible focus ring matching the ttk theme."""
    entry_widget.configure(highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ok)
    return entry_widget
