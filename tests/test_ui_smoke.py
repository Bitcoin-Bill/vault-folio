"""UI smoke tests: every primary screen must construct without Tcl errors.

These exist because a crash in show_beneficiary (an option tk.Text does not
support) once shipped while all 35 logic tests passed. They run under
xvfb-run in CI; they skip when no display is available.
"""
import importlib.util
import os
import sys
import unittest

DISPLAY = bool(os.environ.get("DISPLAY"))


def load_app_module():
    path = os.path.join(os.path.dirname(__file__), "..", "vault-folio.py")
    spec = importlib.util.spec_from_file_location("vault_folio", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_folio"] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")
class ScreenConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vf = load_app_module()
        cls.app = cls.vf.App(test_mode=True)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def plan(self):
        plan = self.vf.blank_plan()
        plan["people"] = {"owner": "Ada Lovelace",
                          "heirs": [{"name": "Bea", "relation": "daughter"}]}
        plan["vaults"] = [{"name": "Main vault", "setupType": "multi", "m": 2, "n": 3,
                           "keys": [{"label": "Coldcard A", "device": "Coldcard",
                                     "locations": "home safe"},
                                    {"label": "Jade B", "device": "Jade",
                                     "locations": "bank box"},
                                    {"label": "Signer C"}]}]
        plan["backupRecords"] = [{"label": "Main vault / Coldcard A",
                                  "holder": "Ada", "location": "home safe"}]
        return plan

    def test_home_screen_constructs(self):
        self.vf.home_screen(self.app)
        self.app.update_idletasks()

    def test_heir_guide_constructs(self):
        """Regression: tk.Text rejected -disabledforeground and killed this screen."""
        self.vf.show_heir(self.app, self.plan())
        self.app.update_idletasks()

    def test_beneficiary_runbook_constructs(self):
        from folio_beneficiary import show_beneficiary
        self.app.clear()
        show_beneficiary(self.app, self.plan(), lambda: None,
                         self.vf.build_runbook_text, lambda box, plan: None)
        self.app.update_idletasks()

    def test_wizard_constructs(self):
        self.app.clear()
        self.vf.Wizard(self.app, self.plan())
        self.app.update_idletasks()


    def test_heir_nav_every_row_renders_without_errors(self):
        """Regression: the sidebar used raw listbox indices, shifting every row
        and crashing on 'Full reference' with an IndexError."""
        import tkinter as tk
        errors = []
        tk.Tk.report_callback_exception = lambda _self, *a: errors.append(a[1])
        self.vf.show_heir(self.app, self.plan())
        self.app.update_idletasks()
        listboxes = []
        def find(widget):
            if isinstance(widget, tk.Listbox):
                listboxes.append(widget)
            for child in widget.winfo_children():
                find(child)
        find(self.app)
        nav = listboxes[0]
        first_row_label = str(nav.get(0))
        self.assertTrue(first_row_label.startswith("1."), first_row_label)
        for row in range(nav.size()):
            nav.selection_clear(0, "end")
            nav.selection_set(row)
            nav.event_generate("<<ListboxSelect>>")
            self.app.update_idletasks()
        self.assertEqual(errors, [])

    def test_heir_checklist_state_survives_reopen(self):
        """Regression: checklist keys were written as str but read as int,
        so saved checkmarks always came back unchecked."""
        import tkinter as tk
        plan = self.plan()
        plan["heirChecklist"] = {"1": True}
        self.vf.show_heir(self.app, plan)
        self.app.update_idletasks()
        boxes = []
        def find(widget):
            if isinstance(widget, tk.Checkbutton):
                boxes.append(widget)
            for child in widget.winfo_children():
                find(child)
        find(self.app)
        checklist = [b for b in boxes if str(b.cget("text"))[0].isdigit()]
        self.assertTrue(checklist, "no checklist rendered")
        self.assertEqual(checklist[0].getvar(checklist[0].cget("variable")), True)

    def test_detail_window_constructs(self):
        self.vf.show_tree_detail("Key 1", [("Holder", "Ada"), ("Location", "home safe")])
        self.app.update_idletasks()

    def test_heir_nav_buttons_are_mapped_and_sized(self):
        """Regression: the scroll rewrite squeezed the bottom bar to 1px, so
        PREVIOUS / NEXT / SAVE / CLOSE were all unreachable in the heir view."""
        import tkinter as tk
        self.vf.show_heir(self.app, self.plan())
        self.app.update_idletasks()
        self.app.update()
        found = {}

        def walk(widget):
            if isinstance(widget, tk.Button):
                found[str(widget.cget("text"))] = widget
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        for label in ("← PREVIOUS", "NEXT STEP →", "SAVE NOTES INTO ENCRYPTED FILE",
                      "EDITOR VIEW", "CLOSE GUIDE & CLEAR SESSION"):
            self.assertIn(label, found, f"{label} missing")
            button = found[label]
            self.assertTrue(button.winfo_ismapped(), f"{label} not mapped")
            self.assertGreater(button.winfo_height(), 20, f"{label} squeezed")

    def test_saved_snapshot_cleared_with_session(self):
        """Regression: CLOSE GUIDE & CLEAR SESSION left a full plaintext copy
        of the guide in RAM and offered RESET TO SAVED on the next new plan."""
        plan = self.plan()
        self.app.saved_snapshot = {"meta": dict(plan["meta"]), "people": dict(plan["people"])}
        self.vf.home_screen(self.app)
        self.app.update_idletasks()
        self.assertIsNone(self.app.saved_snapshot)

    def test_wizard_heir_toggle_round_trips_without_losing_edits(self):
        """Regression: HEIR VIEW from the editor was a one-way door whose close
        discarded unsaved work without a prompt."""
        import tkinter as tk
        plan = self.plan()
        wizard = self.vf.start_wizard(self.app, plan)
        self.app.dirty = True
        plan["meta"]["planName"] = "Edited in the wizard"
        wizard.to_heir()
        self.app.update_idletasks()
        buttons = {}

        def walk(widget):
            if isinstance(widget, tk.Button):
                buttons[str(widget.cget("text"))] = widget
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        self.assertIn("← BACK TO EDITOR", buttons)
        buttons["← BACK TO EDITOR"].invoke()
        self.app.update_idletasks()
        self.assertEqual(plan["meta"]["planName"], "Edited in the wizard")
        self.assertTrue(self.app.dirty)
        self.assertIs(self.app.active_plan, plan)

    def test_family_map_dedups_places(self):
        """Regression: 'Place: Home safe; Home safe' when a key location and a
        backup record name the same spot."""
        import tkinter as tk
        plan = self.plan()
        plan["backupRecords"] = [{"label": "Main vault / Coldcard A",
                                  "custodian": "Ada", "location": "home safe"}]
        cv = tk.Canvas(self.app)
        self.vf.canvas_family_map(cv, plan)
        self.app.update_idletasks()
        texts = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        joined = "\n".join(texts)
        self.assertNotIn("home safe; home safe", joined.casefold())
        cv.destroy()

    def test_open_choice_strips_savedoriginal_and_sets_snapshot(self):
        """Regression: legacy savedOriginal keys must not be carried into new
        saves; the snapshot lives on the app, not inside the plan."""
        import tkinter as tk
        from folio_synthetic import TEST_MARKER
        plan = self.plan()
        plan["meta"][TEST_MARKER] = True
        plan["savedOriginal"] = {"meta": {"planName": "stale duplicate"}}
        self.app.guide_path = "/tmp/fake-guide.csp.json"
        try:
            self.vf.open_choice(self.app, plan)
            self.app.update_idletasks()
            self.assertNotIn("savedOriginal", self.app.active_plan)
            self.assertIsNotNone(self.app.saved_snapshot)
        finally:
            for widget in self.app.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()
            self.app.guide_path = None
            self.app.saved_snapshot = None
            self.vf.home_screen(self.app)

    def test_diagram_cards_contain_their_text_at_2x(self):
        """Regression: fixed card heights and the canvas width= phantom-space
        quirk spilled wrapped text out of its card at other interface scales."""
        import tkinter as tk
        import folio_theme as themes
        free_prefixes = ("PEOPLE", "NUMBERED GUIDE", "unsigned PSBT",
                         "signed PSBT", "THE AIR GAP", "ONLINE SIDE", "AIR-GAPPED")
        themes.set_scaling(self.app, 2.0)
        try:
            plan = self.plan()
            drawers = (lambda cv: self.vf.canvas_family_map(cv, plan),
                       lambda cv: self.vf.canvas_quorum(cv, plan["vaults"][0], 0),
                       lambda cv: self.vf.canvas_psbt_flow(cv, "QR codes"))
            for drawer in drawers:
                cv = tk.Canvas(self.app)
                drawer(cv)
                self.app.update_idletasks()
                rects = [cv.bbox(i) for i in cv.find_all()
                         if cv.type(i) == "rectangle"]
                self.assertTrue(rects, "diagram drew no cards")
                min_top = min(r[1] for r in rects)
                for i in cv.find_all():
                    if cv.type(i) != "text":
                        continue
                    bb = cv.bbox(i)
                    if bb[3] <= min_top + 2:
                        continue  # header band above the first card
                    text = cv.itemcget(i, "text")
                    if text.startswith(free_prefixes):
                        continue  # intentional labels outside cards
                    self.assertTrue(
                        any(r[0] <= bb[0] + 2 and r[1] <= bb[1] + 2 and
                            r[2] >= bb[2] - 2 and r[3] >= bb[3] - 2
                            for r in rects),
                        f"text spills its card: {text[:30]!r} bbox={bb}")
                cv.destroy()
        finally:
            themes.set_scaling(self.app, 1.0)


if __name__ == "__main__":
    unittest.main()
