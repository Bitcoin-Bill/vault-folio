# A private guide for heirs

Record instructions and references only. Never record Bitcoin seeds, private
keys, wallet seed passphrases, SLIP39 words, XOR seed parts, complete
wallet descriptors or the unlock answers/passphrase needed to unlock this very guide. Dropdowns describing a backup
method do not ask for the underlying secret. Free-text fields cannot reliably
identify every secret; the boundary is also a user responsibility.

Owners may deliberately include direct **journal, document or watch-only access
credentials** in the dedicated access section; hint-only is the default. These
values are encrypted with everything else and shown in the decrypted heir guide.
Switching a record to hint-only deletes its direct credential from the current
plan, not from older exported files or every RAM copy. Generic free text accepts
owner-authored content but should not be used to bypass this separation.

## Dynamic records

## Guided wallet interview

When a plan has no wallet records, the desktop editor starts a one-question-at-a-time
interview. It begins by asking whether one key or several separate keys are needed
to spend. Single-signature plans skip the multisignature quorum questions; a
multisignature plan asks for the total keys and required threshold. “I’m not sure”
is an accepted answer and does not create guessed signing rules. Follow-up questions
about a delayed recovery route appear only when the owner reports one. The screen
shows a running summary while answers build the wallet record in memory.

After the interview, the full folio is available for inspection and editing. The
interview is a guided starting point, not a wallet-policy analyzer: verify every
answer against the actual wallet and rehearse recovery before relying on the guide.

- **Lawyers and custodians:** add any number of contacts, their role, known contact
  channel, jurisdiction, what access they actually hold, related vault/key labels,
  agreed release conditions, required-document hints, successors, and review dates.
  Names in the questionnaire do not grant legal authority or cryptographic access.
- **Backup inventory:** add any number of labeled items linked by readable vault/key
  labels, medium, custodian, site alias, family clue, person holding the next clue,
  access prerequisites, alternative route and last test date. A location clue can
  simply be “ask the trustee about the blue packet.” Exact addresses are optional.
- **Conditional questions:** SLIP39 and XOR ask about reconstruction requirements;
  encrypted backups ask who holds their separate unlock information; guide YubiKeys
  ask about device labels, slots and spare/recovery custody. Never enter secret values.
- **Owner-authored steps:** ordered actions, responsible person, prerequisites,
  success checks, stop conditions, fallback and offline manual references. These
  become separate steps in Beneficiary View.
- **Access instructions:** EntropyLab journal availability, format/reader/version,
  backup copy, access hints or optional direct journal password; watch-only
  wallet app/device, network, configuration-copy hint, rescan reference, node
  instructions, known-address verification location; legal documents, archives,
  provider support routes and offline-computer instructions. Add unlimited custom
  entries, dependencies, fallback routes and last-access tests.
- **Recovery paths:** separately describe legal release, provider-enforced delays,
  on-chain relative/absolute timelocks and seed-share reconstruction. Record each
  path's labels, threshold, timing, refresh owner, dependencies and fallback.

All records are included in the encrypted guide and heir runbook. Existing files
without these sections remain readable; new records are added when editing.
Desktop risk review flags missing discovery routes, unverified custodians,
concentrated access, absent successors and incomplete timed recovery paths.
It does not calculate real wallet spendability or verify any legal agreement.

## Presets and their limits

`folio_catalog.py` is the catalog source. The browser companion embeds a snapshot
so it makes no network fetches; `tests/browser_crypto.cjs` checks catalog parity.
Each preset has an official project/provider reference and a review date. The
catalog was reviewed on 2026-10-04. It is deliberately extensible, not a claim to
cover every available product, firmware combination or provider plan.

The presets cover single-signature backups; DIY 2-of-3 and 3-of-5; Core/Yeti 3-of-7;
Sparrow, Specter, Electrum and Nunchuk coordination; Liana timed recovery; and
Unchained, Casa and Nunchuk assisted/inheritance arrangements. Provider quorums
are editable examples unless your agreement confirms them. A preset adds a new
record and never overwrites an existing vault or creates an actual Bitcoin wallet.

BIP39, SLIP39, Seed XOR, encrypted device backups, Electrum/Core backups and
configuration/descriptor records are distinct options. SLIP39 and XOR reconstruct
ONE signing key. They do not create independent multisig keys. Liana's top-level
M/N describes the primary path only: document every delayed path separately.
The app's old flat quorum diagrams are not a Miniscript policy analyzer.

## Primary references

- Sparrow: https://sparrowwallet.com/features/
- Bitcoin Core/Yeti: https://github.com/bowlarbear/yeti-2.0
- Specter: https://docs.specter.solutions/desktop/multisig-guide/
- Electrum: https://electrum.org/
- Nunchuk DIY: https://resources.nunchuk.io/getting-started/multidevicemultisig/
- Nunchuk inheritance: https://nunchuk.io/inheritance
- Liana: https://wizardsardine.com/blog/what-is-liana/
- Unchained: https://help.unchained.com/what-multisig-quorum-should-i-choose
- Casa: https://casa.io/inheritance
- Trezor SLIP39: https://trezor.io/guides/backups-recovery/general-standards/slip39-faqs
- COLDCARD Seed XOR: https://coldcard.com/docs/seedxor/
- COLDCARD encrypted backups: https://coldcard.com/docs/backups/

Verify actual software/firmware and contract requirements when preparing or
rehearsing a guide. Product names are descriptive options, not endorsements.

Keep a simple discovery note outside the encrypted package so heirs can locate
the file, compatible offline application and separate unlock custodian. Clues
for opening the guide must not exist only inside the locked guide.
