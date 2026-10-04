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

- **Fail-closed air-gap gate** — refuses to open if the OS detects Wi-Fi or
  Bluetooth hardware, an active network interface, a default route, or cannot
  complete any environment check. It checks again during use and locks if the
  environment becomes unsafe. It makes no network requests.
- **Encryption-only export** — AES-256-GCM, key derived with PBKDF2-HMAC-SHA-256
  (600,000 rounds). There is no plaintext plan export.
- **In-app heir guide** — decrypts the saved plan in memory and displays a
  setup-specific recovery guide with diagrams. The guide is not written as a
  separate plaintext file.
- **Browser companion prototype** — `browser-edition/index.html` keeps a
  side-by-side version for possible EntropyLab / Ooga Booga plugin work. It
  cannot enforce the desktop app's hardware gate; do not enter real plan data.
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
| `*.csp.json` | The complete questionnaire and recovery guide, sealed with AES-256-GCM. This is the durable file to back up in 2+ places. |

The program opens and displays the heir guide after the recipient enters the
passphrase. It saves only the encrypted plan; it does not export plaintext
runbooks or letters. Keep the passphrase separate from the encrypted file.

## Durability: reading the file in 20 years

The encryption envelope is fully specified in
[docs/FILE-FORMAT.md](docs/FILE-FORMAT.md) — any offline program can read the
documented encrypted JSON envelope. A minimal Python decryptor is documented
for future compatibility.

## Repository layout

```
vault-folio.py            the offline desktop app (Linux / macOS / Windows)
browser-edition/           companion prototype for future plugin integration
docs/FILE-FORMAT.md       the encrypted JSON envelope specification
docs/OPERATIONAL-SECURITY.md  how and where to run this safely
docs/research/            background research on cold-storage inheritance
```

## Disclaimer

This tool documents plans; it is not a wallet, not legal advice, and not a
custodian. An untested backup is a story — rehearse before it matters.

## License

MIT — see [LICENSE](LICENSE).
