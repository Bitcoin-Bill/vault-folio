# Operational security — how and where to run Vault Folio

The app is designed so that *where* and *how* you run it matters more than the
software itself. This document is the recommended setup, from acceptable to
best.

## The rule

Vault Folio authors the map to your cold storage. Run it only on a machine with
**no path to any network**: no Wi-Fi, no Bluetooth, no Ethernet, no tethering.
The desktop app checks the local routing table, active network interfaces,
wireless interfaces, and Bluetooth adapters at startup and during the session.
It refuses to open if Wi-Fi or Bluetooth hardware is enumerated, a network
route or active interface exists, or any check is unavailable. It makes no
external connectivity probes and has no attestation override. These OS checks
are not a proof against compromised firmware or a hostile operating system.
The side-by-side browser companion in `browser-edition/` is only an integration
prototype. Browser APIs cannot enforce the hardware gate; do not use it for real
plans or sensitive details.

## Setups, worst to best

**Acceptable** — a computer with radios physically removed or absent:
disconnect Ethernet and all tethered/network adapters. The app will block if
the operating system still reports Wi-Fi or Bluetooth hardware, any active
network interface, or cannot determine the machine's state. Disabling a radio
in the OS may not be sufficient because the device can remain enumerated.

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

- the encrypted plan (`*.csp.json`) — safe to copy widely, though it reveals
  structure if the passphrase is also obtained.

The app displays the decrypted heir guide in memory. It does not save an
unencrypted runbook or letter.

Save the encrypted plan to removable media you control (such as a USB stick
held with the trustee), not to a cloud-synced folder.

## The passphrase road

The encrypted file and its passphrase must never travel together. If the
passphrase dies with you, the file is a brick. Recommended: sealed copy of the
passphrase with the trustee, plus separate instructions telling heirs who holds
it. Memorized-only passphrases are a theft feature and an inheritance bug.

## After the session

Shut the machine down. Don't sleep it — power it off. If you used a live USB,
remove it and store it with the plan materials or wipe it.

## Future recovery

The encrypted JSON format is documented independently of the app. A future
offline desktop program or a future plugin can implement the same KDF and
cipher. The browser companion exists to explore that integration, not to replace
the desktop app for real plan creation or recovery.

## The human layer

No tool survives contact with an unrehearsed family. The app's risk review will
push you, and the research notes in `docs/research/` explain the reasoning:
distribute the quorum geographically, keep the descriptor copies current,
run a restore drill, do a small test spend, walk the family through it while
you are alive. An untested backup is a story.
