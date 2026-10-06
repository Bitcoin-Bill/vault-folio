# Design proposal: refusing production guides before test-mode decryption

Status: **design only; product-owner decision required before format code**.
Baseline: main at `0c17aa08aa38dc3ac2b8182f71ba4fbd17a315c4`.
This proposal does not change validators, encryption, file formats, or migration behavior.

## Decision to make

Distinguish two goals:

1. Refuse an accidentally selected ordinary production file before a password KDF or hardware operation.
2. Prevent a modified production envelope from being decrypted in an unsafe test session, even when the correct credential is supplied.

An unauthenticated outer flag supports the first goal only. It cannot prove that its ciphertext contains invented data. Neither a filename nor an outer magic string alone provides that proof.

Recommendation: retain the current formats and honest post-decryption limitation until approval. If pre-decryption isolation is required, approve a **separately versioned test format with distinct magic, cryptographic domain separation, and authenticated test metadata**, rather than adding a permissive optional flag to existing production formats. This is a proposed direction, not a format allocation or implementation authorization.

## Current behavior and compatibility

| Reader/writer | Existing shape and validation | Authentication and interop |
|---|---|---|
| Browser v1 | `decryptPlan` requires `VAULTFOLIO/1`, four top-level properties, fixed PBKDF2 parameters, and AES-GCM lengths. `showDecrypt` checks `meta.syntheticTest` after decrypting. | AES-GCM uses no additional authenticated data (AAD). The JSON envelope header is not explicitly authenticated as AAD. Payload, including its inner marker, is authenticated. |
| Python v1 | `vault-folio.py:decrypt_plan` checks the same magic, required values, lengths and four-property envelope size. | PBKDF2-SHA-256 (600,000 rounds), UTF-8 credentials and AES-256-GCM interoperate with the browser. AES-GCM receives `None` AAD. |
| Python v2 | `folio_security.validate` requires exactly `magic, cipher, iv, methods, data`; method metadata is separately strict and bounded. Validation precedes key derivation and YubiKey interaction. | Payload AAD authenticates the canonical public header, including magic and methods. Key wrapping authenticates method metadata and uses the v2 domain string. |
| Desktop synthetic opener | `folio_synthetic.open_synthetic_envelope` accepts one passphrase method in v2, then checks the authenticated inner marker. | It does not accept browser v1 test exports. The shared marker survives Python/browser v1 crypto tests, but this does not mean their synthetic-mode user interfaces accept the same files. |

Source references: `browser-edition/index.html` (`decryptPlan`, `showDecrypt`, `checkOpenBoundary`, `prepareExportPlan`); `vault-folio.py` (`decrypt_plan`, `open_choice`); `folio_security.py` (`validate`, `seal`, `open_package`, `reseal_preserving_methods`); `folio_synthetic.py`; `tests/browser_crypto.cjs`.

All current synthetic checks happen after payload decryption. Rejection prevents normal rendering/use but does not undo plaintext exposure to that process. Dropping references is not guaranteed memory erasure.

## Option A: an outer test flag

A proposed outer `syntheticTest: true` would be a routing hint visible before credentials are processed.

Both v1 readers would need explicit, matching allowed-key sets for legacy and new envelopes, strict boolean validation, identical missing-flag semantics, and rejection of unknown extra fields. Merely changing a key-count check from four to five is insufficient. Exporters, the generated browser build, and cross-edition tests must change together. Existing readers reject the additional property, so this is not transparently backward-compatible despite keeping the old magic.

V2's exact-key validator must also deliberately recognize the new schema. All seal, open and reseal paths must preserve the flag. Today resealing constructs a new fixed header, so an unhandled extra flag would be lost. Changing v2's authenticated header requires encryption/tag recomputation; editing an existing file's JSON is not migration.

A flag outside ciphertext is **not necessarily outside authentication**. V2 already authenticates its public header as AAD. If included consistently in that header, a new flag can be verified after key derivation. It remains untrusted when making the early routing decision. V1 has no header AAD today; authenticating the proposed flag there changes encryption semantics and requires explicitly versioned compatibility handling.

### Forgery and careless-tool analysis

- **Production to test (false/absent → true):** an attacker or mistaken tool can change an unauthenticated v1 flag without knowing the password. A test session then reaches key derivation and may decrypt the original production plaintext before the inner marker rejects it. The attacker does not obtain the password or break AES, but can defeat the intended early-routing safeguard.
- **Test to production (true → false/absent):** a normal session may derive a key and decrypt test data. An authoritative inner marker still rejects it; removing that check risks treating test files as real guides.
- **Authenticated v2 flag flipped either way:** an early parser can still be misdirected, but a correctly implemented AAD check rejects the tampered envelope at authentication. Key derivation, and potentially a hardware request in a general opener, can already have occurred. No authenticated plaintext should be exposed on tag failure. Test mode should retain its passphrase-only restriction.
- **Stripping or adding a flag:** legacy fallback that ignores it can become a downgrade route. Dispatch must not retry a rejected test envelope with production cryptographic rules.
- **Careless re-encryption with valid credentials:** a tool can create a genuinely authenticated file with an incorrect classification. No cryptographic marker proves that humans entered invented data.

Keep the encrypted inner marker and require exact agreement with the outer classification. It remains authoritative for the decrypted document's declared classification; a mismatch is an error, never an automatic conversion. Its authority is limited to authenticated declaration, not verification that the contents are safe.

## Option B: distinct test magic

Distinct magic makes unmodified production files easy to reject before KDF or hardware work, without extending the old production envelope shape. Existing readers fail closed on unknown magic.

However, changing magic alone is not enough for v1: because it is not AAD and the derivation is unchanged, an attacker can relabel a production envelope and still reach its original plaintext with the correct password. V2's authenticated magic provides stronger tamper detection, but still cannot authenticate an early dispatch decision before deriving a key.

A future test format should therefore:

- Use explicit versioned test-only dispatch, with no production fallback in the test opener.
- Separate test and production key-derivation domains, not just labels. For v2 this includes the wrapping domain; for a browser-compatible passphrase format both editions must specify exactly the same derivation bytes.
- Authenticate classification and version in AAD, while retaining and checking the encrypted inner marker.
- Reject ordinary production magic, malformed/unknown versions, and incompatible method types before KDF or hardware operations.
- Preserve all existing resource limits and do not expose unauthenticated plaintext.
- Regenerate the browser test build from its reviewed source.

Domain separation prevents merely relabeling an old production file from recovering its original payload key. It does not prevent wasted KDF work after a forged test label, detect a malicious producer who knows the credential, or secure a compromised browser/OS. It is not a claim that all files routed into test mode are harmless.

Do not silently redefine `VAULTFOLIO/1` or `VAULTFOLIO/2`. A future specification must allocate and document new test-format identifiers and exact cryptographic rules. The existing browser remains v1-only; giving it a flag does not add v2 method support. Product ownership must choose whether both editions gain a shared passphrase-only test format or retain explicitly different test formats. Preserve existing production v1 interoperability in either case.

## Migration

- Leave existing sealed files byte-for-byte intact; no automatic rewrite, relabeling, plaintext export, or background persistence.
- Existing production files without an outer flag keep their current production-reader compatibility.
- A new strict test reader should reject all legacy production-format envelopes before KDF, including old synthetic files that lack an outer discriminator. It cannot safely tell those two classes apart at that point.
- If approved, migrate old synthetic files only in a trusted offline/nonpersistent environment: authenticate with a compatible legacy reader, require the inner marker, and explicitly save a new encrypted test-format copy. Preserve the original until the new copy is independently reopened and verified.
- Do not offer a test-session “try anyway” legacy fallback. Do not mark a real production plan as synthetic merely to make it load.
- An owner can recreate invented fixtures instead of migrating. Users must not lose access to existing production guides just because a test format changed.
- A missing flag must have a documented meaning, not be guessed from a filename. In a flag design it is legacy/unknown, not evidence of synthetic content.

## Acceptance criteria for a separately approved implementation

1. Production and legacy-unclassified envelopes are rejected in test mode before KDF/hardware calls; assert those calls were not made.
2. Flipping, deleting, adding, or changing the type of classification metadata never causes a production payload to be accepted in test mode. Relabel tests must exercise cryptographic domain separation, not only UI checks.
3. Outer/inner disagreement fails closed; corrupted AAD fails authentication; no downgrade/fallback route exists.
4. Python/browser v1 production fixtures remain interoperable. New test-format vectors cover both implementations where support is claimed.
5. V2 unknown-field, method, resource-bound and reseal tests preserve authenticated classification without losing unlock methods.
6. Migration is explicit and ciphertext-only, preserves the original, and never runs in an unsafe test session.

Until the owner approves a format design, document the present boundary accurately: test mode rejects ordinary guides **after decryption**, and must never be given real guides or their credentials. No format code is part of this proposal.
