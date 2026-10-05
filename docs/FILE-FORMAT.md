# The `.csp.json` file format — VAULTFOLIO/1

The sealed plan file is plain JSON. It is deliberately boring: any machine with
Python and the `cryptography` package can decrypt it, decades from now, without
this repository. That is the point — an inheritance file must outlive the app
that wrote it.

## Envelope

```json
{
  "magic": "VAULTFOLIO/1",
  "kdf": {
    "name": "PBKDF2",
    "hash": "SHA-256",
    "iterations": 600000,
    "salt": "<base64, 16 bytes>"
  },
  "cipher": {
    "name": "AES-256-GCM",
    "iv": "<base64, 12 bytes>"
  },
  "data": "<base64: AES-256-GCM ciphertext + 16-byte tag>"
}
```

- **Key derivation:** PBKDF2-HMAC-SHA-256, 600,000 iterations, 16-byte random
  salt, 32-byte output key. Input: the passphrase as UTF-8.
- **Cipher:** AES-256-GCM, 12-byte random IV, no associated data.
  Ciphertext includes the 16-byte GCM tag (appended, as produced by the
  `cryptography` package's `AESGCM.encrypt`).
- **Plaintext:** UTF-8 JSON — the plan document (structure below).

## Minimal decryptor

```python
import base64, json, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

env = json.load(open(sys.argv[1]))
assert env["magic"] == "VAULTFOLIO/1"
passphrase = input("Passphrase: ")          # or getpass.getpass()
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                 salt=base64.b64decode(env["kdf"]["salt"]),
                 iterations=int(env["kdf"]["iterations"]))
key = kdf.derive(passphrase.encode("utf-8"))
pt = AESGCM(key).decrypt(base64.b64decode(env["cipher"]["iv"]),
                         base64.b64decode(env["data"]), None)
plan = json.loads(pt.decode("utf-8"))
print(json.dumps(plan, indent=2, ensure_ascii=False))
```

## Plan document structure

```jsonc
{
  "meta":   { "app": "Vault Folio", "version": 1, "created": "YYYY-MM-DD",
              "planName": "", "owner": "", "jurisdiction": "", "legalNotes": "" },
  "people": { "executor": "", "trustee": "", "helper": "",
              "heirs": [ { "name": "", "relation": "", "role": "", "contact": "" } ] },
  "vaults": [ {
      "name": "", "tier": "", "m": 2, "n": 3,
      "script": "", "coordinator": "",
      "timelock": { "enabled": true, "delay": "" },
      "notes": "",
      "keys": [ { "label": "", "device": "", "generation": "",
                  "media": "", "locations": "", "passphrase": "" } ]
  } ],
  "signing":  { "medium": "", "verifyRitual": ["qr", "..."],
                "testSpend": "", "coordinatorNotes": "" },
  "backups":  { "descriptorLocations": [ { "where": "", "format": "" } ],
                "watchOnly": "", "rescanHeight": "",
                "sampleAddresses": "", "testedSoftware": "" },
  "inheritance": { "mechanism": "", "releaseConditions": "", "legalDocs": "",
                   "letterLocation": "", "heartbeat": "", "canary": "" },
  "rehearsal": { "restoreDrill": "", "familyWalkthrough": "",
                 "testSpendDate": "", "notes": "" },
  "ownerNotes": ""
}
```

## Content rules (enforced by the app's design, not by the format)

The plan document describes *locations and structure*. Its `passphrase` field
is only a categorical seed-passphrase backup status; it must never contain the
passphrase itself. The document must not contain seed words, seed passphrases,
private keys (xprv), full xpub strings, wallet descriptors, or complete signing
plans. The app's questionnaire requests only structural descriptions and
storage locations, and repeats this rule throughout the wizard. Free-text fields
cannot detect every secret a user might type, so follow the rule carefully:

> **Never type seed words, seed passphrases, keys, xpubs, wallet descriptors, or full signing plans into this tool.**

## Compatibility

The desktop app and browser companion prototype use this documented JSON
envelope. Future applications can implement PBKDF2-HMAC-SHA-256 and AES-256-GCM
to open the same files; file-format compatibility does not make the browser
prototype suitable for real plans or give it the desktop app's hardware gate.


## Optional guide sections

New guides may contain `lawyers`, `backupRecords`, `recoveryPaths` and
`accessRecords` and `instructions`, each an array of user-authored records. Missing arrays are empty.
The full field catalog is `folio_catalog.py`; values are descriptions, labels,
clues and optional guide/journal/watch-only access credentials. They must not
contain Bitcoin seeds or private keys. `accessRecords.mode` defaults to hint-only;
`directAccess` is present only when deliberately entered in direct-access mode.
All these fields are inside the encrypted payload and appear in the heir guide.

## Current desktop envelope — VAULTFOLIO/2

New desktop exports use v2. Legacy v1 files remain readable. The browser
prototype supports only v1. V2 does not provide identity, legal authorization,
remote revocation, a calendar lock, or a required combination of factors.

Top-level fields are exactly `magic`, `cipher`, `iv`, `methods`, `data`.
`magic` is `VAULTFOLIO/2`; `cipher` is `AES-256-GCM`; `iv` is a fresh
12-byte random nonce. `methods` contains 1–12 independent alternative wrappers.
Each is `{ "meta": {...}, "wrapped": "<base64 48 bytes>" }`.

Each metadata object contains:
- `kind`: `passphrase`, `yubikey`, or `questions`.
- `label`: public nonempty string, up to 80 characters.
- `salt`: fresh 16 random bytes, Base64.
- `iv`: fresh 12 random bytes, Base64.
- `iterations`: exactly 600000 for passphrase/questions, exactly 0 for YubiKey.

YubiKey metadata additionally contains `slot` (integer 1 or 2) and `challenge`
(32 random bytes, Base64). All keys enrolled during one export use the same
challenge so duplicate HMAC secrets can be rejected. Each export changes it.
Question metadata additionally contains `questions`, an ordered list of 3–5
unique nonempty prompts, each up to 500 characters. Prompts and method labels
are PUBLIC; answers and passphrases are never included.

### Derivation and authenticated encryption

1. Generate a fresh 32-byte data encryption key (DEK) for each export.
2. For passphrases, PBKDF2-HMAC-SHA256 (600000 iterations, metadata salt,
   32-byte output) consumes exact UTF-8 input. Enrollment requires 12+ characters.
3. For questions, normalize each answer using Unicode NFKC, casefold, and
   whitespace collapse (`" ".join(answer.split())`). Punctuation remains significant.
   Canonically serialize the ordered answer array, then apply the same PBKDF2.
   All 3–5 answers are required. Each must be nonempty and at most 4096 characters.
4. For YubiKey, input material is the 20-byte HMAC-SHA1 challenge response from
   an already-configured OTP slot; no passphrase is required.
5. Derive each wrapper key using HKDF-SHA256, length 32, metadata salt, and info
   ASCII `VAULTFOLIO/2/key-wrap/` followed by the method `kind`.
6. AES-256-GCM wraps DEK using that key and metadata IV. AAD is ASCII
   `VAULTFOLIO/2/key-wrap` immediately followed by canonical JSON of `meta`.
7. AES-256-GCM encrypts UTF-8 guide JSON using DEK and the top-level IV.
   AAD is canonical JSON of the entire envelope EXCEPT `data`, including every
   wrapper. Thus changing even an unselected method invalidates the payload.

Canonical JSON is Python `json.dumps(value, sort_keys=True, separators=(',', ':'),
ensure_ascii=True).encode('ascii')`. Standard strict padded Base64 is used.
All algorithms, fields, types, lengths and iteration counts are validated before
expensive derivation or hardware access. AES-GCM tags are appended, 16 bytes.
Plaintext is limited to 10 MiB; GUI files including encoding overhead are capped
at 10 MiB. See `folio_security.py` as the reference v2 reader/writer and
`tests/test_security.py` for examples.

Any ONE wrapper releases the same DEK. This is OR access, not multifactor.
The weakest enrolled alternative governs resistance to guessing. Question sets
can be guessed offline without a retry limit; familiar biographical answers
are often weak. AES-256 does not imply 256 bits of security for every route.
An HMAC response captured by a compromised host can reopen that file.

Export verifies all configured routes before saving. `folio_storage.py` writes
only ciphertext to a mode-0600 sibling temporary file, flushes/fsyncs it, then
atomically replaces the chosen destination. Directory fsync is best effort.
Failures before replacement preserve the previous file. Power loss/media faults
still require multiple verified backups. Changing enrollment does not revoke old
files; owners must enroll every desired method on each new copy.
