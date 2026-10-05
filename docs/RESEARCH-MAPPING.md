# Research used for the guide workflow

Read on 2026-10-04. These repo documents are background brainstorming, not
verified device compatibility matrices or instructions to execute automatically.
The user's current requirement takes precedence: CSIP stores an encrypted guide,
not Bitcoin signing keys, and supports optional direct journal/document/watch-only
access details in addition to hints.

## Repository sources

| Source | Git blob reviewed | Applied to CSIP |
| --- | --- | --- |
| [`bitcoin-cold-storage-brainstorm.pdf`](../bitcoin-cold-storage-brainstorm.pdf), 7 pages | `d2110f9b58fb078b26bbdd70f067258bf19f703b` | Separate backups/signers/inheritance; configuration-copy locations; rehearsals; fallback contacts |
| [`cold-storage-is-not-a-device.pdf`](../cold-storage-is-not-a-device.pdf), 10 pages | `b54d6a90ef1da726124bfe38e6c21889a757fe28` | Replaceable devices and providers; family-first instructions; independent recovery paths; offline/session discipline |
| [`Bitcoin_Custody_and_Inheritance_Brainstorm.txt`](../Bitcoin_Custody_and_Inheritance_Brainstorm.txt) | `ebf7db6787ea7f718a13d1f08b175ee54e48040c` | Differentiate seed shares from multisig; test missing-owner/device/provider scenarios; retain exact wallet configuration separately |
| [`docs/research/bitcoin-cold-storage-brainstorm.txt`](research/bitcoin-cold-storage-brainstorm.txt) | `8fb08807878d813565aa732ac92e51593c263e58` | Additional questionnaire themes and durable recovery-document context |

The first PDF also exists under `docs/research/` with the same blob: it is the
same document, not another independent source.

## Primary sources checked for implementation decisions

- Yubico challenge-response and CLI: USB operation, HMAC response, touch setup,
  and provisioning boundary. See [YUBIKEY.md](YUBIKEY.md).
- Linux tmpfs/dumpability documentation: swap and memory limitations. See
  [RAM-SESSION.md](RAM-SESSION.md).
- [Bitcoin Core offline signing tutorial](https://github.com/bitcoin/bitcoin/blob/master/doc/offline-signing-tutorial.md):
  separates watch-only coordination and actual offline signing. CSIP only explains
  the user's recorded workflow; it runs none of those commands.
- [Yeti 2.0 README](https://github.com/bowlarbear/yeti-2.0): confirms its 3-of-7
  example and backup/rehearsal emphasis. Preset values remain editable.
- [EntropyLab README](https://github.com/OogaBoogaX/entropylab): journal features,
  encryption and exports are version-specific. CSIP asks which reader/version
  and backup location the owner tested; it does not parse or import journals.
- Liana, Nunchuk, Unchained, Casa, Sparrow, Specter, Trezor and COLDCARD official
  documentation for catalog categories. Links are in [QUESTIONNAIRE.md](QUESTIONNAIRE.md).

## Ideas deliberately not converted into promises

- No assumption that every hardware/coordinator combination interoperates.
- No claim a brand name proves independent security or a particular anti-exfil protocol.
- No hard-coded legal entitlement, provider release delay, balance, fee or recovery deadline.
- No assumption that a descriptor is always public-only; record where the correct
  configuration lives rather than import descriptor strings into CSIP.
- No claim a timer detects death, moves money, or resets merely by opening an app.
- No automatic execution of the PDFs' proposed setups or experimental signature schemes.
- No promise of permanent RAM erasure or of protection from a compromised OS.

Some source notes favor unencrypted runbooks. CSIP follows the explicit product
requirement to encrypt the guide, while prompting for a minimal non-secret
external discovery note to avoid locking all unlock instructions inside it.
