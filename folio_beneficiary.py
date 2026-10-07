"""Read-only, plain-language heir journey. Never executes a recovery or edits a plan."""
import copy
import tkinter as tk
from tkinter import ttk
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



# --------------------------------------------------------------------------
# The big picture: a word-light, clickable recovery chain derived from the plan
# --------------------------------------------------------------------------
def big_picture(plan):
    """Derive the visual recovery chain from recorded facts; gaps stay explicit.

    Returns a list of stages. Each stage is {'joiner': '+'|'→'|None,
    'boxes': [box]}, where box = {'icon', 'title', 'detail', 'about'}.
    Boxes in a stage sit side by side joined by the joiner; stages stack
    top to bottom in recovery order. Pure data — no widgets here.
    """
    p = visible_plan(plan)
    stages = [{'joiner': None, 'boxes': [{
        'icon': 'guide',
        'title': 'Sealed guide',
        'detail': 'Opened — that was step one',
        'about': 'Everything the family needs is mapped in this file. It holds no keys and '
                 'cannot move bitcoin; it explains what exists, where the pieces live, and '
                 'who can help. Keep the file and its unlock details safe and separate.'}]}]
    vaults = p.get('vaults', [])
    if not vaults:
        stages.append({'joiner': '+', 'boxes': [{
            'icon': 'vault',
            'title': 'No wallet recorded',
            'detail': 'Ask the executor for details',
            'about': 'The owner has not described a wallet arrangement in this guide yet. '
                     'Without it the rest of the picture cannot be drawn.'}]})
    for v in vaults:
        name = v.get('name') or 'Unnamed arrangement'
        m, n = v.get('m'), v.get('n')
        rule = f'needs {m} of {n} keys to spend' if m and n else 'signing rule not recorded'
        boxes = [{
            'icon': 'vault',
            'title': name,
            'detail': rule,
            'about': ('One arrangement may hold several keys, but spending needs the recorded '
                      'quorum of DIFFERENT keys. Two copies of one key still count as one key.'
                      if m and n else
                      'The signing rule for this arrangement was not recorded. Ask the named '
                      'technical helper before touching anything.')}]
        for i, key in enumerate(v.get('keys', []), 1):
            bits = [b for b in (key.get('medium'), key.get('locations')) if b]
            boxes.append({
                'icon': 'key',
                'title': key.get('label') or key.get('device') or f'Key {i}',
                'detail': ' · '.join(bits) or 'backup and location not recorded',
                'about': 'One signing key. Its backup medium and where it lives are recorded '
                         'in this guide; gather it only as the written steps describe, and '
                         'never type seed words into this app or any website.'})
        if (v.get('timelock') or {}).get('enabled'):
            boxes.append({
                'icon': 'clock',
                'title': 'Delayed path',
                'detail': 'a timer-based route also exists',
                'about': 'Besides the main rule, this arrangement has a delayed spending path. '
                         'A timer does not detect death or move coins by itself; the written '
                         'recovery-route step explains what it means here.'})
        stages.append({'joiner': '+', 'boxes': boxes})
    coordinator = vaults[0].get('coordinator') if len(vaults) == 1 else None
    software_details = '\n'.join(
        f"{v.get('name') or 'Unnamed arrangement'}: {v.get('coordinator') or 'not recorded'}"
        for v in vaults) or 'coordinator not recorded'
    copies = len(p.get('backups', {}).get('descriptorLocations', []))
    stages.append({'joiner': '+', 'boxes': [
        {'icon': 'laptop',
         'title': coordinator or 'Wallet software',
         'detail': software_details,
         'about': 'Use the software recorded for each wallet and its own recovery route. The wallet program builds transactions and holds the watch-only view. '
                  'It is replaceable: any compatible wallet software can stand in, so a dead '
                  'vendor does not strand the coins.'},
        {'icon': 'map',
         'title': 'The wallet map',
         'detail': (f'{copies} recorded copy location(s)' if copies else 'copy locations not recorded'),
         'about': 'The wallet map (output descriptor) tells wallet software what exists '
                  'without holding any keys. It is not a secret that can spend, but it is '
                  'needed to rebuild the watch-only view.'}]})
    stages.append({'joiner': None, 'boxes': [{
        'icon': 'assemble',
        'title': 'Rebuild the wallet',
        'detail': 'load the map into the software first',
        'about': 'Load the wallet map into the coordinator software on a safe computer. This '
                 'recreates the watch-only wallet: the family can SEE balances and addresses '
                 'before anything can move.'}]})
    first = vaults[0] if len(vaults) == 1 else {}
    fm, fn = first.get('m'), first.get('n')
    sign_detail = (f'any {fm} of the {fn} keys approve' if fm and fn
                   else ('Each wallet: follow its recorded signing rule' if len(vaults) > 1
                         else 'signing rule not recorded'))
    stages.append({'joiner': '→', 'boxes': [
        {'icon': 'sign',
         'title': 'Sign',
         'detail': sign_detail,
         'about': 'Each required key approves the transaction on its own device. Check the '
                  'destination and amount on every device screen. Start with a small test '
                  'send, exactly as the rehearsal step describes.'},
        {'icon': 'broadcast',
         'title': 'Broadcast',
         'detail': 'the software sends it to the network',
         'about': 'The signed transaction is sent to the Bitcoin network by the wallet '
                  'software. Once confirmed it is public and cannot be undone — which is why '
                  'the test send comes first.'}]})
    return stages


def _draw_icon(cv, kind, cx, cy, color, tags=()):
    """Small line glyph at the top of a big-picture box. Canvas primitives only."""
    def rect(*a, **kw):
        return cv.create_rectangle(*a, outline=color, width=2, tags=tags, **kw)
    def line(*a, **kw):
        return cv.create_line(*a, fill=color, width=kw.pop('width', 2), tags=tags, **kw)
    def oval(*a, **kw):
        return cv.create_oval(*a, outline=color, width=kw.pop('width', 2),
                              fill=kw.pop('fill', ''), tags=tags, **kw)
    if kind == 'guide':
        rect(cx - 8, cy - 10, cx + 8, cy + 10)
        line(cx - 4, cy - 4, cx + 4, cy - 4)
        line(cx - 4, cy + 1, cx + 4, cy + 1)
    elif kind == 'key':
        oval(cx - 9, cy - 6, cx + 1, cy + 4)
        line(cx + 1, cy - 1, cx + 10, cy - 1)
        line(cx + 6, cy - 1, cx + 6, cy + 4)
        line(cx + 10, cy - 1, cx + 10, cy + 4)
    elif kind == 'vault':
        oval(cx - 10, cy - 2, cx - 2, cy + 6)
        oval(cx + 2, cy - 2, cx + 10, cy + 6)
        oval(cx - 4, cy - 10, cx + 4, cy - 2)
    elif kind == 'clock':
        oval(cx - 9, cy - 9, cx + 9, cy + 9)
        line(cx, cy, cx, cy - 6)
        line(cx, cy, cx + 4, cy + 2)
    elif kind == 'laptop':
        rect(cx - 9, cy - 8, cx + 9, cy + 3)
        line(cx - 12, cy + 8, cx + 12, cy + 8)
    elif kind == 'map':
        rect(cx - 10, cy - 8, cx + 10, cy + 8)
        line(cx - 3, cy - 8, cx - 3, cy + 8, width=1)
        line(cx + 4, cy - 8, cx + 4, cy + 8, width=1)
    elif kind == 'assemble':
        oval(cx - 7, cy - 7, cx + 7, cy + 7)
        oval(cx - 2, cy - 2, cx + 2, cy + 2)
        line(cx - 10, cy - 10, cx - 7, cy - 7)
        line(cx + 10, cy + 10, cx + 7, cy + 7)
    elif kind == 'sign':
        line(cx - 8, cy + 8, cx + 6, cy - 6)
        cv.create_polygon(cx + 6, cy - 6, cx + 9, cy - 9, cx + 9, cy - 4,
                          outline=color, fill='', tags=tags)
        line(cx - 10, cy + 10, cx - 4, cy + 10)
    elif kind == 'broadcast':
        oval(cx - 2, cy + 4, cx + 2, cy + 8, fill=color)
        cv.create_arc(cx - 8, cy - 6, cx + 8, cy + 8, start=30, extent=120, style='arc',
                      outline=color, width=2, tags=tags)
        cv.create_arc(cx - 13, cy - 11, cx + 13, cy + 13, start=30, extent=120, style='arc',
                      outline=color, width=2, tags=tags)


def draw_big_picture(box, plan, explanation=None):
    """Draw a responsive chain; the caller keeps explanations outside the sheet."""
    stages = big_picture(plan)
    explanation = explanation if explanation is not None else box
    detail_title = tk.Label(explanation, text='Click any piece to learn what it is',
                            font=ui.F('Courier', 10, 'bold'), bg=ui.PAPER, fg=ui.INK, anchor='w')
    detail_title.pack(fill='x')
    detail_body = tk.Label(explanation, text='', font=ui.F_BODY, bg=ui.PAPER,
                           fg=ui.BODY_TEXT, anchor='w', justify='left', wraplength=600)
    detail_body.pack(fill='x', pady=(2, 10))
    explanation.bind('<Configure>', lambda e: detail_body.configure(wraplength=max(80, e.width - 8)))
    cv = tk.Canvas(box, bg=ui.PAPER, highlightthickness=0, width=1)
    cv.pack(fill='x', anchor='w')
    boxes = {}
    selected = [None]

    def select(tag):
        selected[0] = tag
        for name, (rect, _) in boxes.items():
            cv.itemconfigure(rect, outline=ui.INK if name == tag else ui.LINE,
                             width=2 if name == tag else 1)
        detail_title.configure(text=boxes[tag][1]['title'])
        detail_body.configure(text=boxes[tag][1]['about'])

    def redraw(_event=None):
        width = cv.winfo_width()
        if width < 32:
            return
        cv.delete('all')
        boxes.clear()
        gap, margin = 34, 8
        columns = max(1, min(4, (width - 2 * margin + gap) // (176 + gap)))
        box_w = min(240, (width - 2 * margin - gap * (columns - 1)) // columns)
        y = 8
        for si, stage in enumerate(stages):
            row = stage['boxes']
            for start in range(0, len(row), columns):
                chunk = row[start:start + columns]
                drawn = []
                row_height = 112
                for j, item in enumerate(chunk):
                    tag = f'bp_{si}_{start + j}'
                    x = margin + j * (box_w + gap)
                    cx = x + box_w / 2
                    rect = cv.create_rectangle(x, y, x + box_w, y + 112,
                                               fill=ui.WHITE, outline=ui.LINE, tags=(tag,))
                    _draw_icon(cv, item['icon'], cx, y + 22, ui.INK, tags=(tag,))
                    title = cv.create_text(cx, y + 40, text=item['title'], anchor='n',
                                           font=ui.F('Courier', 10, 'bold'), fill=ui.INK,
                                           width=max(1, box_w - 16), tags=(tag,))
                    title_bottom = cv.bbox(title)[3]
                    detail = cv.create_text(cx, title_bottom + 8, text=item['detail'], anchor='n',
                                            font=ui.F('Helvetica', 9), fill=ui.HINT,
                                            width=max(1, box_w - 16), tags=(tag,))
                    row_height = max(row_height, cv.bbox(detail)[3] - y + 12)
                    boxes[tag] = (rect, item)
                    cv.tag_bind(tag, '<Button-1>', lambda _e, t=tag: select(t))
                    drawn.append((rect, x))
                for j, (rect, x) in enumerate(drawn):
                    cv.coords(rect, x, y, x + box_w, y + row_height)
                    if stage['joiner'] and j < len(drawn) - 1:
                        cv.create_text(x + box_w + gap / 2, y + row_height / 2,
                                       text=stage['joiner'], font=ui.F('Courier', 14, 'bold'), fill=ui.HINT)
                y += row_height + 16
            if si < len(stages) - 1:
                cv.create_text(margin + box_w / 2, y + 8, text='↓',
                               font=ui.F('Courier', 14), fill=ui.HINT)
                y += 36
        cv.configure(height=y)
        if selected[0] in boxes:
            select(selected[0])

    cv.bind('<Configure>', redraw)
    return {'canvas': cv, 'select': select, 'boxes': boxes}


def show_beneficiary(app, plan, close, full_reference, draw_diagrams=None, save_plan=None,
                     edit_plan=None, close_label='CLOSE GUIDE & CLEAR SESSION'):
    """Distinct UI: step navigation, no editable questionnaire, no export actions.

    draw_diagrams (optional) is called as draw_diagrams(box, plan) on the
    'Start here' and 'Understand what exists' steps so heirs see the same
    quorum pictures the owner checked at export time.

    Layout contract: the bottom button bar is packed FIRST with side='bottom'
    so the expanding scroll area can never squeeze it out; the written step
    leads, the diagram follows, and notes/checklist live inside the scroll.
    """
    app.clear()
    app.active_plan = plan
    app.header(status='BENEFICIARY VIEW · READ ONLY')
    outer = tk.Frame(app, bg=ui.PAPER)
    outer.pack(fill='both', expand=True, padx=24, pady=16)

    bottom = tk.Frame(outer, bg=ui.PAPER)
    bottom.pack(fill='x', side='bottom', pady=(10, 0))

    tk.Label(outer, text='Your family’s recovery guide', font=ui.F('Georgia', 24), bg=ui.PAPER, fg=ui.INK).pack(anchor='w')
    tk.Label(outer, text='One step at a time. Nothing here changes the sealed file until you press SAVE NOTES.',
             bg=ui.PAPER).pack(anchor='w', pady=(4,16))
    body = tk.Frame(outer, bg=ui.PAPER); body.pack(fill='both', expand=True)
    nav = tk.Frame(body, bg=ui.PAPER2, width=360)
    nav.pack(side='left', fill='y', padx=(0,18))
    nav.pack_propagate(False)
    panel = tk.Frame(body, bg=ui.PAPER); panel.pack(side='left', fill='both', expand=True)
    step_lbl = tk.Label(panel, font=ui.F('Courier', 9), fg=ui.HINT, bg=ui.PAPER, anchor='w')
    step_lbl.pack(fill='x')
    title = tk.Label(panel, font=ui.F('Georgia', 20), bg=ui.PAPER, fg=ui.INK, anchor='w', wraplength=760)
    title.pack(fill='x', pady=(2,10))
    explanation = tk.Frame(panel, bg=ui.PAPER)
    sheet = ui.ScrollFrame(panel)
    sheet.pack(fill='both', expand=True)
    text = tk.Text(sheet.inner, wrap='word', font=ui.F('Helvetica', 14), height=14, padx=18, pady=16,
                   relief='flat', bg=ui.WHITE, fg=ui.INK)
    text.pack(fill='x')
    diagram_box = tk.Frame(sheet.inner, bg=ui.PAPER)
    diagram_box.pack(fill='x', pady=(10, 0))
    index = [0]
    reveal = tk.BooleanVar(value=False)
    def nav_model(steps):
        # 'big' sits after 'Start here' as an unnumbered visual page; step and
        # checklist numbering is unchanged so saved files keep their ticks.
        return ([('step', 0), ('big', None)] +
                [('step', i) for i in range(1, len(steps))] + [('full', None)])

    def nav_label(item, steps):
        kind, i = item
        if kind == 'big':
            return '▸ The big picture'
        if kind == 'full':
            return f'{len(steps) + 1}. Full reference'
        return f'{i + 1}. {steps[i][0]}'

    def render(number=None):
        if number is not None: index[0] = number
        steps = recovery_steps(plan, reveal.get())
        model = nav_model(steps)
        index[0] = max(0, min(index[0], len(model) - 1))
        kind, step_i = model[index[0]]
        big = kind == 'big'
        if kind == 'full':
            heading, content = 'Full reference (advanced)', full_reference(visible_plan(plan, reveal.get()))
        elif big:
            heading = 'The big picture'
            content = ('This is the whole recovery as a set of pieces, top to bottom. '
                       'No instructions here — just what the pieces are and how they fit. '
                       'Click any piece for a short explanation.')
        else:
            heading, content = steps[step_i]
        total = len(steps) + 1
        step_lbl.configure(text=('VISUAL OVERVIEW' if big else
                                 f'STEP {step_i + 1} OF {total}' if kind == 'step'
                                 else f'STEP {total} OF {total}'))
        title.configure(text=heading)
        text.configure(state='normal')
        text.delete('1.0', 'end')
        text.insert('1.0', content or 'Nothing was recorded for this step.')
        # The big picture's intro is three lines; keep the Text widget short
        # there so the chain itself is on screen without scrolling.
        text.configure(height=5 if big else 14)
        text.configure(state='disabled')
        for w in diagram_box.winfo_children():
            w.destroy()
        for child in explanation.winfo_children():
            child.destroy()
        explanation.pack_forget()
        if big:
            explanation.pack(fill='x', before=sheet)
            try:
                draw_big_picture(diagram_box, visible_plan(plan, reveal.get()), explanation)
            except Exception:
                tk.Label(diagram_box, text='The big picture could not be drawn. The written steps are still the guide.',
                         bg=ui.PAPER, fg=ui.FLAG, wraplength=640, justify='left').pack(anchor='w')
        elif draw_diagrams is not None and heading in ('Start here', 'Understand what exists'):
            try:
                draw_diagrams(diagram_box, visible_plan(plan, reveal.get()))
            except Exception:
                tk.Label(diagram_box, text='The setup picture could not be drawn. The written steps below are still the guide.',
                         bg=ui.PAPER, fg=ui.FLAG, wraplength=640, justify='left').pack(anchor='w')
        text.yview_moveto(0)
        sheet.scroll_to_top()
        previous.configure(state='normal' if index[0] else 'disabled')
        next_button.configure(state='normal' if index[0] < len(model) - 1 else 'disabled')
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
    for item in nav_model(recovery_steps(plan)):
        choices.insert('end', nav_label(item, recovery_steps(plan)))
    choices.bind('<<ListboxSelect>>', lambda _: render(choices.curselection()[0]) if choices.curselection() else None)
    tk.Label(sheet.inner, text='PROGRESS CHECKLIST — tick steps as you finish them. Ticks and notes are kept when you press SAVE NOTES.',
             font=ui.F('Courier', 9), bg=ui.PAPER, fg=ui.HINT, anchor='w', wraplength=700,
             justify='left').pack(fill='x', pady=(16, 2))
    checks = plan.setdefault('heirChecklist', {})
    check_row = tk.Frame(sheet.inner, bg=ui.PAPER)
    check_row.pack(fill='x')
    for number, (heading, _detail) in enumerate(recovery_steps(plan), start=1):
        var = tk.BooleanVar(value=bool(checks.get(str(number))))
        ui.check_row(check_row, str(number) + ' ' + heading, var, bg='paper',
                     command=lambda key=str(number), value=var: checks.__setitem__(key, value.get())).pack(anchor='w')
    tk.Label(sheet.inner, text='YOUR NOTES — private working notes for the family (what you tried, who you called). '
             'Written into the encrypted file only when you press SAVE NOTES.',
             font=ui.F('Courier', 9), bg=ui.PAPER, fg=ui.HINT, anchor='w', wraplength=700,
             justify='left').pack(fill='x', pady=(16, 2))
    notes = tk.Text(sheet.inner, height=4, wrap='word', font=ui.F('Helvetica', 12), bg=ui.WHITE, fg=ui.INK,
                    relief='solid', bd=1)
    notes.insert('1.0', str(plan.get('heirNotes') or ''))
    notes.pack(fill='x', pady=(0, 4))

    def rebuild_beneficiary():
        # Button-style changes rebuild the screen; keep typed-but-unsaved notes.
        try:
            plan['heirNotes'] = notes.get('1.0', 'end-1c')
        except tk.TclError:
            pass
        show_beneficiary(app, plan, close, full_reference, draw_diagrams,
                         save_plan, edit_plan, close_label)
    app.screen_rebuilder = rebuild_beneficiary
    if save_plan is not None:
        def save_notes():
            plan['heirNotes'] = notes.get('1.0', 'end-1c')
            save_plan(plan)
        ui.btn_primary(sheet.inner, 'SAVE NOTES INTO ENCRYPTED FILE',
                       save_notes).pack(anchor='w', pady=6)
    ui.check_row(sheet.inner, 'Show direct journal / watch-only access details on screen',
                 reveal, command=render, bg='paper').pack(anchor='w', pady=10)
    previous=ui.btn_secondary(bottom,'← PREVIOUS',lambda:render(index[0]-1));previous.pack_configure(side='left')
    next_button=ui.btn_primary(bottom,'NEXT STEP →',lambda:render(index[0]+1));next_button.pack_configure(side='left',padx=8)
    if edit_plan is not None:
        ui.btn_primary(bottom, 'EDITOR VIEW', edit_plan, side='left', padx=8)
    ui.btn_secondary(bottom, close_label, close, side='right')
    render()
