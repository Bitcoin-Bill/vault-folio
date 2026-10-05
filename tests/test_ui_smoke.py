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


if __name__ == "__main__":
    unittest.main()
