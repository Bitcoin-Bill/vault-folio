# Second-revision bug review

Committed for the record from the uploaded review of `c0fc68960c3553ccc1af7d76ee64b5c14df895ef` (zip sha256 `320b920895e32c29f6e1a346458e5de1cda9bb9807eadaef464e338d17a9c4ca`). Spot-checked against that tree: N1, N2, N3, N4, C1, and C2 match the code. This commit does not apply the fixes and is not a merge approval.

## New bugs

- N1 CRASH: `canvas_quorum` / `canvas_psbt_flow` call `_short` at vault-folio.py lines 728, 745, 748, 751, and 760, and `_short` is not defined. Any plan with at least one vault throws NameError while rendering the export-page diagrams. Restore the helper and add a smoke check that actually calls the canvas builders.
- N2: answering "I'm not sure" to both structure questions stores setupType `unsure` because `resolved or "unknown"` treats that string as truthy. Risk engine and runbook only recognize `unknown`. Fix: `setupType = resolved if resolved in ("single", "multi") else "unknown"`.
- N3: 1-of-1 vaults are drawn as "1-OF-1 MULTISIG". Special-case a single signature.
- N4: README points to `AIRGAP-TRANSFER-README.txt`, which is not in the tree.
- N5: browser still says "Single-sig (small amounts only)"; desktop says "Single-signature (one key)". Catalog parity does not cover SCRIPTS.
- N6: delayed route yes with kind unsure appends no recoveryPaths record and leaves timelock disabled.
- N7: intake-created recoveryPaths records are not tied to the vault, so deleting the vault orphans them.
- N8: `--test-only-skip-ram-path-check` skips the entire air-gap gate, not only the RAM path check.

## Still open

- C1: jurisdiction and legal notes are appended twice in `build_runbook_text` (lines 543-546); rehearsal notes twice (lines 691 and 695).
- C2: home screen still says "nine-folio"; the wizard has 15 steps.
- C3: stale Folio numbers passed to `Wizard.page()` are dead copy.
- C4: export caption promises pictures the beneficiary view does not show, and those pictures currently crash (N1).
- C5: module docstring still claims Linux, macOS, and Windows; enforced policy is live Linux.
- C6: desktop exports VAULTFOLIO/2; browser reads v1 only and refuses v2.
- C7: `self_test()` covers v1 crypto only, not the v2 seal/open path.

## Suggested order

Fix N1, then N2, then the C1 deletions. Then the copy sweep (N3, N4, N8, C2). Do not change `folio_security.py`, `folio_storage.py`, or the envelope in that pass. Do not merge on this note.
