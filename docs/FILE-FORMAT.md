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
is only a categorical seed-passphrase backup status (for example, where it is
stored); it must never contain the passphrase itself. The document must never
contain seed words, private keys (xprv), or full xpub strings.
The format cannot stop a user from typing secrets into a text field — the rule
is social, printed on the first screen of the app and on every export:

> **Never type seed words, private keys, or full xpubs into this tool.**

## Compatibility

Files written by `vault-folio.py` and by `fallback-viewer/index.html` are
byte-compatible in both directions. The HTML viewer uses WebCrypto
(PBKDF2-SHA-256, 600,000 iterations; AES-GCM) with the identical envelope.
