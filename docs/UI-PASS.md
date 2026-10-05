# UI pass review

Uploaded tree checksum: `387707a6ffc66112aadb37a5e270c4e822fcc918d0e5aa3a9e971ee61fc09676`.

The note says presentation only, and the new `folio_ui.py` theme matches that. `folio_security.py`, `folio_storage.py`, and the envelope were not part of this commit. The zip was cut from `59eb2d`, before the phase-1 interview, so committing it unchanged would have removed `folio_phase1.py` and the "Start the guide" button. Those were kept. The shared cards, focus rings, record layout, risk chips, heir-step badge, and export-method cards are the UI change.

Not retested here: the claimed 21 unit tests, self-test, browser check, and Xvfb tour. No live Linux or YubiKey check. This is not a certification.
