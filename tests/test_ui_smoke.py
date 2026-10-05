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

    def test_detail_window_constructs(self):
        self.vf.show_tree_detail("Key 1", [("Holder", "Ada"), ("Location", "home safe")])
        self.app.update_idletasks()


if __name__ == "__main__":
    unittest.main()
