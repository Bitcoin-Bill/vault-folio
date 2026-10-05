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


if __name__ == "__main__":
    unittest.main()
