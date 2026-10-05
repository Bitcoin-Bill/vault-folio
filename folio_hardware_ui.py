"""Desktop-only experimental single-key unlock UI; no secret persistence."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import folio_security as security
from folio_storage import save_encrypted


def hardware_job(app, operation, on_success, environment_safe, key_labels=None):
    """Keep tkinter responsive while a user touches the key / PBKDF2 runs.

    All UI calls are on the main thread. Recheck isolation before and after the
    operation; do not display plaintext or write a file on an unsafe result.
    """
    key_labels = key_labels or ["Enrolled YubiKey"]
    pending = queue.Queue()
    cancelled = threading.Event()
    window = tk.Toplevel(app)
    window.title("Offline hardware operation")
    window.transient(app)
    window.grab_set()
    tk.Label(window, text="Keep this machine offline. Connect only the requested key.\n"
             "Touch it when it flashes. Allow up to 40 seconds.", padx=24, pady=20).pack()
    status = tk.StringVar(value="Checking environment…")
    tk.Label(window, textvariable=status, padx=20, pady=10).pack()
    def cancel():
        cancelled.set()
        status.set("Cancelling; waiting for the device operation to finish…")
    tk.Button(window, text="Cancel", command=cancel).pack(pady=12)
    window.protocol("WM_DELETE_WINDOW", cancel)

    def provider(challenge, slot):
        if cancelled.is_set():
            raise ValueError("Operation cancelled.")
        ready = threading.Event()
        pending.put(("touch", (slot, ready)))
        if not ready.wait(120) or cancelled.is_set():
            raise ValueError("Operation cancelled.")
        return security.yubikey_response(challenge, slot)

    def work():
        try:
            if not environment_safe():
                raise ValueError("Offline environment check failed.")
            result = operation(provider)
            if cancelled.is_set() or not environment_safe():
                raise ValueError("Cancelled or unsafe environment. No file saved / plan opened.")
            pending.put(("done", result))
        except Exception as exc:
            # Only our ValueErrors are user-safe; do not expose library diagnostics.
            pending.put(("error", str(exc) if isinstance(exc, ValueError) else "Hardware operation failed."))

    number = 0
    def poll():
        nonlocal number
        try:
            kind, result = pending.get_nowait()
        except queue.Empty:
            app.after(100, poll)
            return
        if kind == "touch":
            number += 1
            slot, ready = result
            if getattr(app, "_locked", False):
                cancelled.set()
            elif not cancelled.is_set():
                if not messagebox.askokcancel("Connect key", f"Connect {key_labels[min(number-1, len(key_labels)-1)]} only (OTP slot {slot}).\n"
                                               "This is one independent unlock method.\n"
                                               "Press OK, then touch the flashing key.", parent=window):
                    cancelled.set()
                status.set(f"Waiting for key #{number}…")
            ready.set()
            app.after(100, poll)
            return
        window.destroy()
        if cancelled.is_set() or getattr(app, "_locked", False):
            messagebox.showwarning("Cancelled", "Operation cancelled or session locked. Nothing opened or saved.", parent=app)
        elif kind == "error":
            messagebox.showerror("Unable to continue", result, parent=app)
        else:
            on_success(result)
    threading.Thread(target=work, daemon=True).start()
    app.after(100, poll)


def add_export_controls(parent, app, plan, environment_safe):
    frame = ttk.LabelFrame(parent, text="Choose any ways your family can unlock this guide")
    frame.pack(fill="x", pady=12)
    tk.Label(frame, justify="left", wraplength=620, text=
             "Any ONE configured method opens the guide. No combination or quorum is required.\n"
             "Use a passphrase, a YubiKey, family questions, or several independent alternatives.\n"
             "Method labels and recovery questions are visible before unlocking; keep them non-sensitive.").pack(anchor="w", padx=10, pady=8)
    rows = []
    methods_box = tk.Frame(frame)
    methods_box.pack(fill="x", padx=10)

    def add(kind):
        if len(rows) >= security.MAX_METHODS:
            messagebox.showinfo("Unlock methods", "Up to 12 independent methods are supported.", parent=app)
            return
        box = ttk.LabelFrame(methods_box, text={"passphrase":"Passphrase", "yubikey":"YubiKey", "questions":"Family questions"}[kind])
        box.pack(fill="x", pady=8)
        row = {"kind":kind,"box":box,"secrets":[]}
        def field(label, secret=False):
            tk.Label(box,text=label,anchor="w",wraplength=580).pack(anchor="w",padx=8,pady=(5,0))
            entry=ttk.Entry(box,show="*" if secret else "")
            entry.pack(fill="x",padx=8)
            if secret: row["secrets"].append(entry)
            return entry
        row["label"] = field("Recognizable label (visible before unlock; e.g. Lawyer key)")
        row["label"].insert(0,{"passphrase":"Guide passphrase", "yubikey":"Guide YubiKey", "questions":"Family recovery"}[kind])
        if kind == "passphrase":
            row["passphrase"] = field("Guide passphrase (12+ characters; not a Bitcoin wallet passphrase)",True)
            row["confirm"] = field("Confirm passphrase",True)
        elif kind == "yubikey":
            tk.Label(box,text="Preconfigured USB HMAC-SHA1 key with touch enabled. See docs/YUBIKEY.md.\n"
                     "The app never overwrites device settings.",wraplength=580,justify="left").pack(anchor="w",padx=8,pady=6)
            row["slot"] = tk.StringVar(value="2")
            ttk.Combobox(box,textvariable=row["slot"],values=["1","2"],state="readonly").pack(anchor="w",padx=8)
        else:
            tk.Label(box,text="Enter 3–5 custom questions. All answers in this set are required.\n"
                     "Avoid public facts: answers are another password and can be guessed offline.\n"
                     "Answers ignore case and extra whitespace; punctuation still matters.",wraplength=580,justify="left").pack(anchor="w",padx=8,pady=6)
            row["questions"] = []
            for i in range(5):
                question=field(f"Question {i+1}" + (" (optional)" if i>=3 else ""))
                answer=field("Answer",True)
                confirm=field("Confirm answer",True)
                row["questions"].append((question,answer,confirm))
        def remove():
            rows.remove(row)
            for entry in row["secrets"]:entry.delete(0,"end")
            box.destroy()
        ttk.Button(box,text="Remove this unlock method",command=remove).pack(anchor="w",padx=8,pady=8)
        rows.append(row)

    buttons=tk.Frame(frame);buttons.pack(fill="x",padx=10,pady=8)
    for kind,label in [("passphrase","+ Passphrase"),("yubikey","+ YubiKey"),("questions","+ Family questions")]:
        ttk.Button(buttons,text=label,command=lambda k=kind:add(k)).pack(side="left",padx=3)
    add("passphrase")

    def export():
        configs=[]
        try:
            for row in rows:
                config={"kind":row["kind"],"label":row["label"].get().strip()}
                if not 1 <= len(config["label"]) <= 80:
                    raise ValueError("Give each method a label of 1–80 characters.")
                if row["kind"]=="passphrase":
                    password=row["passphrase"].get()
                    if len(password)<12 or password!=row["confirm"].get():
                        raise ValueError("Passphrases must match and contain at least 12 characters.")
                    config["passphrase"]=password
                elif row["kind"]=="yubikey":
                    config["slot"]=int(row["slot"].get())
                else:
                    questions,answers,confirmed=[],[],[]
                    for q,a,c in row["questions"]:
                        if q.get().strip() or a.get() or c.get():
                            if not q.get().strip():raise ValueError("Every answer needs a question.")
                            questions.append(q.get().strip());answers.append(a.get());confirmed.append(c.get())
                    if security.question_material(answers)!=security.question_material(confirmed):
                        raise ValueError("The confirmed family answers do not match.")
                    if len(set(questions))!=len(questions) or any(len(q)>500 for q in questions):
                        raise ValueError("Use distinct questions of no more than 500 characters.")
                    config.update(questions=questions,answers=answers)
                configs.append(config)
            if not configs:raise ValueError("Add at least one unlock method.")
        except ValueError as exc:
            messagebox.showerror("Check unlock methods",str(exc),parent=app)
            return
        if any(c["kind"]=="questions" for c in configs):
            if not messagebox.askokcancel("Family-question recovery", "Anyone who guesses these answers can open the guide without a key or passphrase. "
                "The questions are stored visibly so family can answer them. The encrypted file cannot enforce a retry limit. Continue?", parent=app):
                return
        if not messagebox.askokcancel("Save these unlock methods", "Any ONE of these will open the new file:\n\n"+
            "\n".join(c["label"]+" ("+c["kind"]+")" for c in configs)+
            "\n\nThese replace the methods on this new copy. Other methods from an older file are not carried over automatically.",parent=app):
            return
        path=filedialog.asksaveasfilename(parent=app,defaultextension=".csp.json",initialfile="family-guide.csp.json")
        if not path:return
        snapshot=json.loads(json.dumps(plan))
        def operation(provider):
            responses=[]
            def remember(challenge,slot):
                response=provider(challenge,slot);responses.append(response);return response
            env=security.seal(snapshot,configs,response_provider=remember)
            try:
                replay=iter(responses)
                for i,c in enumerate(configs):
                    credential=c.get("passphrase") if c["kind"]=="passphrase" else c.get("answers")
                    back=security.open_package(env,method_index=i,credential=credential,response_provider=lambda ch,sl:next(replay))
                    if back!=snapshot:raise ValueError("Unlock verification failed.")
            finally:
                responses.clear()
            return env
        def saved(env):
            try:
                save_encrypted(path,env)
            except (OSError,ValueError):
                messagebox.showerror("Save failed","Could not save the encrypted guide. The previous destination remains intact if replacement did not complete.",parent=app)
                return
            for row in rows:
                for entry in row["secrets"]:entry.delete(0,"end")
            app.dirty=False;app.opened_format=security.MAGIC
            messagebox.showinfo("Encrypted guide saved","Reopen this saved file and rehearse each intended unlock method with family. "
                "Keep the previous verified backup until that works. Store a non-secret discovery note outside the guide.",parent=app)
        hardware_job(app,operation,saved,environment_safe,[c["label"] for c in configs if c["kind"]=="yubikey"])
    ttk.Button(frame,text="SAVE ENCRYPTED GUIDE",command=export).pack(anchor="w",padx=10,pady=14)


def choose_method(app,env):
    dialog=tk.Toplevel(app);dialog.title("How would you like to unlock this guide?");dialog.transient(app);dialog.grab_set()
    tk.Label(dialog,text="Choose any ONE method. You do not need the others.",padx=20,pady=12).pack()
    labels=[f"{i+1}. {item['meta']['label']} ({item['meta']['kind']})" for i,item in enumerate(env['methods'])]
    selected=tk.StringVar(value=labels[0])
    ttk.Combobox(dialog,textvariable=selected,values=labels,state="readonly",width=65).pack(padx=20,pady=10)
    result=[None]
    def accept():result[0]=labels.index(selected.get());dialog.destroy()
    ttk.Button(dialog,text="Continue",command=accept).pack(pady=10)
    ttk.Button(dialog,text="Cancel",command=dialog.destroy).pack(pady=6)
    app.wait_window(dialog)
    return result[0]


def open_hardware(app,env,on_success,environment_safe):
    try:security.validate(env)
    except ValueError as exc:
        messagebox.showerror("Invalid guide",str(exc),parent=app);return
    index=choose_method(app,env)
    if index is None:return
    meta=env["methods"][index]["meta"]
    credential=None
    if meta["kind"]=="passphrase":
        credential=simpledialog.askstring("Guide passphrase","Enter the passphrase for "+meta["label"]+":",show="*",parent=app)
        if credential is None:return
    elif meta["kind"]=="questions":
        credential=[]
        for i,question in enumerate(meta["questions"],1):
            answer=simpledialog.askstring(f"Family question {i} of {len(meta['questions'])}",question,show="*",parent=app)
            if answer is None:return
            credential.append(answer)
    operation=lambda provider:security.open_package(env,method_index=index,credential=credential,response_provider=provider)
    hardware_job(app,operation,on_success,environment_safe,[meta["label"]])
