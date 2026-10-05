# LLM review of c0fc689

Reviewed commit: `c0fc68960c3553ccc1af7d76ee64b5c14df895ef` on `review/offline-inheritance-guide`.
Uploaded tree checksum: `320b920895e32c29f6e1a346458e5de1cda9bb9807eadaef464e338d17a9c4ca`.

This is not an independent cryptographic audit, hardware certification, or merge approval. No real plans, seeds, passphrases, or YubiKey secrets were used. Unit tests were not executed in the review environment because Tk was not installed there.

## What holds up

VAULTFOLIO/2 in `folio_security.py` matches the documented envelope: fresh DEK, PBKDF2-HMAC-SHA256 at 600,000 iterations, HKDF wrap, AES-256-GCM, wrapper associated data bound to canonical method metadata, and payload associated data bound to the header including unselected methods. Malformed packages are rejected before `ykman`. Duplicate HMAC responses under the shared challenge are rejected. `folio_storage` writes ciphertext only, fsyncs, then `os.replace`; a failed replace leaves the previous file. v1 remains a separate magic. The browser prototype refuses v2.

## Findings

1. Medium — `folio_hardware_ui.hardware_job` checks `environment_safe()` before queueing success, but `saved()` calls `save_encrypted()` with no new check. A route or radio that appears in that gap can still persist ciphertext. Recheck immediately before the write and discard the envelope on failure.
2. Medium, operational — `--test-only-skip-ram-path-check` and `--test-only-synthetic-questionnaire` skip the entire air-gap gate in `App.show_gate`, not only the RAM path check. Route, Wi-Fi, and Bluetooth are not checked. Rename the flag or keep the radio and route checks.
3. Low — `bluetooth_adapters()` returns `[]` on `FileNotFoundError` for `/sys/class/bluetooth`. An unavailable check should block, as `OSError` already does.
4. Low — `default_route_exists()` reads only IPv4 `/proc/net/route`. An IPv6 default route is invisible unless an interface is also reported up. Also read `/proc/net/ipv6_route`.
5. Low — browser `b64e` uses `String.fromCharCode(...bytes)` and can throw on a large plan. Encode in chunks. The browser gate is `navigator.onLine` plus an attestation checkbox; a positive Bluetooth result does not block entry. Keep it prototype-only.
6. Low — `visible_plan` masks only `accessRecords.directAccess`. The same secret in `hint`, `notes`, `instructions`, or `ownerNotes` is shown without the reveal checkbox.
7. Low — `page_export` still says the app writes nothing to disk. `save_encrypted` writes a `.csip-sealed-*.tmp` sibling, and a crash after write and before `os.replace` can leave that ciphertext behind.
8. Low — `yubikey_response` trusts `shutil.which("ykman")` and puts the public challenge on argv. Pin a documented absolute path.
9. Docs / CI — `docs/FILE-FORMAT.md` is still titled VAULTFOLIO/1 while new exports are v2. Root PDFs duplicate `docs/research/`. `.github/workflows/checks.yml` uses floating action tags and does not prove live-Linux or YubiKey acceptance.

Question-set confirmation compares normalized `question_material()`, so case and whitespace differences pass. That matches the KDF; say so next to the confirm fields. Any one method opens the file, so a weak public question set remains an offline guessing path. Do not add a local clock gate. Do not merge this draft on this review.
