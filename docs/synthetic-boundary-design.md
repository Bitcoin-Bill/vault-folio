# Synthetic-file boundary before decryption — design decision pending

Status: design only; product-owner approval required before format code.
Reviewed against stack tip `105700ba142313bbb1842d1547edc05b1d2f0291`
(PR #21, following #16–#20), now merged into main
`0c17aa08aa38dc3ac2b8182f71ba4fbd17a315c4`. This document changes no format.

## Recommendation

Keep the authenticated, post-decryption `meta.syntheticTest === true` check
for VAULTFOLIO/1 and VAULTFOLIO/2 in this round. Document its limit explicitly:
a test build can derive a key and decrypt an unmarked real guide into memory
before rejecting it. It must reject before rendering or adopting that plan,
but this is not a pre-decryption confidentiality boundary. A test build's
relaxed environment means that transient plaintext exposure matters.

Do not retrofit an optional unauthenticated flag and describe it as security
isolation. If early accidental-file refusal is a product requirement, prefer
a separately versioned synthetic format with a distinct magic and authenticated
purpose/domain separation, plus the inner marker. That requires its own approved
specification and coordinated browser/Python implementation, not this UI fix.
No change permits network code, plaintext saves, or Bitcoin secrets/xpubs.

## Current formats and validators

| Format | Readers and validation | Authentication and interoperability |
| --- | --- | --- |
| VAULTFOLIO/1 | Browser `decryptPlan` requires the magic and exactly four top-level fields with supported KDF/cipher parameters and bounded decoded sizes. Python `decrypt_plan` also checks magic, four fields, parameters and bounds. | AES-GCM encrypts the JSON payload with no AAD in either implementation. Browser/Python v1 ciphertext is interoperable. Both editions must enforce the same inner-marker policy after opening. |
| VAULTFOLIO/2 | `folio_security.validate` requires exactly `magic`, `cipher`, `iv`, `methods`, `data`, and validates each method's schema before KDF/hardware access. The browser does not implement v2 unlocking. | The complete canonical header excluding `data` is payload AAD. Method metadata is also authenticated when wrapping the data key. Synthetic desktop packages are restricted to one passphrase method; browser v1 interop is not browser v2 support. |

The marker is inside authenticated plaintext in both formats. A party without
the relevant key cannot simply change it while retaining a valid GCM tag. A
credential holder can decrypt and re-encrypt a relabeled guide; this boundary
cannot certify that someone used invented rather than real data.

## What an envelope flag would require

An outer boolean (for example `syntheticTest`) is visible before key derivation.
A bounded parser could inspect it and refuse the wrong edition before prompting
for credentials, invoking a KDF or requesting a hardware response. This is an
unverified routing decision, not proof of file provenance.

Adding a fifth v1 field breaks both existing v1 readers' four-field check.
Adding a sixth v2 field breaks `folio_security.validate`'s exact field set.
Both browser source and its generated test edition, Python v1 decoding, v2
validation, synthetic helpers, save/reseal paths, and the format specification
would need coordinated changes. Enumerate exact legacy/new schemas; require
an actual boolean, not strings or truthy values; reject unknown fields and
malformed combinations. Do not merely loosen field counts. Preserve existing
size/KDF bounds and reject unsupported types before expensive work.

For v1, including purpose metadata as AAD requires changes to BOTH the browser
and Python encryption/decryption implementations and a precisely specified byte
encoding. Existing no-AAD ciphertext cannot be opened using new AAD: it requires
an explicit legacy path or authenticated re-encryption. Simply appending an
unbound field preserves crypto mechanics for upgraded readers but not old
reader compatibility or a trustworthy early classification.

For v2, public does not mean unauthenticated: the existing encryption logic
includes all header fields other than `data` in AAD. Accepting a new flag in
`validate` would therefore also affect payload authentication. Adding a flag to
an already sealed v2 file without re-encryption makes its tag fail. Excluding
the flag from AAD deliberately would make it forgeable. `reseal_preserving_methods`
currently reconstructs a fixed header; it must preserve any approved new purpose
field and authenticate it rather than silently dropping it. Test sealing,
opening, and note-saving as well as normal exports.

Do not silently redefine VAULTFOLIO/1 or VAULTFOLIO/2. An approved revision needs
unambiguous format negotiation, legacy test vectors and explicit old-reader
rejection expectations. A v1 extension cannot imply that the browser can now
open v2. Shared marker semantics and encrypted-file interop are distinct claims.

## Forgery and careless-tool analysis

| Alteration | If the flag is unbound metadata | If purpose is bound to authentication |
| --- | --- | --- |
| Real/unmarked file relabeled synthetic | Test build may accept the header and derive/decrypt real plaintext. The inner marker must still reject before UI/adoption; exposure in the relaxed test environment has already occurred. | New-format tampering fails authentication, but only after KDF/verification. It still forces work; outer inspection cannot establish authenticity. |
| Synthetic relabeled normal or flag stripped | Normal build may derive/decrypt before the inner marker rejects. A default treating absence as normal enables this downgrade route. | Tampering fails authentication for an authenticated new-format header. Legacy compatibility must not provide an alternate unbound interpretation. |
| Valid file mislabeled for the wrong edition | Early rejection causes denial of service/confusion, not recovery or access. The attacker needs no key to cause refusal. | Early refusal is still possible before the tag is checked: authentication cannot make an early reject trustworthy. |
| Tool re-encrypts after relabeling | A credential holder can produce another valid package, so neither flag nor magic proves data is synthetic. | Same limitation: authorization to encrypt is not evidence of invented content. |

A v1 ciphertext with an added unauthenticated flag is particularly important:
the original GCM payload remains valid, so the test environment can see its
plaintext before learning from the inner marker that it was a real guide.
An AAD-bound design avoids releasing plaintext on a failed GCM authentication,
but does not authenticate the early classification itself. Keep the inner marker
as the authoritative semantic check and require consistency with any outer
purpose after successful authentication. No automatic relabel-and-open fallback.

Distinct magic alone is also only routing metadata. Without authenticated
purpose/domain separation, changing the magic can route the same ciphertext to
a different edition, particularly in the current no-AAD v1 construction. A future
synthetic format should bind purpose cryptographically (and specify appropriate
KDF/wrapping domains); a magic spelling alone does not achieve that.

## Migration and existing files

Existing files have no outer purpose field. Absence means legacy/unknown, not
proof of either normal or synthetic origin. A pre-KDF policy cannot reliably
classify them without decrypting them.

Under the recommendation, leave existing v1/v2 readers and files unchanged and
retain the current post-decryption marker checks. No migration is performed.

If a future format is approved, normal hardened/offline software may retain an
explicit legacy read path and apply the inner check. Strict synthetic test builds
should refuse flagless/legacy files before KDF; recreating a disposable synthetic
fixture is preferable to guessing that a legacy file is safe. If legacy synthetic
fixtures must be migrated, open and verify them in a trusted nonpersistent offline
migration environment, verify the inner marker, and write a NEW encrypted package
with explicit approval. Never infer purpose from filename, method label, or a
missing flag; never upgrade by editing the JSON header. Retain originals, avoid
plaintext intermediate files, and do not convert real guides into test fixtures.

## Acceptance criteria for any later approved format work

- Zero KDF/hardware calls for early-refused, unambiguously wrong-purpose files.
- Flag/magic flip, removal, malformed type and outer/inner mismatch tests in both
  directions; no rendering/adoption on refusal and no permissive legacy fallback.
- Existing v1 Python/browser vectors stay green; new-format interop is specified
  and tested separately. v2 wrapping, metadata authentication, and method-preserving
  note saves remain verified. No unrequested browser v2 support.
- Legacy policy, old-reader rejection, file-format documentation and synthetic
  build generation all agree. Save output remains encrypted only.
- Product-owner decision recorded before implementation. Until then, describe
  the current boundary accurately as authenticated post-decryption refusal.

