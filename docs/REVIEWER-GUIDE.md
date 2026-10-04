# Reviewer guide

This branch is a security-sensitive review preview. Use synthetic data only
until independent crypto review and real-device/live-image acceptance complete.

## Components and authentication flow

There is no account system, server, HTTP authentication, bearer token, session
cookie, or remote password reset. File decryption is the access boundary.

- `vault-folio.py`: Tk application, offline environment gate, wizard, v1 import,
  post-unlock mode selection and recovery text.
- `folio_memory.py`: conservative Linux RAM-backed mount and swap checks, core
  dump hardening, best-effort session reference disposal.
- `folio_security.py`: strict v2 envelope validation, derivation, DEK wrapping,
  AES-GCM encryption/decryption, YubiKey CLI adapter.
- `folio_hardware_ui.py`: alternative-method enrollment and unlock dialogs,
  worker thread with UI queue, cancellation and pre/post environment checks.
- `folio_storage.py`: atomic ciphertext-only write.
- `folio_document.py`: normalize missing legacy fields, reject malformed known
  structures before rendering; preserve unknown future fields.
- `folio_catalog.py`: editable profiles and conditional questionnaire fields.
- `folio_beneficiary.py`: distinct read-only guided interface, optional direct
  credential reveal, full reference. Reveal is not an authorization boundary.

Open flow: environment check → read bounded file → validate envelope → select
one enrolled method → derive wrapper key / request hardware response → unwrap
DEK → authenticate and decrypt payload → validate guide structure → choose
Beneficiary View or Plan Editor. V1 imports use their original passphrase KDF.

Save flow: collect and confirm desired alternatives → snapshot plan in RAM →
generate fresh DEK and nonces → independently wrap DEK for each method → encrypt
guide with authenticated header → self-decrypt through every method → write
ciphertext to sibling temporary file → fsync → atomic replacement. Each new
copy requires explicit enrollment; opening an old copy cannot recover its other
credentials. Old copies are not revoked by a new export.

Passphrases, answers, hardware responses and decrypted data exist in host memory.
The configured YubiKey HMAC secret is never requested by this app; a response
leaves the device and can unlock that file if captured. There are no online
tokens. Labels, question prompts, salts, challenges, nonces, sizes and filesystem
metadata are public. Low-entropy question answers weaken the entire package
because any one method suffices. Offline files cannot enforce guessing limits.

## Commands

```sh
python3 -B vault-folio.py --self-test
python3 -B -m unittest discover -s tests -v
node tests/browser_crypto.cjs
```

Tests use synthetic plans and simulated hardware. The browser companion remains
a v1-only prototype; it cannot meet RAM-only or hardware-isolation policy.

## Required human/device acceptance

1. On a verified nonpersistent live Linux image, confirm the safe session opens
   and unsafe swap, persistent mounts, routes and radios block/lock it.
2. Exercise the actual Tk GUI: keyboard navigation, long records, scroll areas,
   edit/reload, unsaved prompts, cancel/touch timeout and clear session.
3. Enroll two distinct compatible keys in the same OTP slot number. Reopen with
   each independently; try wrong key, unplug, timeout and duplicate enrollment.
4. Reopen the actual saved file separately with every passphrase and question
   set. Check Unicode answer normalization and deliberate spelling mistakes.
5. Simulate unavailable/full/read-only media; retain a prior verified backup.
6. Let a nontechnical heir discover the program and ciphertext from the external
   note, unlock unaided, choose Beneficiary View and follow synthetic steps.
7. Independently review envelope construction, parsing/resource bounds,
   subprocess behavior, dependencies, memory assumptions and all public metadata.

Do not report tests as hardware certification, guaranteed memory erasure or
proof of legal authority. Do not add plaintext exports, telemetry, wallet secret
fields, network dependencies at unlock, or fake calendar enforcement.

## Review conventions

File issues with exact commit, affected function, reproduction using synthetic
data, expected vs actual result, severity and proposed validation. Put fixes in
small pull requests. Never attach real guides, credentials, customer data or
hardware provisioning secrets. Review correctness before visual polish.
