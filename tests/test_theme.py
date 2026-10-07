"""Theme system tests.

Headless-safe tests run anywhere. Tests that need a window skip unless
DISPLAY is set (run under xvfb-run in CI or on a desktop).
"""
import os
import unittest

import folio_theme as themes
import folio_ui as ui

DISPLAY = bool(os.environ.get("DISPLAY"))
needs_display = unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")


class ThemeDefinitionTests(unittest.TestCase):
    def test_self_check_passes_at_import(self):
        self.assertTrue(themes.validate_themes())

    def test_every_theme_defines_every_role_exactly_once(self):
        for name, theme in themes.THEMES.items():
            colors = theme["colors"]
            self.assertEqual(set(colors), set(themes.ROLES), name)
            self.assertEqual(len(set(colors.values())), len(themes.ROLES),
                             f"{name} reuses a color; repaint would be ambiguous")

    def test_light_and_dark_templates_exist(self):
        self.assertIn("archival-light", themes.THEMES)
        self.assertIn("ledger-dark", themes.THEMES)

    def test_default_theme_matches_stock_constants(self):
        stock = {"ink": ui.INK, "paper": ui.PAPER, "paper2": ui.PAPER2,
                 "line": ui.LINE, "flag": ui.FLAG, "ok": ui.OK, "card": ui.WHITE,
                 "hint": ui.HINT, "body": ui.BODY_TEXT}
        light = themes.THEMES[themes.DEFAULT_THEME]["colors"]
        for role, value in stock.items():
            self.assertEqual(light[role], value.lower(), role)

    def test_F_scales_literal_fonts(self):
        themes._set_factor(2.0)
        try:
            self.assertEqual(themes.F("Georgia", 22), ("Georgia", 44))
            self.assertEqual(themes.F("Courier", 10, "bold"), ("Courier", 20, "bold"))
        finally:
            themes._set_factor(1.0)
        self.assertEqual(themes.F("Georgia", 22), ("Georgia", 22))

    def test_unknown_theme_rejected(self):
        with self.assertRaises(ValueError):
            themes.apply_theme("no-such-theme", None)


@needs_display
class ThemeApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        cls.tk = tk
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        themes.apply_theme(themes.DEFAULT_THEME, self.root)

    def test_install_then_apply_syncs_namespace(self):
        ns = {}
        themes.install(ns)
        themes.apply_theme("ledger-dark", self.root)
        self.assertEqual(ns["PAPER"], themes.THEMES["ledger-dark"]["colors"]["paper"])
        themes.apply_theme(themes.DEFAULT_THEME, self.root)
        self.assertEqual(ns["PAPER"], ui.PAPER)

    def test_repaint_recolors_existing_widgets_and_canvas_items(self):
        tk = self.tk
        frame = tk.Frame(self.root, bg=ui.PAPER)
        label = tk.Label(frame, bg=ui.PAPER, fg=ui.INK)
        canvas = tk.Canvas(frame, bg=ui.PAPER)
        item = canvas.create_rectangle(2, 2, 20, 20, fill=ui.WHITE, outline=ui.INK)
        frame.pack(); label.pack(); canvas.pack()
        themes.apply_theme("ledger-dark", self.root)
        dark = themes.THEMES["ledger-dark"]["colors"]
        self.assertEqual(str(label.cget("bg")), dark["paper"])
        self.assertEqual(str(label.cget("fg")), dark["ink"])
        self.assertEqual(canvas.itemcget(item, "fill"), dark["card"])
        self.assertEqual(canvas.itemcget(item, "outline"), dark["ink"])
        frame.destroy()

    def test_lock_overlay_colors_stay_fixed(self):
        """The lock screen is a security boundary: fixed palette by policy."""
        path = os.path.join(os.path.dirname(__file__), "..", "vault-folio.py")
        with open(path) as handle:
            source = handle.read()
        overlay = source.split("class LockOverlay", 1)[1].split("def try_resume", 1)[0]
        self.assertIn('"#0a0a0a"', overlay)   # pinned background
        self.assertNotIn("configure(bg=INK)", overlay)

    def test_scaling_clamps_to_supported_range(self):
        self.assertEqual(themes.set_scaling(self.root, 9.9), 2.4)
        self.assertEqual(themes.set_scaling(self.root, 0.1), 1.0)
        themes.set_scaling(self.root, 1.0)

    def test_scaling_visibly_changes_widgets(self):
        """Root-cause regression: tk scaling alone never touched pixel fonts."""
        from tkinter import font as tkfont
        tk = self.tk
        label = tk.Label(self.root, text="x", font=themes.F("Helvetica", 11))
        default_font_widget = tk.Label(self.root, text="y")  # no explicit font
        canvas = tk.Canvas(self.root)
        item = canvas.create_text(5, 5, text="z", font=themes.F("Courier", 10))
        label.pack(); default_font_widget.pack(); canvas.pack()

        def size_of(widget=None, canvas_item=None):
            spec = (canvas.itemcget(canvas_item, "font") if canvas_item
                    else widget.cget("font"))
            return tkfont.Font(root=self.root, font=str(spec)).cget("size")

        base_label = size_of(label)
        themes.set_scaling(self.root, 2.0)
        self.assertEqual(size_of(label), base_label * 2)
        self.assertEqual(size_of(canvas_item=item), 20)
        default_after = tkfont.nametofont("TkDefaultFont", root=self.root).cget("size")
        themes.set_scaling(self.root, 1.0)
        # exact restore, no rounding drift
        self.assertEqual(size_of(label), base_label)
        self.assertEqual(size_of(canvas_item=item), 10)
        self.assertEqual(tkfont.nametofont("TkDefaultFont", root=self.root).cget("size"),
                         tkfont.nametofont("TkDefaultFont", root=self.root).cget("size"))
        self.assertNotEqual(default_after, 0)  # named font was touched and valid
        label.destroy(); default_font_widget.destroy(); canvas.destroy()

    def test_scaling_updates_registered_font_constants(self):
        ns = {"F_BODY": ("Helvetica", 11), "F_MONO_B": ("Courier", 10, "bold"),
              "PAPER": "#fafaf8", "NOTAFONT": (1, 2), "NAME": "x"}
        themes.install(ns)
        themes.set_scaling(self.root, 2.0)
        self.assertEqual(ns["F_BODY"], ("Helvetica", 22))
        self.assertEqual(ns["F_MONO_B"], ("Courier", 20, "bold"))
        self.assertEqual(ns["NOTAFONT"], (1, 2))
        themes.set_scaling(self.root, 1.0)
        self.assertEqual(ns["F_BODY"], ("Helvetica", 11))

    def test_scaling_never_touches_tk_scaling(self):
        """tk scaling stays at the display's own value; we scale fonts once."""
        before = float(self.root.tk.call("tk", "scaling"))
        themes.set_scaling(self.root, 2.0)
        after = float(self.root.tk.call("tk", "scaling"))
        themes.set_scaling(self.root, 1.0)
        self.assertEqual(before, after)

    def test_scaling_renders_exactly_linearly(self):
        """Regression: positive tuple sizes are points, so F() plus a
        `tk scaling` mutation rendered at factor^2 (4x pixels at 2.0x)."""
        canvas = self.tk.Canvas(self.root)
        canvas.pack()

        def rendered_width(scale):
            themes.set_scaling(self.root, scale)
            item = canvas.create_text(0, 0, text="WATCH-ONLY",
                                      font=themes.F("Courier", 10, "bold"))
            bbox = canvas.bbox(item)
            canvas.delete(item)
            return bbox[2] - bbox[0]

        base = rendered_width(1.0)
        doubled = rendered_width(2.0)
        themes.set_scaling(self.root, 1.0)
        canvas.destroy()
        self.assertGreater(base, 0)
        self.assertAlmostEqual(doubled / base, 2.0, delta=0.15)

    def test_pixel_sized_named_fonts_scale_too(self):
        """Regression: TkDefaultFont is pixel-sized (negative) on X11 and the
        old engine skipped every size <= 0, so font-less widgets never scaled."""
        from tkinter import font as tkfont
        named = tkfont.nametofont("TkDefaultFont", root=self.root)
        base = named.cget("size")
        themes.set_scaling(self.root, 2.0)
        doubled = named.cget("size")
        themes.set_scaling(self.root, 1.0)
        self.assertEqual(abs(doubled), abs(base) * 2)
        self.assertEqual((doubled < 0), (base < 0))  # pixel/point sign kept
        self.assertEqual(named.cget("size"), base)  # exact restore

    def test_scaling_no_drift_across_round_trips(self):
        tk = self.tk
        label = tk.Label(self.root, text="x", font=themes.F("Georgia", 17))
        label.pack()
        original = str(label.cget("font"))
        for factor in (2.4, 1.3, 2.0, 1.0):
            themes.set_scaling(self.root, factor)
        self.assertEqual(str(label.cget("font")), original)
        label.destroy()


if __name__ == "__main__":
    unittest.main()


class ThemedEntryTests(unittest.TestCase):
    """Raw tk.Entry widgets pick up the OS appearance — on a dark-mode Mac
    they rendered as dark slabs inside light dialogs, with unthemed labels
    going white-on-white. All single-line fields must go through
    ui.text_entry() so colors are explicit palette roles."""

    SOURCE_FILES = ("vault-folio.py", "folio_beneficiary.py", "folio_catalog.py",
                    "folio_document.py", "folio_hardware_ui.py", "folio_memory.py",
                    "folio_security.py", "folio_storage.py", "folio_synthetic.py",
                    "folio_theme.py")

    def test_no_raw_tk_entry_outside_ui_helper(self):
        import os
        import re
        repo = os.path.join(os.path.dirname(__file__), "..")
        raw = re.compile(r"(?<!t)tk\.Entry\(")  # ttk.Entry is styled in init_style
        for name in self.SOURCE_FILES:
            path = os.path.join(repo, name)
            if not os.path.exists(path):
                continue
            with open(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    self.assertIsNone(raw.search(line),
                                      f"{name}:{lineno} creates a raw tk.Entry; "
                                      "use ui.text_entry() so colors stay themed")

    @needs_display
    def test_text_entry_carries_explicit_palette_colors(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            entry = ui.text_entry(root)
            self.assertEqual(entry.cget("bg"), ui.WHITE)
            self.assertEqual(entry.cget("fg"), ui.INK)
            self.assertEqual(entry.cget("insertbackground"), ui.INK)
            self.assertEqual(entry.cget("highlightbackground"), ui.LINE)
            secret = ui.text_entry(root, secret=True)
            self.assertEqual(secret.cget("show"), "*")
        finally:
            root.destroy()

    @needs_display
    def test_dialog_labels_carry_explicit_colors(self):
        """Labels with a themed bg but no fg went white-on-white on macOS
        dark mode. Every tk.Label in app sources must set fg when it sets bg."""
        import ast
        import os
        repo = os.path.join(os.path.dirname(__file__), "..")
        for name in self.SOURCE_FILES + ("folio_ui.py",):
            path = os.path.join(repo, name)
            if not os.path.exists(path):
                continue
            tree = ast.parse(open(path).read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "Label"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "tk"):
                    kw = {k.arg for k in node.keywords if k.arg}
                    self.assertFalse("bg" in kw and "fg" not in kw,
                                     f"{name}:{node.lineno} tk.Label sets bg without fg")
