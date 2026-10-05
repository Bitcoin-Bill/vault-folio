# CSIP — Cold Storage Inheritance Package

For synthetic test mode and its limitations, see
[RAM-SESSION.md](docs/RAM-SESSION.md). It skips all environment checks and
allows saving and reopening marked, passphrase-only test files; use made-up
answers and a new test passphrase only. Normal mode refuses marked test files.

**Vault Folio** is an offline plan-authoring tool for Bitcoin cold storage and
inheritance. It walks you through documenting *how* your cold storage is built —
the quorum, the keys, the backups, the signing procedure, the inheritance path —
and seals that plan into a single encrypted file. Family, an executor, or counsel
open that file years later and see exactly how to rebuild and recover what you
built, with pictures and step-by-step instructions.

It creates no keys. It signs nothing. It never asks for seed words.
**It stores the map, not the treasure.**

Developer preview, online and not the app: [browser-edition/app.html](browser-edition/app.html). Purpose: [docs/APP-PURPOSE.md](docs/APP-PURPOSE.md). Do not enter a real plan there.

## What it never does

| It documents | It never contains |
|---|---|
| Quorum structure and script types | Seed words / private keys |
| Which signer guards each key; where backups live | Full xpub strings |
| Descriptor-copy locations, rescan height, tested software | Seed passphrases |
| Inheritance mechanism, trustee, heirs, release conditions | Exact locations unless deliberately chosen |
| Rehearsal log: restore drills, test spends | Anything a thief could spend with directly |

## The app

`vault-folio.py` — standard-library GUI (tkinter), with local companion modules. No browser engine,
no web storage, cookies, or application autosave. Plan writes contain only
ciphertext, including a transient sibling used for atomic replacement.

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

## Guide-only scope

This app authors an encrypted guide for heirs. It never creates wallets, signs
transactions, handles Bitcoin seeds/private keys, or requests spending-wallet secrets,
seed passphrases or recovery-share words. Owners may optionally include direct
access details for journals, watch-only wallets and documents; hints are the default. The **package passphrase**,
**family-question answers**, and **package YubiKey** only unlock this guide.
Contacts, family clues and custody structure still deserve privacy.

## Open a saved guide

After decrypting, choose **Beneficiary View** for a read-only, plain-language
step-by-step journey, or **Plan Editor** to reconfigure the existing guide and
save a new encrypted copy. Direct access details are masked until revealed.
Owners can add their own ordered recovery steps, with prerequisites, success
checks and fallback instructions. See [USER-FLOWS.md](docs/USER-FLOWS.md).

The two repo PDFs and TXT research informed the questions; source mappings and
limits are documented in [RESEARCH-MAPPING.md](docs/RESEARCH-MAPPING.md).

## New in this preview

- Independent alternative unlock methods: any enrolled passphrase alone,
  YubiKey alone, or complete 3–5-question set opens the guide. Up to 12 methods.
- Every answer within a question set is required. This is OR access, not MFA.
  Question prompts and method labels are public; weak answers can be guessed
  offline with no retry limit. Choose and rehearse alternatives deliberately.
- Repeatable lawyer/custodian records: access held, associated backup labels,
  release instructions, known contact channel, successor and review date.
- Repeatable backup inventory: formats, media, custodians, site aliases, family
  clues, fallback routes and rehearsal dates. Exact locations are not required.
- Editable, sourced starting presets for DIY multisig, Bitcoin Core/Yeti,
  Sparrow, Specter, Electrum, Nunchuk, Liana, Unchained and Casa. They are not an
  exhaustive compatibility matrix or automatic wallet configuration.
- Conditional questions for SLIP39, Seed XOR, encrypted backups and guide keys;
  separate records for legal, provider-enforced and on-chain recovery paths.

Hardware support is **experimental**: automated tests use simulated responses;
real YubiKey/OS testing and independent cryptographic review remain required.
Read [YubiKey setup and threat model](docs/YUBIKEY.md) and
[questionnaire catalog](docs/QUESTIONNAIRE.md). The browser companion mirrors
questionnaire additions but deliberately does not unlock hardware packages.

## RAM-only operation

Real guide creation/viewing now requires a nonpersistent live Linux session.
The app fails closed unless writable system/home/temp paths are RAM-backed,
swap is disabled, process dump protection is active, and offline checks pass.
Normal installed macOS/Windows sessions cannot pass this policy. This is a
change from the earlier cross-platform runtime policy, not a claim that Python
can securely erase all RAM. Read [RAM-SESSION.md](docs/RAM-SESSION.md).

There is a **Clear session** action. Only chosen encrypted files are persisted;
reopen them in the app for later viewing. Power off after use: no sleep or
hibernation. OS/firmware compromise and physical memory recovery remain outside
what these checks can prove.

## Quick start

```bash
pip install cryptography        # plus tkinter from your OS; optional ykman for keys
python3 vault-folio.py --self-test   # verify crypto + logic on your machine
python3 vault-folio.py               # run — must be offline to pass the gate
python3 vault-folio.py --test-only-synthetic-questionnaire  # UI + encrypted save/open; invented data only
python3 -B -m unittest discover -s tests -v  # hardware-free regression tests
node tests/browser_crypto.cjs        # optional browser/Python compatibility test
```

- Prepare the live Linux image with Python, tkinter, `cryptography`, and (for
  hardware unlock) the official `ykman` CLI before offline use.
- Other OSes may run source/crypto tests but cannot pass the new RAM-session gate.

For maximum hygiene, boot a live Linux USB (no persistence) on a machine with
wireless physically removed and run the app and its companion modules from there — this avoids intentional persistent plaintext writes; memory erasure is not guaranteed. See [docs/OPERATIONAL-SECURITY.md](docs/OPERATIONAL-SECURITY.md).

## What it produces

| File | Purpose |
|---|---|
| `*.csp.json` | The complete questionnaire and recovery guide, sealed with AES-256-GCM. This is the durable file to back up in 2+ places. |

The program opens the guide using any one enrolled method. It saves only the
encrypted plan; there is no plaintext export. Keep credentials separate from
the file. A lawyer can hold a key or passphrase, with the program and ciphertext
in a safety deposit box. Leave a non-secret discovery note outside the package.

Release dates/events are advisory instructions. There is no cryptographic
calendar lock: an enrolled credential can open the file immediately. True timed
release requires a separate design and is tracked as research, not promised here.

## Durability: reading the file in 20 years

The encryption envelope is fully specified in
[docs/FILE-FORMAT.md](docs/FILE-FORMAT.md) — any offline program can read the
documented encrypted JSON envelope. A minimal Python decryptor is documented
for future compatibility.

## Repository layout

```
vault-folio.py            the offline desktop app (live Linux required for RAM mode)
folio_security.py         version-2 alternative-method envelope
folio_hardware_ui.py      desktop enrollment / unlock flow
folio_catalog.py          editable questionnaire catalog and fields
folio_memory.py           conservative Linux RAM-session checks
folio_storage.py          atomic ciphertext-only save
folio_document.py         loaded-plan schema validation
folio_beneficiary.py      separate read-only step-by-step heir interface
tests/                    offline cryptography and compatibility checks
browser-edition/           companion prototype for future plugin integration
docs/FILE-FORMAT.md       the encrypted JSON envelope specification
docs/OPERATIONAL-SECURITY.md  how and where to run this safely
docs/research/            background research on cold-storage inheritance
```

## Review status

This is a review preview, not an audited release. Automated tests cover software
behavior with simulated hardware. Real YubiKey, GUI, and nonpersistent live Linux
acceptance are outstanding. Start with [REVIEWER-GUIDE.md](docs/REVIEWER-GUIDE.md)
for code ownership, request flow, threat boundaries and test commands.

## Disclaimer

This tool documents plans; it is not a wallet, not legal advice, and not a
custodian. An untested backup is a story — rehearse before it matters.

## License

MIT — see [LICENSE](LICENSE).
