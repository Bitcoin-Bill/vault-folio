"""Phase-1 setup interview. One plain question at a time; never a seed or key.

The interview fills the existing plan sheets. The current editor remains the
place to add or change answers afterward.
"""
import copy
import re
from datetime import date


def new_state():
    return {"plan_name": "", "owner": "", "wallets": [], "draft": {},
            "contact": "", "heirs": [], "map_holder": "", "restored": "",
            "test_spend": "", "wallets_done": False}


def rejects_secret(text):
    """Refuse a word list or an explicit key/seed. Places and names are allowed."""
    raw = (text or "").strip()
    if not raw:
        return False
    low = re.sub(r"[_-]+", " ", raw.casefold())
    if re.search(r"\b(?:seed(?:\s+(?:phrase|words?))?|private\s+key|secret\s+key|xprv|xpub|recovery\s+(?:phrase|words?))\b", low):
        return True
    words = [word.strip(".,;:").lower() for word in raw.split()]
    return 12 <= len(words) <= 24 and all(word.isalpha() and len(word) <= 10 for word in words)


def _wallet_ready(draft):
    structure = draft.get("structure")
    if structure not in ("single", "multi", "unsure") or not draft.get("name"):
        return False
    if not draft.get("delayed"):
        return False
    if draft.get("delayed") == "yes" and not draft.get("delayed_kind"):
        return False
    if structure == "single":
        return bool(draft.get("backup_copies"))
    if structure == "multi":
        return draft.get("n") == "unsure" or isinstance(draft.get("m"), int)
    return True


def interview_questions(state):
    """Return the questions still relevant for this state. Later answers drop out."""
    draft = state["draft"]
    questions = [
        ("plan_name", "What should this plan be called?",
         "A short name your family will recognize. Do not enter a seed or a key.", "text", None),
        ("owner", "Whose bitcoin does this plan describe?",
         "A name is enough.", "text", None),
        ("structure", "Does spending need one key, or several keys that must agree?",
         "Copies of the same backup are still one key. Do not type the key or the seed.",
         "choice", [("single", "One key"), ("multi", "Several keys must agree"), ("unsure", "I'm not sure")]),
    ]
    if not draft.get("structure"):
        return questions
    questions.append(("name", "What should your family call this setup?",
                      "For example, household savings.", "text", None))
    structure = draft.get("structure")
    if structure == "single":
        questions.append(("backup_copies", "Is the backup of that key in one place, or more than one?",
                          "This asks only how many places hold a copy. Not the seed words.",
                          "choice", [("one", "One place"), ("several", "More than one place"),
                                     ("unsure", "I'm not sure")]))
        if draft.get("backup_copies"):
            questions.append(("backup_where", "Where are the backup copies kept?",
                              "A broad description such as home safe or bank box is enough. Never enter backup words.",
                              "text", None))
    elif structure == "multi":
        questions.append(("n", "How many separate keys are there?",
                          "Count keys, not backup copies. Use 2 to 12, or not sure.", "number", None))
        if isinstance(draft.get("n"), int):
            questions.append(("m", "How many of those keys must agree before a spend?",
                              "This cannot be more than the number of keys.", "number", None))
            if isinstance(draft.get("m"), int):
                for i in range(draft["n"]):
                    questions.extend([
                        (f"key_label_{i}", f"What should key {i + 1} be called?",
                         "A label only, such as home signer. Not the seed.", "text", None),
                        (f"key_holder_{i}", f"Who holds key {i + 1}?",
                         "A person or role. This guide does not collect the key.", "text", None),
                        (f"key_where_{i}", f"Where does the backup for key {i + 1} live?",
                         "A non-secret place. Not the backup words.", "text", None),
                    ])
    if draft.get("name") and (structure != "multi" or draft.get("n") == "unsure" or isinstance(draft.get("m"), int)):
        questions.append(("delayed", "Is there a way to spend if those people cannot act?",
                          "A date written here does not lock bitcoin.",
                          "choice", [("no", "No"), ("yes", "Yes, after a delay"), ("unsure", "I'm not sure")]))
    if draft.get("delayed") == "yes":
        questions.append(("delayed_kind", "What controls that delay?",
                          "Choose the closest description.",
                          "choice", [("onchain", "A delay built into this setup’s policy"),
                                     ("provider", "A company or person releases access"),
                                     ("unsure", "I'm not sure")]))
        if draft.get("delayed_kind") == "onchain":
            questions.append(("delay", "What delay is documented?",
                              "For example, 12 months after the last activity. Leave blank if unknown.", "text", None))
    if structure == "multi" or draft.get("delayed") == "yes":
        questions.append(("config_where", "Where is the setup configuration copy?",
                          "The configuration, not a seed. Not sure is allowed.", "text", None))
    if _wallet_ready(draft):
        questions.append(("another", "Is there another setup to describe?",
                          "You can add more later in the plan editor.",
                          "choice", [("yes", "Yes, another setup"), ("no", "No, continue")]))
    if not state.get("wallets_done"):
        return questions
    questions.extend([
        ("contact", "Who should your family contact first?",
         "A name or role. This person is not asked for a key.", "text", None),
        ("heir", "Who else should be named as an heir?",
         "Leave blank if there is no one else to add.", "text", None),
        ("map_holder", "Who holds these instructions but no key?",
         "Leave blank if that is the same person as the first contact.", "text", None),
        ("restored", "Has anyone restored this without you?",
         "An untested backup is only a story.",
         "choice", [("yes", "Yes"), ("no", "Not yet"), ("unsure", "I'm not sure")]),
        ("test_spend", "Has there been a small test spend?",
         "A small spend the family controlled. Do not enter a transaction key.",
         "choice", [("yes", "Yes"), ("no", "Not yet"), ("unsure", "I'm not sure")]),
    ])
    return questions


def _clear_dependents(draft, key):
    if key == "structure":
        for stale in ("backup_copies", "backup_where", "n", "m", "keys", "delayed", "delayed_kind", "delay", "config_where", "another"):
            draft.pop(stale, None)
    elif key == "backup_copies":
        draft.pop("backup_where", None)
    elif key == "n":
        draft.pop("m", None)
        draft.pop("keys", None)
    elif key == "delayed":
        draft.pop("delayed_kind", None)
        draft.pop("delay", None)
    elif key == "delayed_kind":
        draft.pop("delay", None)


def apply_answer(state, key, value):
    """Record one answer. Returns an error string, or None."""
    if rejects_secret(value if isinstance(value, str) else ""):
        return "This guide never stores a seed, private key, or recovery phrase. Describe the place or the person, not the secret."
    draft = state["draft"]
    if key in ("plan_name", "owner", "contact", "map_holder", "restored", "test_spend"):
        state[key] = value
        return None
    if key == "heir":
        if value and value not in state["heirs"]:
            state["heirs"].append(value)
        return None
    if key == "another":
        if value == "yes":
            state["wallets"].append(copy.deepcopy(draft))
            state["draft"] = {}
        else:
            state["wallets"].append(copy.deepcopy(draft))
            state["draft"] = {}
            state["wallets_done"] = True
        return None
    if key.startswith("key_"):
        kind, index = key.split("_")[1], int(key.rsplit("_", 1)[-1])
        keys = draft.setdefault("keys", [])
        while len(keys) <= index:
            keys.append({})
        field = {"label": "label", "holder": "holder", "where": "where"}[kind]
        keys[index][field] = value
        return None
    if key in ("n", "m"):
        if value == "unsure":
            if key == "m":
                return "Choose not sure for the total first, or enter how many must agree."
            draft[key] = "unsure"
            _clear_dependents(draft, key)
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return "Enter a whole number, or choose not sure."
        if key == "n" and not 2 <= number <= 12:
            return "Enter a number from 2 to 12, or choose not sure."
        if key == "m":
            total = draft.get("n")
            if not isinstance(total, int) or not 1 <= number <= total:
                return "That number cannot be higher than the number of keys."
        draft[key] = number
        _clear_dependents(draft, key)
        return None
    previous = draft.get(key)
    draft[key] = value
    if previous != value:
        _clear_dependents(draft, key)
    return None


def build_plan(state):
    """Fill the existing sheet shape. Unknown stays unknown; no seed fields."""
    wallets = list(state["wallets"])
    if _wallet_ready(state["draft"]):
        wallets.append(state["draft"])
    plan = {
        "meta": {"app": "Vault Folio", "version": 1, "created": date.today().isoformat(),
                 "planName": state.get("plan_name") or "", "owner": state.get("owner") or "",
                 "jurisdiction": "", "legalNotes": ""},
        "people": {"executor": state.get("contact") or "", "trustee": state.get("map_holder") or "",
                   "helper": "", "heirs": [{"name": name} for name in state.get("heirs") or []]},
        "vaults": [],
        "signing": {"medium": "", "verifyRitual": [], "testSpend": state.get("test_spend") or "",
                    "coordinatorNotes": ""},
        "backups": {"descriptorLocations": [], "watchOnly": "", "rescanHeight": "",
                    "sampleAddresses": "", "testedSoftware": ""},
        "inheritance": {"mechanism": "", "releaseConditions": "", "legalDocs": "",
                        "letterLocation": "", "heartbeat": "", "canary": ""},
        "rehearsal": {"restoreDrill": state.get("restored") or "", "familyWalkthrough": "",
                      "testSpendDate": "", "notes": ""},
        "ownerNotes": "Started from the phase-1 setup interview. Seeds and keys were not requested.",
    }
    any_delay = False
    any_multi = False
    for wallet in wallets:
        structure = wallet.get("structure") if wallet.get("structure") in ("single", "multi") else "unknown"
        record = {"name": wallet.get("name") or "Wallet", "setupType": structure,
                  "coordinator": "", "timelock": {"enabled": False, "delay": ""}, "keys": [],
                  "intakeAnswers": {k: v for k, v in wallet.items() if k != "keys"}}
        if structure == "single":
            record.update({"m": 1, "n": 1, "script": "Single-signature (one key)",
                           "backupCopyArrangement": wallet.get("backup_copies") or "unsure"})
            record["keys"] = [{"label": "Key A", "locations": wallet.get("backup_where") or ""}]
        elif structure == "multi":
            record.update({"m": wallet.get("m") if isinstance(wallet.get("m"), int) else "",
                           "n": wallet.get("n") if isinstance(wallet.get("n"), int) else "",
                           "script": "Not sure yet"})
            any_multi = True
            for key in wallet.get("keys") or []:
                record["keys"].append({"label": key.get("label") or "", "locations": key.get("where") or "",
                                       "notes": key.get("holder") or ""})
        else:
            record.update({"m": "", "n": "", "script": "Not sure yet"})
        if wallet.get("delayed") == "yes" and wallet.get("delayed_kind") == "onchain":
            record["timelock"] = {"enabled": True, "delay": wallet.get("delay") or ""}
            any_delay = True
        elif wallet.get("delayed") == "yes":
            any_delay = True
        if wallet.get("config_where"):
            plan["backups"]["descriptorLocations"].append(
                {"where": wallet["config_where"], "format": "Wallet configuration copy"})
        plan["vaults"].append(record)
    if any_multi and any_delay:
        plan["inheritance"]["mechanism"] = "Combination of the above"
    elif any_delay:
        plan["inheritance"]["mechanism"] = "On-chain timelock decay — recovery path opens after inactivity (Liana/Nunchuk style)"
    elif any_multi:
        plan["inheritance"]["mechanism"] = "Distributed keys — heirs reach a quorum via trustee/executor after death"
    else:
        plan["inheritance"]["mechanism"] = "Letter + executor only (simple, single-sig or small amounts)"
    return plan


def start_phase1(app, start_editor, on_cancel):
    import tkinter as tk
    from tkinter import messagebox
    interview = _Interview(app, start_editor, on_cancel, tk, messagebox)
    interview.show()
    return interview


class _Interview:
    def __init__(self, app, start_editor, on_cancel, tk, messagebox):
        self.app = app
        self.start_editor = start_editor
        self.on_cancel = on_cancel
        self.tk = tk
        self.messagebox = messagebox
        self.state = new_state()
        self.history = []
        self.index = 0
        self.value = tk.StringVar()
        self.restore_value = None

    def show(self):
        self.app.clear()
        self.app.header("SETUP INTERVIEW · NO SEEDS OR KEYS", ok=True)
        self.frame = self.tk.Frame(self.app, bg="#fafaf8")
        self.frame.pack(fill="both", expand=True)
        self.render()

    def render(self):
        for child in self.frame.winfo_children():
            child.destroy()
        questions = interview_questions(self.state)
        self.index = min(self.index, max(0, len(questions) - 1))
        key, title, help_text, kind, options = questions[self.index]
        pad = self.tk.Frame(self.frame, bg="#fafaf8")
        pad.pack(fill="both", expand=True, padx=70, pady=36)
        self.tk.Label(pad, text=f"QUESTION {self.index + 1} OF {len(questions)}",
                      font=("Courier", 9), bg="#fafaf8", fg="#6b6b6b").pack(anchor="w")
        self.tk.Label(pad, text=title, font=("Georgia", 22), bg="#fafaf8", fg="#0a0a0a",
                      wraplength=720, justify="left").pack(anchor="w", pady=(8, 8))
        self.tk.Label(pad, text=help_text, font=("Helvetica", 11), bg="#fafaf8", fg="#2e2e2e",
                      wraplength=720, justify="left").pack(anchor="w", pady=(0, 16))
        self.value.set(self.restore_value if self.restore_value is not None else "")
        self.restore_value = None
        if kind == "choice":
            for value, label in options:
                self.tk.Radiobutton(pad, text=label, value=value, variable=self.value,
                                    font=("Helvetica", 12), bg="#fafaf8", anchor="w").pack(anchor="w", pady=3)
        else:
            entry = self.tk.Entry(pad, textvariable=self.value, font=("Helvetica", 13), width=52)
            entry.pack(anchor="w", ipady=6)
            entry.focus_set()
            if kind == "number":
                self.tk.Button(pad, text="I'M NOT SURE", command=lambda: self.answer("unsure")).pack(anchor="w", pady=(8, 0))
        row = self.tk.Frame(pad, bg="#fafaf8")
        row.pack(anchor="w", pady=(22, 0))
        self.tk.Button(row, text="BACK", command=self.back).pack(side="left", padx=(0, 8))
        self.tk.Button(row, text="NEXT", command=self.next).pack(side="left")
        self.tk.Label(pad, text="This interview fills the plan. You can edit every sheet afterward. It never asks for a seed or a key.",
                      font=("Courier", 8), bg="#fafaf8", fg="#6b6b6b", wraplength=720, justify="left").pack(anchor="w", pady=(24, 0))

    def answer(self, value):
        self.value.set(value)
        self.next()

    def next(self):
        questions = interview_questions(self.state)
        key, _title, _help, kind, _options = questions[self.index]
        value = self.value.get().strip()
        if kind == "choice" and not value:
            self.messagebox.showinfo("Vault Folio", "Choose an answer, including “I'm not sure.”")
            return
        self.history.append((copy.deepcopy(self.state), self.index, value))
        error = apply_answer(self.state, key, value)
        if error:
            self.state, self.index, _answer = self.history.pop()
            self.messagebox.showinfo("Vault Folio", error)
            return
        if key == "another" and value == "yes":
            self.index = next(i for i, item in enumerate(interview_questions(self.state)) if item[0] == "structure")
            self.render()
            return
        if key == "test_spend":
            self.finish()
            return
        self.index += 1
        self.render()

    def back(self):
        if not self.history:
            self.on_cancel()
            return
        self.state, self.index, self.restore_value = self.history.pop()
        self.render()

    def finish(self):
        plan = build_plan(self.state)
        self.app.clear()
        pad = self.tk.Frame(self.app, bg="#fafaf8")
        pad.pack(fill="both", expand=True, padx=70, pady=36)
        self.tk.Label(pad, text="HERE IS WHAT YOU SAID", font=("Courier", 9), bg="#fafaf8", fg="#6b6b6b").pack(anchor="w")
        self.tk.Label(pad, text=plan["meta"].get("planName") or "Untitled plan",
                      font=("Georgia", 22), bg="#fafaf8").pack(anchor="w", pady=(6, 12))
        lines = [f"Owner: {plan['meta'].get('owner') or 'Not named'}",
                 f"Wallets: {len(plan['vaults'])}",
                 f"First contact: {plan['people'].get('executor') or 'Not named'}"]
        for vault in plan["vaults"]:
            lines.append(f"{vault.get('name')}: {vault.get('setupType')} — no seed stored")
        for line in lines:
            self.tk.Label(pad, text=line, font=("Helvetica", 12), bg="#fafaf8", anchor="w").pack(anchor="w", pady=2)
        self.tk.Button(pad, text="EDIT THE PLAN", command=lambda: self.start_editor(plan)).pack(anchor="w", pady=(18, 0))
