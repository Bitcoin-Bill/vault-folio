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

    def _big_picture_widgets(self):
        import tkinter as tk
        self.vf.show_heir(self.app, self.plan())
        self.app.update_idletasks()
        def walk(w):
            yield w
            for child in w.winfo_children():
                yield from walk(child)
        nav = next(w for w in walk(self.app) if isinstance(w, tk.Listbox))
        nav.selection_clear(0, 'end')
        nav.selection_set(1)
        nav.event_generate('<<ListboxSelect>>')
        self.app.update_idletasks()
        canvas = max((w for w in walk(self.app) if isinstance(w, tk.Canvas)),
                     key=lambda w: len(w.find_all()))
        sheet = canvas.master
        while not isinstance(sheet, self.vf.ui.ScrollFrame):
            sheet = sheet.master
        return canvas, sheet, walk

    def test_big_picture_reflows_at_minimum_window_and_large_text(self):
        try:
            self.vf.themes.set_scaling(self.app, 1.0)
            self.app.geometry('1100x760')
            cv, sheet, _ = self._big_picture_widgets()
            for factor in (1.0, 1.6):
                self.vf.themes.set_scaling(self.app, factor)
                self.app.update_idletasks()
                tags = dict.fromkeys(cv.gettags(i)[0] for i in cv.find_all()
                                     if cv.type(i) == 'rectangle')
                rectangles = [cv.find_withtag(tag)[0] for tag in tags]
                self.assertGreater(len(rectangles), 4)
                for rect in rectangles:
                    tag = cv.gettags(rect)[0]
                    x0, y0, x1, y1 = cv.bbox(tag)
                    self.assertGreaterEqual(x0, 0)
                    self.assertLessEqual(x1, cv.winfo_width())
                    texts = [i for i in cv.find_withtag(tag) if cv.type(i) == 'text']
                    self.assertLess(cv.bbox(texts[0])[3], cv.bbox(texts[1])[1])
                    self.assertLessEqual(cv.bbox(texts[1])[3], cv.coords(rect)[3])
                    # Move each box's center into the visible vertical viewport.
                    content_y = cv.winfo_rooty() - sheet.inner.winfo_rooty() + (y0 + y1) / 2
                    total = sheet.canvas.bbox('all')[3]
                    sheet.canvas.yview_moveto(max(0, (content_y - sheet.canvas.winfo_height()/2) / total))
                    self.app.update_idletasks()
                    center = cv.winfo_rooty() + (y0 + y1) / 2
                    self.assertGreaterEqual(center, sheet.canvas.winfo_rooty())
                    self.assertLessEqual(center, sheet.canvas.winfo_rooty() + sheet.canvas.winfo_height())
        finally:
            self.vf.themes.set_scaling(self.app, 1.0)
            self.app.geometry('1280x900')

    def test_big_picture_lower_click_explanation_stays_in_viewport(self):
        import tkinter as tk
        self.app.geometry('1100x760')
        try:
            cv, sheet, walk = self._big_picture_widgets()
            item = next(i for i in cv.find_all() if cv.type(i) == 'text'
                        and cv.itemcget(i, 'text') == 'Broadcast')
            x0, y0, x1, y1 = cv.bbox(item)
            content_y = cv.winfo_rooty() - sheet.inner.winfo_rooty() + (y0+y1)/2
            sheet.canvas.yview_moveto((content_y - sheet.canvas.winfo_height()/2) / sheet.canvas.bbox('all')[3])
            self.app.update_idletasks()
            cv.event_generate('<Button-1>', x=int((x0+x1)/2), y=int((y0+y1)/2))
            self.app.update_idletasks()
            label = next(w for w in walk(self.app) if isinstance(w, tk.Label)
                         and str(w.cget('text')).startswith('The signed transaction'))
            self.assertTrue(label.winfo_ismapped())
            self.assertGreaterEqual(label.winfo_rooty(), self.app.winfo_rooty())
            self.assertLessEqual(label.winfo_rooty()+label.winfo_height(),
                                 sheet.canvas.winfo_rooty())
            self.assertLess(label.winfo_rooty()+label.winfo_height(),
                            self.app.winfo_rooty()+self.app.winfo_height())
        finally:
            self.app.geometry('1280x900')

    def test_big_picture_page_draws_and_explains(self):
        """The word-light recovery chain: page renders from plan facts, and
        clicking a box shows its plain-language explanation."""
        import tkinter as tk
        plan = self.plan()  # 2-of-3 vault with Coldcard A, Jade B, Signer C
        self.vf.show_heir(self.app, plan)
        self.app.update_idletasks()

        def find(widget, cls, out):
            if isinstance(widget, cls):
                out.append(widget)
            for child in widget.winfo_children():
                find(child, cls, out)

        navs, canvases, labels = [], [], []
        find(self.app, tk.Listbox, navs)
        self.assertIn("big picture", str(navs[0].get(1)))
        navs[0].selection_clear(0, "end")
        navs[0].selection_set(1)
        navs[0].event_generate("<<ListboxSelect>>")
        self.app.update_idletasks()
        find(self.app, tk.Canvas, canvases)
        self.assertTrue(canvases, "big picture canvas missing")
        cv = max(canvases, key=lambda c: len(c.find_all()))  # not the ScrollFrame's window canvas
        self.assertGreater(len(cv.find_all()), 20, "chain not drawn")
        # click the Coldcard A key box
        target = next(i for i in cv.find_all()
                      if cv.type(i) == "text" and cv.itemcget(i, "text") == "Coldcard A")
        tag = cv.gettags(target)[0]
        x0, y0, x1, y1 = cv.bbox(tag)
        cv.event_generate("<Button-1>", x=(x0 + x1) // 2, y=(y0 + y1) // 2)
        self.app.update_idletasks()
        find(self.app, tk.Label, labels)
        self.assertTrue(any("One signing key" in str(lb.cget("text")) for lb in labels),
                        "clicking the box did not show its explanation")

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
            if isinstance(widget, (tk.Checkbutton, self.vf.ui.CheckRow)):
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
            if isinstance(widget, (tk.Button, self.vf.ui.FlatButton)):
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
            if isinstance(widget, (tk.Button, self.vf.ui.FlatButton)):
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

    def test_mid_interview_heir_round_trip_preserves_pending_answer(self):
        """Regression: HEIR VIEW mid-wallet-interview used to construct a fresh
        Wizard on return, resetting the step and losing a half-typed answer."""
        import tkinter as tk
        plan = self.plan()
        wizard = self.vf.start_wizard(self.app, plan)
        vaults_step = next(i for i, (sid, _t) in enumerate(self.vf.STEP_DEFS) if sid == "vaults")
        wizard.goto(vaults_step)
        wizard.begin_vault_intake()
        self.app.update_idletasks()
        wizard.intake_value.set("multi")  # chosen but NOT committed (NEXT never pressed)
        wizard.to_heir()
        self.app.update_idletasks()
        buttons = {}

        def walk(widget):
            if isinstance(widget, (tk.Button, self.vf.ui.FlatButton)):
                buttons[str(widget.cget("text"))] = widget
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        buttons["← BACK TO EDITOR"].invoke()
        self.app.update_idletasks()
        self.assertIs(self.app.wizard, wizard)                # same wizard, not a fresh one
        self.assertEqual(wizard.step, vaults_step)            # still on the vaults step
        self.assertIsNotNone(wizard.vault_intake)             # interview still active
        self.assertEqual(wizard.intake_value.get(), "multi")  # pending answer restored
        self.assertEqual(wizard.vault_intake["answers"], {})  # but never auto-committed

    def test_intake_options_are_drawn_rows_that_set_the_answer(self):
        """macOS Aqua renders native radiobutton labels invisibly (blank
        options), so intake choices must be app-drawn RadioRows that still
        drive the same StringVar."""
        plan = self.plan()
        wizard = self.vf.start_wizard(self.app, plan)
        wizard.goto(next(i for i, (sid, _t) in enumerate(self.vf.STEP_DEFS) if sid == "vaults"))
        wizard.begin_vault_intake()
        self.app.update_idletasks()
        rows = []

        def walk(widget):
            if isinstance(widget, self.vf.ui.RadioRow):
                rows.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        self.assertGreaterEqual(len(rows), 3, "intake choice rows not rendered")
        labels = [str(row.cget("text")) for row in rows]
        self.assertTrue(any("single-signature" in label for label in labels), labels)
        rows[1].invoke()
        self.assertEqual(wizard.intake_value.get(), "multi")

    def test_button_style_toggle_switches_button_widgets(self):
        """Session-only button style: flat draws FlatButtons, classic uses
        native tk.Buttons; switching rebuilds the current screen in place."""
        import tkinter as tk
        ui = self.vf.ui

        def buttons():
            found = []
            def walk(widget):
                if isinstance(widget, (tk.Button, ui.FlatButton)):
                    found.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(self.app)
            return found

        try:
            self.vf.themes.set_button_style("classic", self.app)
            self.app.update_idletasks()
            classic = buttons()
            self.assertTrue(classic, "no buttons rendered in classic mode")
            self.assertFalse(any(isinstance(b, ui.FlatButton) for b in classic))
            self.vf.themes.set_button_style("flat", self.app)
            self.app.update_idletasks()
            self.assertTrue(any(isinstance(b, ui.FlatButton) for b in buttons()))
        finally:
            ui.set_button_style("flat")
            self.vf.home_screen(self.app)
            self.app.update_idletasks()

    def test_style_switch_preserves_uncommitted_intake(self):
        wizard = self.vf.start_wizard(self.app, self.plan())
        wizard.goto(next(i for i, (sid, _) in enumerate(self.vf.STEP_DEFS) if sid == "vaults"))
        wizard.begin_vault_intake()
        wizard.intake_value.set("multi")
        wizard.advance_vault_intake()
        key = wizard.vault_intake_questions()[wizard.vault_intake["index"]][0]
        wizard.intake_value.set("unfinished invented answer")
        try:
            for style in ("classic", "flat"):
                self.vf.themes.set_button_style(style, self.app)
                self.app.update()
                self.assertEqual(wizard.intake_value.get(), "unfinished invented answer")
                self.assertNotIn(key, wizard.vault_intake["answers"])
        finally:
            self.vf.ui.set_button_style("flat")
            self.vf.home_screen(self.app)

    def test_flat_button_release_cancellation_and_keyboard(self):
        self.vf.home_screen(self.app)
        calls = []
        button = self.vf.ui.FlatButton(self.app, text="REMOVE invented record",
                                      command=lambda: calls.append(True))
        button.pack()
        self.app.update()
        label = button._label
        label.event_generate("<ButtonPress-1>", x=5, y=5)
        self.app.update()
        self.assertEqual(calls, [])
        label.event_generate("<ButtonRelease-1>", x=-100, y=-100)
        self.app.update()
        self.assertEqual(calls, [])
        label.event_generate("<ButtonPress-1>", x=5, y=5)
        label.event_generate("<ButtonRelease-1>", x=5, y=5)
        self.app.update()
        self.assertEqual(len(calls), 1)
        button.configure(state="disabled")
        label.event_generate("<ButtonPress-1>", x=5, y=5)
        label.event_generate("<ButtonRelease-1>", x=5, y=5)
        self.assertEqual(len(calls), 1)
        button.configure(state="normal")
        button.focus_force()
        self.app.update()
        for key in ("space", "Return"):
            before = len(calls)
            button.event_generate("<KeyPress-" + key + ">")
            button.event_generate("<KeyPress-" + key + ">")
            self.assertEqual(len(calls), before)
            button.event_generate("<KeyRelease-" + key + ">")
            self.app.update()
            self.assertEqual(len(calls), before + 1)
        button.destroy()

    def test_choice_rows_release_inside_and_drag_away(self):
        import tkinter as tk
        self.vf.home_screen(self.app)
        for cls in (self.vf.ui.CheckRow, self.vf.ui.RadioRow):
            var = tk.StringVar(value="")
            calls = []
            row = cls(self.app, "invented choice", var, value="chosen",
                      command=lambda: calls.append(True))
            row.pack()
            self.app.update()
            for target in (row, row._canvas, row._label):
                target.event_generate("<Button-1>", x=5, y=5)
                self.assertEqual(var.get(), "")
                self.assertEqual(calls, [])
                target.event_generate("<ButtonRelease-1>", x=-100, y=-100)
                self.assertEqual(var.get(), "")
                self.assertEqual(calls, [])
                target.event_generate("<Button-1>", x=5, y=5)
                target.event_generate("<ButtonRelease-1>", x=5, y=5)
                self.assertTrue(var.get())
                self.assertEqual(calls, [True])
                var.set("")
                calls.clear()
            row.destroy()

    def test_pending_interview_answer_survives_back_without_committing(self):
        wizard = self.vf.start_wizard(self.app, self.plan())
        wizard.goto(next(i for i, (sid, _) in enumerate(self.vf.STEP_DEFS) if sid == "vaults"))
        wizard.begin_vault_intake()
        wizard.intake_value.set("single")
        wizard.forward()
        self.assertEqual(wizard.vault_intake_questions()[1][0], "name")
        wizard.intake_value.set("Half typed wallet ")
        wizard.back()
        self.assertEqual(wizard.intake_value.get(), "single")
        self.assertNotIn("name", wizard.vault_intake["answers"])
        wizard.forward()
        self.assertEqual(wizard.intake_value.get(), "Half typed wallet ")
        self.assertNotIn("name", wizard.vault_intake["answers"])
        self.assertEqual(wizard.vault_intake["pending"], {"name": "Half typed wallet "})
        wizard.forward()
        self.assertEqual(wizard.vault_intake["answers"]["name"], "Half typed wallet")
        self.assertNotIn("name", wizard.vault_intake["pending"])

    def test_locked_text_control_whitelist(self):
        import tkinter as tk
        from types import SimpleNamespace
        from unittest.mock import patch
        wizard = self.vf.start_wizard(self.app, self.plan())
        target = tk.Text(self.app)
        target.pack()
        self.addCleanup(target.destroy)
        original = "Saved text must stay intact"
        target.insert("1.0", original)
        with patch.object(wizard, "saved_value", return_value=original), \
                patch.object(self.vf.messagebox, "showwarning") as warning:
            with patch.object(target, "bind", wraps=target.bind) as bindings:
                self.assertTrue(wizard.lock_saved(target, "meta.legalNotes"))
            block = next(call.args[1] for call in bindings.call_args_list
                         if call.args[0] == "<Key>")
            # Capture the actual callback as well as exercising Tk's real event
            # dispatch: a virtual Cut/Paste binding alone cannot satisfy this.
            for key in ("x", "v", "a", "z"):
                warning.reset_mock()
                result = block(SimpleNamespace(state=0x4, keysym=key))
                self.assertEqual(result, "break")
                warning.assert_called_once()
            for key in ("c", "C", "Insert", "Left"):
                warning.reset_mock()
                result = block(SimpleNamespace(state=0x4, keysym=key))
                self.assertNotEqual(result, "break")
                warning.assert_not_called()
            self.app.update()
            target.focus_force()
            self.app.update()
            target.clipboard_clear()
            target.clipboard_append("replacement")
            for event in ("<Control-x>", "<Control-v>"):
                target.tag_add("sel", "1.0", "end-1c")
                target.event_generate(event)
                self.app.update()
                self.assertEqual(target.get("1.0", "end-1c"), original)
            warning.reset_mock()
            target.event_generate("<Control-c>")
            self.app.update()
            warning.assert_not_called()
            self.assertEqual(target.clipboard_get(), original)

    def test_locked_text_refuses_cut_shortcut(self):
        """Regression: Ctrl+X slipped past the <Key> block via the <<Cut>>
        virtual event, so a 'locked' saved entry could be cut on screen."""
        import copy
        import tkinter as tk
        orig_warn = self.vf.messagebox.showwarning
        self.vf.messagebox.showwarning = lambda *a, **k: None  # keep the test modal-free
        self.addCleanup(setattr, self.vf.messagebox, "showwarning", orig_warn)
        plan = self.plan()
        plan["meta"]["legalNotes"] = "SAVED LEGAL NOTE — must not change"
        self.app.saved_snapshot = copy.deepcopy(plan)
        wizard = self.vf.start_wizard(self.app, plan)
        wizard.goto(next(i for i, (sid, _t) in enumerate(self.vf.STEP_DEFS) if sid == "identity"))
        self.app.update_idletasks()
        texts = []

        def walk(widget):
            if isinstance(widget, tk.Text):
                texts.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        target = next(t for t in texts if "SAVED LEGAL NOTE" in t.get("1.0", "end"))
        target.tag_add("sel", "1.0", "end")
        target.event_generate("<<Cut>>")
        self.app.update_idletasks()
        self.assertIn("SAVED LEGAL NOTE — must not change", target.get("1.0", "end"))
        self.assertEqual(plan["meta"]["legalNotes"], "SAVED LEGAL NOTE — must not change")

    def test_locked_combobox_reverts_dropdown_changes(self):
        """Regression: a readonly ttk.Combobox still allows choosing another
        option (mouse or arrows); the locked value must be re-asserted."""
        import copy
        from tkinter import ttk
        orig_warn = self.vf.messagebox.showwarning
        self.vf.messagebox.showwarning = lambda *a, **k: None  # keep the test modal-free
        self.addCleanup(setattr, self.vf.messagebox, "showwarning", orig_warn)
        plan = self.plan()
        plan["rehearsal"]["familyWalkthrough"] = "Not yet"
        self.app.saved_snapshot = copy.deepcopy(plan)
        wizard = self.vf.start_wizard(self.app, plan)
        wizard.goto(next(i for i, (sid, _t) in enumerate(self.vf.STEP_DEFS) if sid == "rehearsal"))
        self.app.update_idletasks()
        combos = []

        def walk(widget):
            if isinstance(widget, ttk.Combobox):
                combos.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(self.app)
        target = next(c for c in combos if c.get() == "Not yet")
        target.set("Yes — they found everything unaided")
        target.event_generate("<<ComboboxSelected>>")
        self.app.update_idletasks()
        self.assertEqual(target.get(), "Not yet")
        self.assertEqual(plan["rehearsal"]["familyWalkthrough"], "Not yet")

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


@unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")
class UbuntuTestModeExportTests(unittest.TestCase):
    """page_export only takes its real branch outside synthetic test mode, so
    the shared test app (test_mode=True) never exercised it: a button-factory
    contract bug crashed the page below the unlock-methods card and hid SAVE.
    Render it in ubuntu-test mode, which takes the real branch."""

    @classmethod
    def setUpClass(cls):
        cls.vf = load_app_module()
        cls.app = cls.vf.App(ubuntu_test=True)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def _export_page(self):
        wizard = self.vf.start_wizard(self.app, self.vf.blank_plan())
        wizard.goto(len(self.vf.STEP_DEFS) - 1)  # "export" is the last step
        self.app.update_idletasks()
        return wizard

    @staticmethod
    def _flat_buttons(widget):
        found = []
        for child in widget.winfo_children():
            if isinstance(child, UbuntuTestModeExportTests.vf.ui.FlatButton):
                found.append(child)
            found.extend(UbuntuTestModeExportTests._flat_buttons(child))
        return found

    def test_export_page_renders_unlock_and_save_controls(self):
        self._export_page()
        texts = {b.cget("text") for b in self._flat_buttons(self.app)}
        self.assertIn("ADD PASSPHRASE", texts)
        self.assertIn("SAVE ENCRYPTED GUIDE", texts)

    def test_passphrase_dialog_opens(self):
        """Same contract bug crashed the enrollment dialog (pady tuple)."""
        self._export_page()
        add = next(b for b in self._flat_buttons(self.app)
                   if b.cget("text") == "ADD PASSPHRASE")
        before = set(self.app.winfo_children())
        add.invoke()
        self.app.update_idletasks()
        dialogs = [w for w in self.app.winfo_children() if w not in before]
        self.assertEqual(len(dialogs), 1, "passphrase dialog did not open")
        texts = {b.cget("text") for b in self._flat_buttons(dialogs[0])}
        self.assertIn("USE THIS PASSPHRASE", texts)
        dialogs[0].destroy()
        self.app.update_idletasks()


@unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")
class WheelScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vf = load_app_module()
        cls.app = cls.vf.App(test_mode=True)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_wheel_notch_scrolls_sheet_by_fixed_pixels(self):
        """Canvas scroll units default to viewport fractions; with
        yscrollincrement=1 one notch must move a small fixed pixel count."""
        import tkinter as tk
        sheet = self.vf.ui.ScrollFrame(self.app)
        sheet.pack(fill="both", expand=True)
        filler = tk.Frame(sheet.inner, height=4000, width=200)
        filler.pack()
        self.app.update_idletasks()
        filler.event_generate("<Button-5>", x=5, y=5)
        self.app.update_idletasks()
        top = sheet.canvas.yview()[0]
        height = sheet.canvas.bbox("all")[3]
        moved = top * height
        self.assertGreater(moved, 0, "wheel notch did not scroll the sheet")
        self.assertLessEqual(moved, 80, f"one notch moved {moved:.0f}px — viewport-fraction scrolling")
        sheet.destroy()
        self.app.update_idletasks()


@unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")
class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vf = load_app_module()
        cls.app = cls.vf.App(test_mode=True)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    @staticmethod
    def _walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from SettingsDialogTests._walk(child)

    def test_settings_dialog_scrolls_and_fits_the_screen(self):
        dialog = self.vf.themes.open_settings(self.app)
        self.app.update_idletasks()
        sheets = [w for w in self._walk(dialog)
                  if isinstance(w, self.vf.ui.ScrollFrame)]
        self.assertTrue(sheets, "settings dialog content is not scrollable")
        self.assertLessEqual(dialog.winfo_height(), dialog.winfo_screenheight() - 40)
        dialog.destroy()
        self.app.update_idletasks()

    def test_seedqr_medium_option_mirrored_in_both_editions(self):
        import folio_catalog
        self.assertIn("Paper QR (SeedQR)", self.vf.MEDIA)        # vault key backup media
        self.assertIn("Paper QR (SeedQR)", folio_catalog.MEDIA)  # backup record media
        path = os.path.join(os.path.dirname(__file__), "..", "browser-edition", "index.html")
        with open(path, encoding="utf-8") as handle:
            html = handle.read()
        self.assertIn("Paper QR (SeedQR)", html)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(DISPLAY, "needs a display (xvfb-run)")
class ScrollAndComboBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vf = load_app_module()
        cls.app = cls.vf.App(test_mode=True)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_wheel_over_combobox_scrolls_sheet_and_keeps_value(self):
        """Native wheel-over-combobox cycled the value and rebuilt wizard
        pages mid-scroll ('screen goes blank'). The class binding must scroll
        the sheet instead and leave the selection alone."""
        import tkinter as tk
        import folio_ui as ui
        self.app.clear()
        sheet = ui.ScrollFrame(self.app)
        sheet.pack(fill="both", expand=True)
        var = tk.StringVar(value="Alpha")
        cb = ui.option_combo(sheet.inner, var, ["Alpha", "Beta", "Gamma"])
        cb.pack(anchor="w")
        for i in range(80):
            tk.Label(sheet.inner, text=f"filler {i}", bg=ui.PAPER, fg=ui.INK).pack()
        self.app.update_idletasks()
        cb.event_generate("<Button-5>", x=4, y=4)
        self.app.update_idletasks()
        self.assertEqual(var.get(), "Alpha", "wheel cycled the combobox value")
        self.assertGreater(sheet.canvas.yview()[0], 0, "sheet did not scroll")
        cb.event_generate("<Button-4>", x=4, y=4)
        self.app.update_idletasks()
        self.assertEqual(var.get(), "Alpha")

    def test_option_combo_opens_on_click_anywhere(self):
        """Wide questionnaire dropdowns looked broken: only the far-right
        arrow opened them. A click in the text area must post the list."""
        import tkinter as tk
        import folio_ui as ui
        self.app.clear()
        var = tk.StringVar(value="")
        cb = ui.option_combo(self.app, var, ["One", "Two"], editable=True)
        cb.pack()
        self.app.update_idletasks()
        cb.event_generate("<Button-1>", x=4, y=4)
        self.app.update_idletasks()
        self.assertTrue(cb.tk.call("winfo", "exists", cb._w + ".popdown"),
                        "dropdown did not post on click")
        cb.tk.call("ttk::combobox::Unpost", cb._w)

    def test_editable_combo_allows_free_text(self):
        """Backup-status style fields: presets are suggestions, typing a
        custom value must work (state normal, not readonly)."""
        import tkinter as tk
        import folio_ui as ui
        var = tk.StringVar(value="")
        cb = ui.option_combo(self.app, var, ["Preset A"], editable=True)
        cb.pack()
        self.assertEqual(str(cb.cget("state")), "normal")
        cb.insert(0, "my own words")
        self.assertEqual(var.get(), "my own words")
        cb.destroy()
