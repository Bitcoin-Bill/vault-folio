# Two interfaces, one encrypted guide

## Create or edit (Plan Editor)

The editor walks through identity, people, arrangements, lawyers, backup
inventory, access instructions, recovery paths, rehearsals and custom ordered
family steps. Major arrangements have editable preloaded examples. Repeated
records have add/remove controls; conditional questions appear when relevant.
Custom values remain possible. Records request useful hints rather than require
precise hiding places. Journal/document/watch-only access details are optional
and deliberately selected; Bitcoin seeds/private keys are never requested.

For custom steps, record who acts, prerequisites, the plain-language action,
how to check success, when to stop, fallback and the offline reference. Preserve
unknowns explicitly rather than infer a recovery route that was never tested.

Save makes an encrypted file. There is no autosave. Reopening an existing guide
and selecting Plan Editor retains its recorded fields; changes remain in memory
until exported again. The original file is not changed unless that destination
is explicitly chosen. Leaving with unsaved changes prompts first.

Each new desktop export explicitly enrolls its desired alternatives: passphrases,
YubiKeys, and optional 3–5-question sets. Any one method opens the file; every
answer in a selected question set is required. Old methods are not automatically
carried forward. The exact new method list is confirmed before saving.
Re-exporting never revokes old copies.

## Reload (choose a mode after decrypting)

1. Open the encrypted `.csp.json` file in the offline/RAM-checked desktop app.
2. Unlock using its package passphrase, enrolled YubiKey alone, or one complete question set.
3. Choose **Beneficiary View** or **Plan Editor**.

These are separate task interfaces, not separate identities or permissions.
Anyone who can decrypt can choose the editor. No legal authority is implied.

## Beneficiary View (read-only)

The family sees a navigable sequence rather than the questionnaire:

1. Start calmly and understand what the guide can and cannot do.
2. Contact known executor, trustee, lawyer and technical helper.
3. Understand which arrangements exist and the recorded signing requirement.
4. Follow backup labels and family clues.
5. Find the wallet configuration, watch-only wallet and journal.
6. Confirm legal release instructions and actual recovery-path eligibility.
7. Follow the recorded tested procedure with qualified help and a small rehearsal.
8. Follow any owner-authored steps in their recorded order.
9. Use fallback instructions when something is missing.

An advanced full-reference view retains the complete recorded information.
Direct access details are masked by default; an explicit reveal control displays
them. It is a screen-privacy convenience, not a second cryptographic permission.
No editing or encryption/export controls appear in this interface. Navigation
and revealing fields never modify the loaded plan or saved file.

Closing the guide drops app references. Fully shut down the live OS afterward;
this UI action is not a guaranteed RAM wipe. Open the encrypted file again for
a future session. The browser companion demonstrates these flows but cannot
satisfy RAM-only or hardware-isolation requirements and cannot open v2 files.

## Lawyer / safety deposit handoff

Record the ciphertext and offline program locations (hints are fine), which
method label the custodian holds, successor contact, and agreed release event
or date. These are advisory instructions, not a cryptographic time lock.
Anyone with a currently enrolled method can open the file immediately.
Keep discovery instructions accessible outside the guide; do not lock the only
explanation of how to find the app and credentials inside the file itself.
