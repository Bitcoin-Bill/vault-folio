"""Read-only, plain-language heir journey. Never executes a recovery or edits a plan."""
import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import folio_ui as ui
from folio_catalog import record_fields


def visible_plan(plan, reveal=False):
    result = copy.deepcopy(plan)
    if not reveal:
        for item in result.get('accessRecords', []):
            if item.get('directAccess'):
                item['directAccess'] = '[Hidden: choose Show direct access details to reveal]'
    return result


def describe_records(plan, section, empty):
    output = []
    for i, row in enumerate(plan.get(section, []), 1):
        output.append(f'Record {i}')
        for key, label, _ in record_fields(section, row):
            if row.get(key):
                output.append(f'{label}: {row[key]}')
        output.append('')
    return '\n'.join(output) or empty


def recovery_steps(plan, reveal=False):
    """Derive a guide from recorded facts; missing facts remain explicit gaps."""
    p = visible_plan(plan, reveal)
    meta, people, backups = p.get('meta', {}), p.get('people', {}), p.get('backups', {})
    contact_lines = []
    for key, label in [('executor','Executor'),('trustee','Trustee'),('helper','Technical helper')]:
        contact_lines.append(f'{label}: {people.get(key) or "Not recorded — ask the family’s known legal contact."}')
    contact_lines.append(describe_records(p, 'lawyers', 'No additional lawyers or custodians recorded.'))
    vault_lines = []
    for v in p.get('vaults', []):
        vault_lines.append(f"{v.get('name') or 'Unnamed arrangement'}")
        m, n = v.get('m'), v.get('n')
        if m and n:
            vault_lines.append(f'The recorded primary rule needs {m} of {n} independent signing keys. Multiple copies of the same key still count as one.')
        else:
            vault_lines.append('The signing requirement is incomplete. Ask the named technical helper before proceeding.')
        vault_lines.append(f"Wallet software/coordinator: {v.get('coordinator') or 'Not recorded'}")
        if (v.get('timelock') or {}).get('enabled'):
            vault_lines.append('This arrangement has a delayed path. The primary count above does not describe every path; see Step 6. This app does not check chain eligibility.')
        if v.get('notes'):
            vault_lines.append('Owner notes: ' + str(v['notes']))
        vault_lines.append('')
    location_lines = [describe_records(p, 'backupRecords', 'No detailed backup inventory recorded.')]
    for v in p.get('vaults', []):
        for key in v.get('keys', []):
            location_lines.append(f"{v.get('name') or 'Vault'} / {key.get('label') or 'Key'}: {key.get('locations') or 'No location hint recorded'}")
    config_lines = []
    for row in backups.get('descriptorLocations', []):
        config_lines.append(f"Configuration copy: {row.get('where') or 'Location missing'} ({row.get('format') or 'format not recorded'})")
    for key, label in [('watchOnly','Watch-only wallet'),('rescanHeight','Rescan starting point'),('testedSoftware','Previously tested software'),('sampleAddresses','Address verification record')]:
        if backups.get(key):
            config_lines.append(f'{label}: {backups[key]}')
    steps = [
        ('Start here', f"This is {meta.get('owner') or 'the owner'}’s private recovery guide.\n"
         f"Plan: {meta.get('planName') or 'Untitled'}\nLast prepared: {meta.get('created') or 'Not recorded'}\n"
         f"Jurisdiction: {meta.get('jurisdiction') or 'Not recorded'}\nLegal notes: {meta.get('legalNotes') or 'Not recorded'}\n\n"
         'You do not have to solve everything today. Read first, then contact people you already know. '
         'This application only explains the recorded plan. It cannot sign, send bitcoin, verify legal authority, or confirm the plan is complete.\n\n'
         'Never give Bitcoin seeds or private keys to unsolicited callers or type them into this guide. '
         'Use an independently verified contact route. If something does not match, stop and ask the named helper.'),
        ('Contact the right people', '\n'.join(contact_lines)),
        ('Understand what exists', '\n'.join(vault_lines) or 'No wallets/vaults are described. Ask the executor for the missing plan information.'),
        ('Find the backups', 'Follow the owner’s labels and clues. Do not gather every secret on this computer. '
         'Seed shares reconstruct one key; multisig requires distinct signing keys.\n\n' + '\n'.join(location_lines)),
        ('Find the wallet map and journal', 'A watch-only wallet can show transactions but cannot sign. The wallet configuration is the map of the recovery setup. '
         'Journal/document passwords are separate from Bitcoin signing secrets.\n\n' + '\n'.join(config_lines) + '\n\n' +
         describe_records(p, 'accessRecords', 'No journal or watch-only access instructions recorded. Ask the named helper.')),
        ('Check the recovery route', 'Legal release conditions and Bitcoin spending conditions are different. '
         'A timer does not detect death or automatically send coins. A relative timelock applies to particular outputs; logging into a wallet does not reset it. '
         'Have the helper check the actual policy, required people and eligibility.\n\n' +
         describe_records(p, 'recoveryPaths', 'No alternate paths recorded. Do not assume a delayed or provider-independent route exists.') +
         '\n\nOwner’s inheritance mechanism: ' + str(p.get('inheritance', {}).get('mechanism') or 'Not recorded') +
         '\nRelease instructions: ' + str(p.get('inheritance', {}).get('releaseConditions') or 'Not recorded')),
        ('Rehearse before moving funds', 'With the authorized people and a trusted technical helper, follow the owner’s tested wallet-specific procedure. '
         'Recover in the appropriate wallet/signing tools, never in this guide. Check the wallet map and known-address records. '
         'Use a small test before any larger transfer. Verify destination, amount, fee and change on trusted displays. '
         'The guide does not generate or approve a transaction.\n\n'
         f"Transfer medium noted by owner: {p.get('signing', {}).get('medium') or 'Not recorded'}\n"
         f"Procedure notes: {p.get('signing', {}).get('coordinatorNotes') or 'Not recorded'}\n"
         f"Last restore drill: {p.get('rehearsal', {}).get('restoreDrill') or 'Not recorded'}\n"
         f"Last family walkthrough: {p.get('rehearsal', {}).get('familyWalkthrough') or 'Not recorded'}\n"
         f"Last test spend: {p.get('rehearsal', {}).get('testSpendDate') or 'Not recorded'}\n"
         f"Rehearsal notes: {p.get('rehearsal', {}).get('notes') or 'Not recorded'}"),
        ('If something is missing', 'Stop rather than guess a password, missing key, policy or legal entitlement. '
         'Use the fallback contacts and alternate routes recorded in this guide. A provider or a particular device may be replaceable, '
         'but that requires the right surviving backups and configuration. Opening this guide does not prove the Bitcoin is recoverable.\n\n'
         f"Owner’s final instructions: {p.get('ownerNotes') or 'Not recorded'}\n\n"
         'When finished, clear this session and fully shut down the live system. The encrypted file remains available for your next session. '
         'Clearing the screen is not a guaranteed physical RAM wipe.'),
    ]
    # Insert owner-authored actions before the closing fallback step.
    custom = []
    for i, row in enumerate(p.get('instructions', []), 1):
        body = []
        for key, label, _ in record_fields('instructions', row):
            if key != 'title' and row.get(key):
                body.append(f'{label}: {row[key]}')
        custom.append((row.get('title') or f'Owner instruction {i}', '\n\n'.join(body) or 'No action recorded. Ask the executor.'))
    steps[-1:-1] = custom
    return steps



def show_beneficiary(app, plan, close, full_reference, draw_diagrams=None):
    """Distinct UI: step navigation, no editable questionnaire, no export actions.

    draw_diagrams (optional) is called as draw_diagrams(box, plan) on the
    'Understand what exists' step so heirs see the same quorum pictures the
    owner checked at export time.
    """
    app.clear()
    app.active_plan = plan
    app.header(status='BENEFICIARY VIEW · READ ONLY')
    outer = tk.Frame(app, bg=ui.PAPER)
    outer.pack(fill='both', expand=True, padx=24, pady=16)
    tk.Label(outer, text='Your family’s recovery guide', font=ui.F('Georgia', 24), bg=ui.PAPER, fg=ui.INK).pack(anchor='w')
    tk.Label(outer, text='One step at a time. Notes can be saved back into the encrypted file.', bg=ui.PAPER).pack(anchor='w', pady=(4,16))
    body = tk.Frame(outer, bg=ui.PAPER); body.pack(fill='both', expand=True)
    nav = tk.Frame(body, bg=ui.PAPER2, width=360)
    nav.pack(side='left', fill='y', padx=(0,18))
    nav.pack_propagate(False)
    panel = tk.Frame(body, bg=ui.PAPER); panel.pack(side='left', fill='both', expand=True)
    step_lbl = tk.Label(panel, font=ui.F('Courier', 9), fg=ui.HINT, bg=ui.PAPER, anchor='w')
    step_lbl.pack(fill='x')
    title = tk.Label(panel, font=ui.F('Georgia', 20), bg=ui.PAPER, fg=ui.INK, anchor='w', wraplength=760)
    title.pack(fill='x', pady=(2,10))
    text = tk.Text(panel, wrap='word', font=ui.F('Helvetica', 14), padx=18, pady=16,
                   relief='flat', bg=ui.WHITE, fg=ui.INK)
    text.pack(fill='both', expand=True)
    diagram_box = tk.Frame(panel, bg=ui.PAPER)
    diagram_box.pack(fill='x', before=text)
    index = [0]
    reveal = tk.BooleanVar(value=False)
    def render(number=None):
        if number is not None: index[0] = number
        steps = recovery_steps(plan, reveal.get())
        index[0] = max(0, min(index[0], len(steps)))  # len(steps) = Full reference
        total = len(steps) + 1
        if index[0] == len(steps):
            heading, content = 'Full reference (advanced)', full_reference(visible_plan(plan, reveal.get()))
        else:
            heading, content = steps[index[0]]
        step_lbl.configure(text=f'STEP {index[0] + 1} OF {total}')
        title.configure(text=heading)
        text.configure(state='normal')
        text.delete('1.0', 'end')
        text.insert('1.0', content or 'Nothing was recorded for this step.')
        text.configure(state='disabled')
        for w in diagram_box.winfo_children():
            w.destroy()
        if draw_diagrams is not None and heading in ('Start here', 'Understand what exists'):
            try:
                draw_diagrams(diagram_box, visible_plan(plan, reveal.get()))
            except Exception:
                tk.Label(diagram_box, text='The setup picture could not be drawn. The written steps below are still the guide.',
                         bg=ui.PAPER, fg=ui.FLAG, wraplength=640, justify='left').pack(anchor='w')
        text.yview_moveto(0)
        previous.configure(state='normal' if index[0] else 'disabled')
        next_button.configure(state='normal' if index[0] < len(steps) else 'disabled')
        choices.selection_clear(0, 'end')
        choices.selection_set(index[0])
        choices.see(index[0])
    count = len(recovery_steps(plan))
    choices = tk.Listbox(nav, width=36, exportselection=False, font=ui.F('Helvetica', 12),
                         relief='flat', highlightthickness=0, activestyle='none',
                         bg=ui.PAPER2, fg=ui.INK, selectbackground=ui.INK, selectforeground=ui.PAPER)
    choices.pack(side='left', fill='both', expand=True)
    nav_scroll = ttk.Scrollbar(nav, command=choices.yview)
    nav_scroll.pack(side='right', fill='y')
    choices.configure(yscrollcommand=nav_scroll.set)
    for i,(heading,_) in enumerate(recovery_steps(plan)):
        choices.insert('end', f'{i+1}. {heading}')
    choices.insert('end', f'{count+1}. Full reference')
    choices.bind('<<ListboxSelect>>', lambda _: render(choices.curselection()[0]) if choices.curselection() else None)
    notes = tk.Text(outer, height=4, wrap='word', font=ui.F('Helvetica', 12), bg=ui.WHITE, fg=ui.INK)
    notes.insert('1.0', str(plan.get('heirNotes') or ''))
    notes.pack(fill='x', pady=(8, 4))
    checks = plan.setdefault('heirChecklist', {})
    check_row = tk.Frame(outer, bg=ui.PAPER)
    check_row.pack(fill='x')
    for number, (heading, _detail) in enumerate(recovery_steps(plan), start=1):
        var = tk.BooleanVar(value=bool(checks.get(str(number))))
        tk.Checkbutton(check_row, text=str(number) + ' ' + heading, variable=var, bg=ui.PAPER, fg=ui.INK,
                       command=lambda key=str(number), value=var: checks.__setitem__(key, value.get())).pack(anchor='w')
    def save_notes():
        plan['heirNotes'] = notes.get('1.0', 'end-1c')
        path = getattr(app, 'guide_path', '')
        if not path:
            messagebox.showinfo('Vault Folio', 'Open the encrypted file again, then save the notes.')
            return
        password = simpledialog.askstring('Vault Folio', 'Enter the guide passphrase to save these notes:', show='*', parent=app)
        if not password:
            return
        try:
            from folio_security import seal
            from folio_storage import save_encrypted
            save_encrypted(path, seal(plan, [{'kind': 'passphrase', 'label': 'Guide passphrase', 'passphrase': password}]))
        except Exception as exc:
            messagebox.showerror('Vault Folio', str(exc))
            return
        finally:
            password = None
        messagebox.showinfo('Vault Folio', 'Notes and checklist were saved into the encrypted file.')
    tk.Button(outer, text='SAVE NOTES INTO ENCRYPTED FILE', command=save_notes).pack(anchor='w', pady=6)
    tk.Checkbutton(outer, text='Show direct journal / watch-only access details on screen', variable=reveal, command=render, bg=ui.PAPER).pack(anchor='w', pady=10)
    bottom=tk.Frame(outer,bg=ui.PAPER);bottom.pack(fill='x')
    previous=ui.btn_secondary(bottom,'← PREVIOUS',lambda:render(index[0]-1));previous.pack_configure(side='left')
    next_button=ui.btn_primary(bottom,'NEXT STEP →',lambda:render(index[0]+1));next_button.pack_configure(side='left',padx=8)
    ui.btn_secondary(bottom,'CLOSE GUIDE & CLEAR SESSION',close,side='right')
    render()
