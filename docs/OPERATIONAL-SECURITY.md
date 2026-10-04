# Operational security — how and where to run Vault Folio

The app is designed so that *where* and *how* you run it matters more than the
software itself. This document is the recommended setup, from acceptable to
best.

## The rule

Vault Folio authors the map to your cold storage. Run it only on a machine with
**no path to any network**: no Wi-Fi, no Bluetooth, no Ethernet, no tethering.
The native app checks the local routing table, wireless interfaces, and
Bluetooth adapters at startup and during the session. It makes no external
connectivity probes. These checks are best-effort and cannot prove physical
isolation; inspect the machine yourself. The browser fallback makes no network
requests, but browser APIs cannot verify physical isolation. Use it only on a
machine you have physically air-gapped.

## Setups, worst to best

**Acceptable** — your everyday machine, radios off:
disable Wi-Fi and Bluetooth in the OS, unplug Ethernet, then run the app. When
the OS won't let the app verify radio state, the gate will ask you to attest
that wireless is disabled in firmware or physically absent. Attest honestly.

**Better** — a dedicated machine:
an old laptop with wireless and Bluetooth disabled in BIOS/UEFI, used for
nothing else. Keep it powered off and stored with the rest of the plan
materials.

**Best** — a live USB on stripped hardware:
boot a live Linux USB **with persistence disabled** on a machine whose wireless
card is physically removed. Copy `vault-folio.py` onto the live session (or a
ramdisk) and run it from there. The OS writes nothing to disk; the app writes
nothing but the files you export; RAM is volatile — when you shut down, the
session is gone.

Verify the tool on any machine before trusting it:

```bash
python3 vault-folio.py --self-test
```

## What the app writes — and what it never writes

The app holds your plan in memory only. It never creates temp files, logs,
caches, or config directories, and it suppresses Python's bytecode cache. The
only disk writes are files you choose yourself in a Save dialog:

- the encrypted plan (`*.csp.json`) — safe to copy widely;
- the heir runbooks (`*.runbook.html`, `*.runbook.txt`) — contain no keys, but
  they describe your setup's structure: treat them as sensitive paper;
- the sealed letter (`*.sealed-letter.txt`) — print it, seal it, give it to
  the trustee.

Export to removable media you control (a USB stick that then lives with the
trustee, a printed runbook in the safe), not to cloud-synced folders.

## The passphrase road

The encrypted file and its passphrase must never travel together. If the
passphrase dies with you, the file is a brick. Recommended: sealed copy of the
passphrase with the trustee, plus the sealed letter telling heirs who holds it.
Memorized-only passphrases are a theft feature and an inheritance bug.

## After the session

Shut the machine down. Don't sleep it — power it off. If you used a live USB,
remove it and store it with the plan materials or wipe it.

## Browser fallback limitations

Browsers are designed to remember: history, caches, storage APIs, session
restore, crash recovery, sync. A page that handles the map to your cold storage
should not run inside an engine whose job is persistence. That is why Vault
Folio is a native single-file app. The `fallback-viewer/` HTML is only an
emergency decryptor for heirs, decades from now, if nothing else survives.
Use it on a physically air-gapped machine, ideally from a live USB, and close
the browser entirely afterwards.

## The human layer

No tool survives contact with an unrehearsed family. The app's risk review will
push you, and the research notes in `docs/research/` explain the reasoning:
distribute the quorum geographically, keep the descriptor copies current,
run a restore drill, do a small test spend, walk the family through it while
you are alive. An untested backup is a story.
