# CSIP — Cold Storage Inheritance Package

**Vault Folio** is an offline plan-authoring tool for Bitcoin cold storage and
inheritance. It walks you through documenting *how* your cold storage is built —
the quorum, the keys, the backups, the signing procedure, the inheritance path —
and seals that plan into a single encrypted file. Family, an executor, or counsel
open that file years later and see exactly how to rebuild and recover what you
built, with pictures and step-by-step instructions.

It creates no keys. It signs nothing. It never asks for seed words.
**It stores the map, not the treasure.**

## What it never does

| It documents | It never contains |
|---|---|
| Quorum structure and script types | Seed words / private keys |
| Which signer guards each key; where backups live | Full xpub strings |
| Descriptor-copy locations, rescan height, tested software | Seed passphrases |
| Inheritance mechanism, trustee, heirs, release conditions | Street-precise hiding places |
| Rehearsal log: restore drills, test spends | Anything a thief could spend with directly |

## The app

`vault-folio.py` — one file, standard-library GUI (tkinter). No browser engine,
no web storage, no cookies, no caches, no background persistence. The only disk
writes are the files you explicitly choose in a Save dialog.

- **Air-gap gate** — the native app checks local OS network and radio state and
  refuses to run when a default route or active wireless interface is reported.
  These checks cannot prove physical isolation and do not contact external
  connectivity services. The browser fallback makes no network requests, but
  browsers cannot verify physical isolation; use it only on a physically
  air-gapped machine.
- **Encryption-only export** — AES-256-GCM, key derived with PBKDF2-HMAC-SHA-256
  (600,000 rounds). There is no plaintext plan export.
- **Illustrated runbook** — exports a self-contained HTML document (no scripts,
  no external resources, prints to A4) with drawn diagrams: the quorum map for
  each vault and the air-gap signing ceremony. Plus plain-text runbook and a
  sealed executor letter.
- **Risk review** — a failure simulator reads what you documented and flags the
  classic ways cold-storage plans and inheritances actually die (quorum in one
  location, memory-only passphrases, no descriptor backup, untested restores,
  signer monoculture, device-RNG-only key generation).

## Quick start

```bash
pip install cryptography        # the only dependency
python3 vault-folio.py --self-test   # verify crypto + logic on your machine
python3 vault-folio.py               # run — must be offline to pass the gate
```

- **Linux:** `sudo apt install python3-tk` if tkinter is missing.
- **macOS / Windows:** tkinter ships with python.org Python. On Windows run
  with `py vault-folio.py`.

For maximum hygiene, boot a live Linux USB (no persistence) on a machine with
wireless physically removed and run the file from there — RAM is volatile and
nothing survives power-off. See [docs/OPERATIONAL-SECURITY.md](docs/OPERATIONAL-SECURITY.md).

## What it produces

| File | Purpose |
|---|---|
| `*.csp.json` | The sealed plan — AES-256-GCM encrypted. Back up in 2+ places. |
| `*.runbook.html` | Illustrated heir runbook — self-contained, prints to A4. No keys. |
| `*.runbook.txt` | Plain-text runbook — the durable format. No keys. |
| `*.sealed-letter.txt` | Cover letter for the sealed envelope with the trustee. |

The encrypted file is safe to store widely; the passphrase must travel by a
different road (sealed with the trustee, split with a lawyer, memorized by two
people). Whoever holds file + passphrase can read the plan.

## Durability: reading the file in 20 years

The encryption envelope is fully specified in
[docs/FILE-FORMAT.md](docs/FILE-FORMAT.md) — any machine with Python +
`cryptography` can decrypt a `.csp.json` with ~20 lines of code, no Vault Folio
required. A format-compatible standalone HTML viewer is kept in
`fallback-viewer/` as an emergency decryptor (browsers retain data — use it on
an offline machine, preferably a live USB, and only if the native app is
unavailable).

## Repository layout

```
vault-folio.py            the app (Linux / macOS / Windows)
fallback-viewer/          emergency format-compatible HTML viewer
docs/FILE-FORMAT.md       the .csp.json envelope specification
docs/OPERATIONAL-SECURITY.md  how and where to run this safely
docs/research/            background research on cold-storage inheritance
```

## Disclaimer

This tool documents plans; it is not a wallet, not legal advice, and not a
custodian. An untested backup is a story — rehearse before it matters.

## License

MIT — see [LICENSE](LICENSE).
