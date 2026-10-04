"""Offline questionnaire catalog. Presets document choices, never create wallets.

Source review: 2026-10-04. Not an exhaustive compatibility or endorsement list.
Custom values remain available; verify exact software, firmware and contract.
"""
REVIEWED = "2026-10-04"
PROFILES = [
    {"name": "Custom / existing arrangement", "m": 2, "n": 3, "coordinator": "Other / undecided", "note": "Document the arrangement you actually tested; edit every suggested value.", "source": ""},
    {"name": "Single signature + separate physical backups", "m": 1, "n": 1, "coordinator": "Other / undecided", "note": "Multiple copies of one seed do not make multisig. Record seed format and separate passphrase custody.", "source": "https://trezor.io/guides/backups-recovery/general-standards/how-to-use-a-wallet-backup"},
    {"name": "DIY 2-of-3 multisig (Sparrow)", "m": 2, "n": 3, "coordinator": "Sparrow Wallet", "note": "Three independent signing keys. Preserve wallet configuration / descriptor copies and test recovery.", "source": "https://sparrowwallet.com/features/"},
    {"name": "DIY 3-of-5 multisig (Sparrow)", "m": 3, "n": 5, "coordinator": "Sparrow Wallet", "note": "Five independent keys; three authorize spending. Document who can reach each key, including backups.", "source": "https://sparrowwallet.com/features/"},
    {"name": "Bitcoin Core / Yeti 2.0 style", "m": 3, "n": 7, "coordinator": "Bitcoin Core (Yeti-style)", "note": "Starting values only: confirm the exact guide revision and your actual quorum. Record offline machines, descriptor copies, archival media and rehearsal dates.", "source": "https://github.com/bowlarbear/yeti-2.0"},
    {"name": "Specter Desktop multisig", "m": 2, "n": 3, "coordinator": "Specter", "note": "Editable example quorum. Record node, signer interoperability and exported wallet configuration.", "source": "https://docs.specter.solutions/desktop/multisig-guide/"},
    {"name": "Electrum multisig", "m": 2, "n": 3, "coordinator": "Electrum", "note": "Editable example quorum. Record exact seed format; an Electrum seed is not automatically BIP39.", "source": "https://electrum.org/"},
    {"name": "Nunchuk self-managed multisig", "m": 2, "n": 3, "coordinator": "Nunchuk", "note": "Editable example quorum. Preserve BSMS / wallet configuration and independent recovery instructions.", "source": "https://resources.nunchuk.io/getting-started/multidevicemultisig/"},
    {"name": "Liana / Miniscript timed recovery", "m": 1, "n": 1, "coordinator": "Liana", "timelock": True, "note": "M/N describes the primary path ONLY. Separately record each delayed recovery path, key labels, threshold, relative delay and refresh procedure. A timer is not proof of death.", "source": "https://wizardsardine.com/blog/what-is-liana/"},
    {"name": "Unchained collaborative custody", "m": 2, "n": 3, "coordinator": "Unchained", "note": "Common example; verify your contracted quorum. Record provider-held keys, legal contact and recovery without the provider.", "source": "https://help.unchained.com/what-multisig-quorum-should-i-choose"},
    {"name": "Casa collaborative custody", "m": 2, "n": 3, "coordinator": "Casa", "note": "Editable example, not a claim about your subscription. Confirm key count, recovery and inheritance process in your current contract.", "source": "https://casa.io/inheritance"},
    {"name": "Nunchuk assisted / autonomous inheritance", "m": 2, "n": 4, "coordinator": "Nunchuk", "note": "Example only; choose your actual plan. Distinguish provider-enforced off-chain release from on-chain Miniscript recovery. Record beneficiary requirements without secrets.", "source": "https://nunchuk.io/inheritance"},
]
BACKUP_SCHEMES = ["BIP39 seed backup", "BIP39 + separately held passphrase", "SLIP39 single share", "SLIP39 threshold shares (one signing key)", "Seed XOR (all parts required; one signing key)", "Encrypted device backup", "Electrum seed format", "Bitcoin Core wallet backup", "Descriptor / BSMS / wallet configuration", "Package YubiKey", "Other / custom"]
SIGNERS = ["COLDCARD Q / Mk4", "Trezor", "Ledger", "BitBox02", "Foundation Passport", "Keystone", "Jade", "SeedSigner", "Krux", "Specter DIY", "TAPSIGNER", "Air-gapped Bitcoin Core", "Other / custom"]
MEDIA = ["Steel / metal", "Paper", "MicroSD", "USB drive", "Archival optical disc", "Hardware device", "Sealed legal packet", "Other / custom"]
FIELDS = {
    "lawyers": [
        ("name", "Lawyer / firm / trusted contact", None),
        ("role", "Role", ["Lawyer", "Executor", "Trustee", "Notary", "Technical helper", "Backup custodian", "Other / custom"]),
        ("contact", "Known contact method / independently verified channel", None),
        ("jurisdiction", "Jurisdiction / engagement reference (optional)", None),
        ("access", "What access do they have?", ["No access; advice only", "Location hints only", "Encrypted package only", "Package unlock credential only", "Package AND unlock credential", "One Bitcoin key backup", "Several Bitcoin key backups", "Descriptor / configuration only", "Other / custom"]),
        ("items", "Vault / key / backup labels they can access (no secrets)", None),
        ("release", "Release conditions", ["Owner request", "Death documentation + executor authority", "Incapacity documentation", "Trust instructions", "Joint written approval", "Other / custom", "Not yet agreed"]),
        ("proof", "Required documents and where instructions are held (hints)", None),
        ("alternate", "Successor if firm closes / contact unavailable", None),
        ("reviewed", "Last verified date / acknowledgment", None),
        ("notes", "Custom conditions or limits (no secret values)", None),
    ],
    "backupRecords": [
        ("label", "Backup label", None),
        ("vault", "Related vault / key label", None),
        ("scheme", "Backup / access method", BACKUP_SCHEMES),
        ("medium", "Physical medium", MEDIA),
        ("custodian", "Who holds it / can retrieve it?", None),
        ("site", "Site alias (e.g. Site A; same alias = same failure location)", None),
        ("hint", "Family location hint (no exact address required)", None),
        ("locator", "Who knows the full location / next clue?", None),
        ("conditions", "Access prerequisites / release conditions (no codes)", None),
        ("fallback", "Alternate contact / backup route if inaccessible", None),
        ("tested", "Last restore or access rehearsal date", None),
        ("notes", "Custom details / compatible restore tool version", None),
    ],
    "recoveryPaths": [
        ("label", "Recovery path name / related vault", None),
        ("mechanism", "Release mechanism", ["Human / legal release", "Provider-enforced off-chain delay", "Bitcoin on-chain relative timelock", "Bitcoin on-chain absolute timelock", "Threshold seed-share reconstruction", "Other / custom"]),
        ("keys", "Required key or share labels (never secret values)", None),
        ("threshold", "Required count / total count for THIS path", None),
        ("delay", "Delay / units / starting event (if any)", None),
        ("refresh", "How and when to refresh / responsible person", None),
        ("dependencies", "Provider, software and configuration-copy dependencies", None),
        ("fallback", "Recovery if provider / lawyer / owner is unavailable", None),
        ("tested", "Last test date and result", None),
        ("scenario", "When is this route needed?", ["Owner death", "Owner incapacity", "Both primary contacts unavailable", "One key or site lost", "Provider unavailable", "Lost guide unlock key", "Other / custom"]),
        ("stop", "Stop conditions / who resolves disagreement", None),
    ],
}
EXTRA_BACKUP_FIELDS = {
    "SLIP39 threshold shares (one signing key)": [("threshold", "Shares required / total; group thresholds if used", None), ("groups", "Share labels and group/site aliases (no share words)", None)],
    "Seed XOR (all parts required; one signing key)": [("threshold", "Number of parts required (all parts)", None), ("groups", "Part labels / independent site aliases", None)],
    "Package YubiKey": [("device", "Key label / model / configured OTP slot (no secret)", None), ("lossPlan", "If this guide key is lost: separately protected guide-copy location hint", None)],
    "BIP39 + separately held passphrase": [("separate", "Passphrase custodian / location hint (never the passphrase)", None)],
    "Encrypted device backup": [("separate", "Backup-password custodian / hint (never the password)", None)],
}


def ensure_sections(plan):
    for key in FIELDS:
        plan.setdefault(key, [])
    return plan


def extra_runbook(plan):
    lines = ["", "CONTACTS, BACKUP HINTS AND ALTERNATE RECOVERY PATHS",
             "These are instructions, not proof of authority or automatic release."]
    for key, fields in FIELDS.items():
        lines.append("\n" + {"lawyers": "Lawyers and custodians", "backupRecords": "Backup inventory and clues", "recoveryPaths": "Recovery paths", "accessRecords": "Guide, journal and watch-only access", "instructions": "Owner-authored recovery steps"}[key])
        for i, row in enumerate(plan.get(key, []), 1):
            lines.append(f"  Record {i}")
            all_fields = record_fields(key, row)
            for name, label, _ in all_fields:
                if row.get(name):
                    lines.append(f"    {label}: {row[name]}")
    return "\n".join(lines)


def extra_risks(plan):
    out = []
    def add(title, detail):
        out.append({"sev": "warning", "title": title, "detail": detail,
                    "fix": "Document an independent route and rehearse it with the responsible people."})
    for row in plan.get("lawyers", []):
        if row.get("access") and row["access"] != "No access; advice only" and not row.get("alternate"):
            add("Custodian has no named successor", row.get("name") or "Unnamed contact")
        if row.get("access") in ("Package AND unlock credential", "Several Bitcoin key backups"):
            add("Concentrated access needs review", "Check whether this contact can open the package or reach a spending quorum alone.")
        if row.get("access") and not row.get("reviewed"):
            add("Custodian arrangement is unverified", "Record acknowledgment and a review date; selecting a role grants no authority.")
    for row in plan.get("backupRecords", []):
        if not row.get("hint") and not row.get("locator"):
            add("Backup has no usable discovery route", row.get("label") or "Unnamed backup")
        if row.get("scheme") in ("SLIP39 threshold shares (one signing key)", "Seed XOR (all parts required; one signing key)") and not row.get("threshold"):
            add("Seed reconstruction requirement missing", "Seed shares reconstruct one key; they are not independent multisig signers.")
    if any((v.get("timelock") or {}).get("enabled") for v in plan.get("vaults", [])) and not plan.get("recoveryPaths"):
        add("Timed recovery path is undocumented", "Record each path separately; a single M-of-N count cannot describe a Miniscript policy.")
    for row in plan.get("recoveryPaths", []):
        if "timelock" in row.get("mechanism", "") and (not row.get("delay") or not row.get("keys")):
            add("Incomplete on-chain recovery path", "Record the delay, units, starting event, and required key labels.")
    for row in plan.get("accessRecords", []):
        if row.get("mode") == "Direct access details inside encrypted guide" and row.get("directAccess"):
            add("Guide contains direct access credentials", "Anyone who unlocks this guide can read the entered access details. Keep an independent route outside it.")
        if row.get("exists") in ("Available and tested", "Available; not tested") and not row.get("where"):
            add("Access item has no discovery instructions", row.get("label") or row.get("kind", "Access item"))
    return out

# Access records deliberately distinguish guide-only credentials from Bitcoin secrets.
FIELDS['accessRecords'] = [
    ('label', 'Access item / recognizable name', None),
    ('kind', 'What does this help heirs access?', [
        'EntropyLab journal', 'Watch-only wallet', 'Wallet coordinator / configuration backup',
        'Bitcoin node / watch-only server', 'Encrypted guide copy', 'Legal documents / will / trust',
        'Backup inventory / location map', 'Encrypted document archive', 'Provider account / support route',
        'Offline computer / live USB instructions', 'Other / custom']),
    ('exists', 'Status', ['Available and tested', 'Available; not tested', 'Planned', 'Not applicable', 'Unknown']),
    ('where', 'Where to find it (path / device alias / location hint)', None),
    ('custodian', 'Who can help / who controls access?', None),
    ('mode', 'How should access instructions be recorded?', ['Hint only', 'Direct access details inside encrypted guide']),
    ('hint', 'Password / access hint or separate custodian (not a wallet seed)', None),
    ('requirements', 'Required device, software/version, account or second factor (hints allowed)', None),
    ('fallback', 'If unavailable: alternate copy, contact or access route', None),
    ('tested', 'Last successful access test / person who tested it', None),
    ('offlineCopy', 'Offline copy of required software / manuals / verification instructions', None),
    ('renewal', 'Renewal, maintenance or account-continuity responsibility', None),
    ('notes', 'Additional instructions / custom questions', None),
]
ACCESS_EXTRA = {
    'EntropyLab journal': [
        ('journalFormat', 'Journal format / application version / compatible reader', None),
        ('journalCopy', 'Independent journal backup or export location / hint', None),
        ('journalPurpose', 'What the journal documents (description only; no Bitcoin secret material)', None)],
    'Watch-only wallet': [
        ('walletSoftware', 'Watch-only app / version / device alias', None),
        ('walletNetwork', 'Bitcoin network', ['Mainnet', 'Testnet', 'Signet', 'Regtest', 'Unknown']),
        ('walletConfig', 'Descriptor / wallet-configuration copy location or hint', None),
        ('walletRescan', 'Birth height/date or rescan instructions', None),
        ('walletNode', 'Node/server connection instructions or separate hint', None),
        ('walletCheck', 'Where a known address-verification record is kept', None)],
}
ACCESS_DIRECT = [('directAccess', 'Optional guide/journal/watch-only access details (encrypted; NOT Bitcoin seeds or private keys)', None)]


def record_fields(section, row):
    fields = list(FIELDS[section])
    if section == 'backupRecords':
        fields += EXTRA_BACKUP_FIELDS.get(row.get('scheme'), [])
    if section == 'accessRecords':
        fields += ACCESS_EXTRA.get(row.get('kind'), [])
        if row.get('mode') == 'Direct access details inside encrypted guide':
            fields += ACCESS_DIRECT
    return fields


FIELDS['instructions'] = [
    ('title', 'Step title (records are followed in the order added)', None),
    ('audience', 'Who should do this?', ['Beneficiary', 'Executor', 'Trustee', 'Technical helper', 'Joint action', 'Other / custom']),
    ('appliesTo', 'Related vault / backup / access-item labels', None),
    ('before', 'Before starting: prerequisites / approvals / people needed', None),
    ('action', 'What to do, in plain language (instructions, not Bitcoin secrets)', None),
    ('success', 'How to know this step worked', None),
    ('stop', 'When to stop and ask for help', None),
    ('fallback', 'If this fails: alternate contact / route', None),
    ('reference', 'Offline manual / file / tested procedure location or hint', None),
]

# Handoff details are encrypted instructions, never an enforced calendar lock.
FIELDS["lawyers"].extend([
    ("guideFile", "Encrypted guide copy / safety deposit box hint", None),
    ("appCopy", "Offline program, dependencies and instructions location / hint", None),
    ("unlockLabel", "Which guide unlock method label does this custodian hold? (no secret)", None),
    ("releaseDate", "Requested release date / event (advisory; not cryptographically enforced)", None),
    ("discovery", "Where is the non-secret discovery note for family?", None),
])
