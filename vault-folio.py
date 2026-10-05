#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VAULT FOLIO — offline desktop edition
============================================
An offline plan-authoring tool for Bitcoin cold storage and inheritance.

It documents HOW a cold storage setup is built and HOW heirs recover it,
then seals that plan into one encrypted file (.csp.json). It never touches
keys, seeds, xprvs, or xpubs-by-value — it stores the map, not the treasure.

  - Local Python modules, standard-library GUI (tkinter). No browser engine, no web
    storage, no cookies, no caches — nothing persists in the background.
  - Real guide creation/viewing requires a supported live Linux session with
    the RAM, swap, process, and air-gap checks satisfied. Other OSes are not
    supported for real guide data.
  - The app does not persist plaintext plans or write logs/bytecode. Encrypted
    saves use a temporary ciphertext sibling for atomic replacement.
  - Encryption: AES-256-GCM, key via PBKDF2-HMAC-SHA256 (600,000 rounds).
    Only external dependency: the `cryptography` package.
  - The encrypted JSON format is documented independently so other offline
    applications can read the plan in the future.

Requires: Python 3.9+, tkinter, cryptography
Run:      python3 vault-folio.py          (normal; requires verified RAM-backed session)
          python3 vault-folio.py --test-only-synthetic-questionnaire (no checks or file access)
          python3 vault-folio.py --self-test   (headless crypto/risk check)
"""

import base64
import glob
import json
import math
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
import uuid
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk

sys.dont_write_bytecode = True  # RAM discipline: never drop __pycache__ on disk

from folio_memory import harden_process, memory_report, discard_plan
from folio_beneficiary import show_beneficiary
from folio_document import prepare_plan

from folio_catalog import (PROFILES, FIELDS, EXTRA_BACKUP_FIELDS, SIGNERS,
                           ensure_sections, extra_runbook, extra_risks, record_fields)

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    print("Missing dependency: cryptography\nInstall with:  pip install cryptography")
    sys.exit(1)

from folio_hardware_ui import add_export_controls, open_hardware
from folio_security import MAGIC as HARDWARE_MAGIC
from folio_phase1 import start_phase1

APP_NAME = "Vault Folio"
VERSION = "2.1-guide-preview"
PLATFORM = platform.system()  # "Linux" | "Darwin" | "Windows" | other
ENC_MAGIC = "VAULTFOLIO/1"
KDF_ITERATIONS = 600_000
MAX_PLAN_BYTES = 10 * 1024 * 1024

# --------------------------------------------------------------------------
# Questionnaire option vocabularies
# --------------------------------------------------------------------------
TIERS = ["Deep vault (no timelock)", "Family vault (timelocked decay allowed)",
         "Spending / liquidity wallet", "Collaborative custody slice"]
SCRIPTS = ["P2WSH — wsh(sortedmulti(...))", "Taproot / Miniscript (Liana-style leaves)",
           "Single-signature (one key)", "Not sure yet"]
COORDS = ["Bitcoin Core (Yeti-style)", "Sparrow Wallet", "Nunchuk", "Liana",
          "Casa", "Unchained", "Specter", "Electrum", "Caravan", "Other / undecided"]
DEVICES = ["SeedSigner (stateless QR)", "Krux (stateless QR)", "Jade (stateless mode)",
           "BitBox02-class (secure element)", "Air-gapped laptop + Bitcoin Core",
           "COLDCARD (see warning)", "Trezor / other", "Undecided"] + SIGNERS
GENMETHODS = ["Dice / coins / cards + offline calculator (EntropyLab)",
              "Device RNG (device-generated)", "Bitcoin Core wallet generation",
              "Imported existing seed", "Undecided"]
MEDIA = ["Steel / metal plate", "Paper (NATO-phonetic, checksum)",
         "Archival optical disc + printed paper", "Encrypted digital file",
         "Hardware device only (no separate backup)"]
PASSPHRASE = ["None — explicit record of that", "Stored at a separate site",
              "Sealed copy held by trustee", "Memory only (dangerous)", "Undecided"]
MECHANISMS = [
    "Distributed keys — heirs reach a quorum via trustee/executor after death",
    "On-chain timelock decay — recovery path opens after inactivity (Liana/Nunchuk style)",
    "Collaborative custody inheritance program (Casa/Unchained/Nunchuk assisted)",
    "Letter + executor only (simple, single-sig or small amounts)",
    "Combination of the above",
    "Not decided yet",
]
RITUAL = [
    ("qr", "PSBT crosses the air gap by QR code (UR / animated)"),
    ("verify2", "PSBT decoded on a second, independent tool before signing"),
    ("three", "Three displays agree before signing: coordinator, second watch-only device, signer"),
    ("change", "Change outputs confirmed to belong to the wallet"),
    ("small", "Small test transaction before any large spend"),
    ("never2", "Never two quorum seeds loaded on one signer in one session"),
]
YESNO3 = ["Yes — done and dated", "Partially", "Not yet"]


def blank_plan():
    return {
        "meta": {"app": "Vault Folio", "version": 1, "created": date.today().isoformat(),
                 "planName": "", "owner": "", "jurisdiction": "", "legalNotes": ""},
        "people": {"executor": "", "trustee": "", "helper": "", "heirs": []},
        "vaults": [],
        "signing": {"medium": "", "verifyRitual": [], "testSpend": "", "coordinatorNotes": ""},
        "backups": {"descriptorLocations": [], "watchOnly": "", "rescanHeight": "",
                    "sampleAddresses": "", "testedSoftware": ""},
        "inheritance": {"mechanism": "", "releaseConditions": "", "legalDocs": "",
                        "letterLocation": "", "heartbeat": "", "canary": ""},
        "rehearsal": {"restoreDrill": "", "familyWalkthrough": "", "testSpendDate": "", "notes": ""},
        "ownerNotes": "",
    }


# --------------------------------------------------------------------------
# Crypto — versioned and documented envelope
# --------------------------------------------------------------------------
def encrypt_plan(plan: dict, passphrase: str) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object.")
    plaintext = json.dumps(plan, ensure_ascii=False).encode("utf-8")
    if len(plaintext) > MAX_PLAN_BYTES:
        raise ValueError("Plan is too large to save.")
    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    key = kdf.derive(passphrase.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plaintext, None)
    return {
        "magic": ENC_MAGIC,
        "kdf": {"name": "PBKDF2", "hash": "SHA-256", "iterations": KDF_ITERATIONS,
                "salt": base64.b64encode(salt).decode()},
        "cipher": {"name": "AES-256-GCM", "iv": base64.b64encode(iv).decode()},
        "data": base64.b64encode(ct).decode(),
    }


def decrypt_plan(env: dict, passphrase: str) -> dict:
    try:
        if not isinstance(env, dict) or env.get("magic") != ENC_MAGIC:
            raise ValueError("Not a Vault Folio file.")
        if (env["kdf"]["name"], env["kdf"]["hash"], int(env["kdf"]["iterations"])) != (
                "PBKDF2", "SHA-256", KDF_ITERATIONS):
            raise ValueError("Unsupported encryption parameters.")
        if (env["cipher"]["name"] != "AES-256-GCM" or
                len(env) != 4):
            raise ValueError("Malformed encrypted plan.")
        salt = base64.b64decode(env["kdf"]["salt"], validate=True)
        iv = base64.b64decode(env["cipher"]["iv"], validate=True)
        ct = base64.b64decode(env["data"], validate=True)
        if len(salt) != 16 or len(iv) != 12 or not 16 <= len(ct) <= MAX_PLAN_BYTES + 16:
            raise ValueError("Malformed encrypted plan.")
    except (KeyError, TypeError, ValueError, base64.binascii.Error, OverflowError) as e:
        if isinstance(e, ValueError) and str(e) in {
                "Not a Vault Folio file.", "Unsupported encryption parameters.", "Malformed encrypted plan."}:
            raise
        raise ValueError("Malformed encrypted plan.") from e
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=KDF_ITERATIONS)
    key = kdf.derive(passphrase.encode("utf-8"))
    try:
        pt = AESGCM(key).decrypt(iv, ct, None)
    except Exception:
        raise ValueError("Wrong passphrase, or the file is corrupted.")
    if len(pt) > MAX_PLAN_BYTES:
        raise ValueError("Plan file is too large.")
    plan = json.loads(pt.decode("utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("Malformed plan document.")
    return plan


# --------------------------------------------------------------------------
# Air-gap gate — platform-aware. Checks are local only; unknown state fails closed.
# --------------------------------------------------------------------------
def _run(cmd, timeout=4.0):
    """Run a local OS inspection command; return output or None on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            return None
        return r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None


def default_route_exists():
    """True/False if the OS has a default route; None if undeterminable."""
    if PLATFORM == "Linux":
        try:
            with open("/proc/net/route") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if len(parts) > 2 and parts[1] == "00000000":
                        return True
            return False
        except OSError:
            return None
    if PLATFORM == "Darwin":
        out = _run(["route", "-n", "get", "default"])
        if out is None:
            return None
        return "gateway:" in out
    if PLATFORM == "Windows":
        out = _run(["route", "print", "-4"])
        if out is None:
            return None
        return any(line.strip().startswith("0.0.0.0") for line in out.splitlines())
    return None


def active_network_interfaces():
    """List active non-loopback links; None when the OS check is unavailable."""
    if PLATFORM == "Linux":
        active = []
        try:
            for path in glob.glob("/sys/class/net/*"):
                name = path.rsplit("/", 1)[-1]
                if name == "lo":
                    continue
                try:
                    state = open(os.path.join(path, "operstate"), encoding="ascii").read().strip()
                except OSError:
                    return None
                try:
                    carrier = open(os.path.join(path, "carrier"), encoding="ascii").read().strip() == "1"
                except FileNotFoundError:
                    carrier = False
                except OSError:
                    return None
                if state == "up" or carrier:
                    active.append(name)
            return active
        except OSError:
            return None
    if PLATFORM == "Darwin":
        names = _run(["ifconfig", "-l"])
        if names is None:
            return None
        active = []
        for name in names.split():
            if name == "lo0":
                continue
            details = _run(["ifconfig", name])
            if details is None:
                return None
            if "status: active" in details:
                active.append(name)
        return active
    if PLATFORM == "Windows":
        out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} "
                    "| Select-Object -ExpandProperty Name) -join \"`n\""] , timeout=12.0)
        return None if out is None else [line.strip() for line in out.splitlines() if line.strip()]
    return None


def wireless_interfaces():
    """(present, active) lists of wifi interfaces; (None, None) if unknown."""
    if PLATFORM == "Linux":
        present, active = [], []
        for path in glob.glob("/sys/class/net/*/wireless"):
            iface = path.split("/")[4]
            present.append(iface)
            try:
                if open(f"/sys/class/net/{iface}/operstate").read().strip() == "up":
                    active.append(iface)
            except OSError:
                pass
        return present, active
    if PLATFORM == "Darwin":
        out = _run(["networksetup", "-listallhardwareports"], timeout=6.0)
        if out is None:
            return None, None
        present, active = [], []
        port = None
        for line in out.splitlines():
            if line.startswith("Hardware Port:"):
                port = line.split(":", 1)[1].strip()
            elif line.startswith("Device:") and port:
                dev = line.split(":", 1)[1].strip()
                if "wi-fi" in port.lower() or "airport" in port.lower():
                    present.append(dev)
                    st = _run(["ifconfig", dev])
                    if st and "status: active" in st:
                        active.append(dev)
                port = None
        return present, active
    if PLATFORM == "Windows":
        out = _run(["netsh", "wlan", "show", "interfaces"], timeout=6.0)
        if out is None:
            return None, None
        if "no wireless interface" in out.lower():
            return [], []
        states = [l.lower() for l in out.splitlines() if l.strip().lower().startswith("state")]
        active = ["wireless"] if any("connected" in s and "disconnected" not in s for s in states) else []
        return ["wireless"], active
    return None, None


def bluetooth_adapters():
    """List of adapter names; None if the OS won't say."""
    if PLATFORM == "Linux":
        try:
            return os.listdir("/sys/class/bluetooth")
        except FileNotFoundError:
            return []
        except OSError:
            return None
    if PLATFORM == "Darwin":
        out = _run(["system_profiler", "SPBluetoothDataType"], timeout=10.0)
        if out is None:
            return None
        low = out.lower()
        return ["onboard bluetooth"] if ("bluetooth" in low and "controller" in low) else []
    if PLATFORM == "Windows":
        out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue "
                    "| Select-Object -ExpandProperty FriendlyName"], timeout=12.0)
        if out is None:
            return None
        return [l.strip() for l in out.splitlines() if l.strip()]
    return None


def environment_report(*, test_mode=False):
    """Return local hardware/link findings; unavailable checks fail closed."""
    wifi_present, wifi_active = wireless_interfaces()
    bt = bluetooth_adapters()
    route = default_route_exists()
    return {
        "route": route,
        "active_network": active_network_interfaces(),
        "wifi_present": wifi_present, "wifi_active": wifi_active,
        "bluetooth": bt,
        "memory": memory_report(test_only_skip_path_check=test_mode),
    }


def environment_is_safe(report, *, test_mode=False):
    """Only a complete, clean local report permits use; unknown means blocked."""
    paths_ok = (report.get("memory", {}).get("safe") is True and
                (not report.get("memory", {}).get("path_check_skipped") or test_mode))
    return (report["route"] is False and report["active_network"] == [] and
            report["wifi_present"] == [] and report["wifi_active"] == [] and
            report["bluetooth"] == [] and paths_ok)


GATE_HINT = {
    "Linux": "This edition reads wireless and Bluetooth devices from /sys, active "
             "network links, and the kernel routing table.",
    "Darwin": "This edition checks macOS hardware ports, active interfaces, and routes. "
              "Any detected Wi-Fi or Bluetooth hardware blocks use.",
    "Windows": "This edition checks Windows network adapters, routes, and radio devices. "
               "Any detected Wi-Fi or Bluetooth hardware blocks use.",
}.get(PLATFORM, "This operating system is unsupported for enforcement; the app remains locked.")


# --------------------------------------------------------------------------
# Risk engine — failure simulator for the documented setup
# --------------------------------------------------------------------------
def analyze_plan(p):
    out = []

    def add(sev, title, detail, fix=""):
        out.append({"sev": sev, "title": title, "detail": detail, "fix": fix})

    locs = {}
    all_devices, all_gen = set(), set()
    any_timelock = any_pass_memory = False
    total_keys = 0

    for vi, v in enumerate(p["vaults"]):
        vn = v.get("name") or f"Vault {vi+1}"
        if (v.get("timelock") or {}).get("enabled"):
            any_timelock = True
        expected = int(v.get("n") or 0)
        if expected and len(v.get("keys") or []) != expected:
            add("warning", f"{vn}: key count mismatch",
                f"Quorum says {v.get('m') or '?'}-of-{v.get('n')} but {len(v.get('keys') or [])} keys are documented.",
                "Document every key — heirs can only plan around what is written down.")
        for ki, k in enumerate(v.get("keys") or []):
            total_keys += 1
            kn = f"{k.get('label') or ('Key %d' % (ki+1))} ({vn})"
            if k.get("device"):
                all_devices.add(k["device"])
            if k.get("generation"):
                all_gen.add(k["generation"])
            if k.get("media") == "Hardware device only (no separate backup)":
                add("critical", f"{kn}: no backup beyond the device",
                    "Hardware wallets fail, screens break, companies disappear. A device is a signer, not a backup.",
                    "Stamp the seed words into steel (or your chosen durable medium) and store it apart from the device.")
            if k.get("passphrase") == "Memory only (dangerous)":
                any_pass_memory = True
            for loc in [s.strip() for s in (k.get("locations") or "").split(";") if s.strip()]:
                threshold = v.get("m")
                if type(threshold) is int and threshold >= 1:
                    locs.setdefault(loc.lower(), []).append({"vault": vn, "m": threshold, "kn": kn})

    for loc, holders in locs.items():
        by_vault = {}
        for h in holders:
            by_vault.setdefault(h["vault"], set()).add(h["kn"])
        for vn, keys in by_vault.items():
            m = next((h["m"] for h in holders if h["vault"] == vn), 1)
            if len(keys) >= m:
                add("critical", "One location can reach a spending quorum",
                    f"\u201c{loc}\u201d holds backups for {len(keys)} key(s) of {vn}, which needs {m}. "
                    "Fire, burglary, or one dishonest person at that site can spend.",
                    "Redistribute so no single location holds M or more keys of any vault.")

    if total_keys and len(all_devices) == 1 and any(int(v.get("n") or 1) > 1 for v in p["vaults"]):
        add("warning", "Signer monoculture",
            f"Every documented key uses the same device type ({next(iter(all_devices))}). "
            "One firmware bug or supply-chain failure reaches the whole quorum.",
            "Prefer different manufacturers across the quorum. Diversity helps — but never replaces user-supplied entropy.")
    if total_keys and all_gen == {"Device RNG (device-generated)"} and any(int(v.get("n") or 1) > 1 for v in p["vaults"]):
        add("warning", "All keys born from device RNGs",
            "The 2026 Coldcard incident showed device RNGs can silently fail; fixed firmware does not heal a weak seed.",
            "For future ceremonies, supply your own entropy (dice/coins/cards) through a verified offline calculator, "
            "and verify the derived address with a second independent program.")
    if any_pass_memory:
        add("critical", "A passphrase exists only in someone\u2019s memory",
            "If that person dies or forgets, the passphrase-protected keys are gone forever — while the backups look fine.",
            "Write it down, store it apart from the words, and give the trustee a sealed copy.")

    dlocs = p["backups"].get("descriptorLocations") or []
    needs_wallet_config = any(
        v.get("setupType") == "multi" or int(v.get("n") or 0) > 1 or
        (v.get("timelock") or {}).get("enabled")
        for v in p["vaults"]
    )
    setup_unknown = any(v.get("setupType") == "unknown" for v in p["vaults"])
    if not dlocs and needs_wallet_config:
        add("critical", "No wallet-configuration copy recorded",
            "A multisignature or timed policy can require its descriptor or configuration to rebuild the watch-only wallet and spending policy.",
            "Record tested configuration-copy locations and instructions, then rehearse a restore.")
    elif len(dlocs) == 1 and needs_wallet_config:
        add("warning", "Only one wallet-configuration copy recorded",
            "This copy may be essential to reconstruct the documented multisignature or timed policy.",
            "Record an independent copy and rehearse recovery from it.")
    elif not dlocs and setup_unknown:
        add("info", "Wallet setup is not identified",
            "The plan cannot tell whether a descriptor or wallet-configuration copy is needed for recovery.",
            "Confirm the signing setup and record the recovery material the tested procedure requires.")
    if not p["backups"].get("rescanHeight"):
        add("info", "No wallet birthday / rescan height recorded",
            "A restorer who starts from the wrong height may conclude the coins are gone.",
            "Record a block height or month/year of wallet creation with each descriptor copy.")
    if (p["backups"].get("sampleAddresses") or "").startswith("Not"):
        add("info", "No sample receiving addresses recorded",
            "2–3 known addresses let heirs verify a restore BEFORE trusting it with a spend.",
            "Note a few previously used addresses alongside the descriptor copies.")

    heirs = p["people"].get("heirs") or []
    if any(h.get("holdsKeyNow") == "Yes — intentional co-signer" for h in heirs):
        add("warning", "An heir holds a live quorum key today",
            "They can be targeted, coerced, or collude. Bitcoin checks signatures, not intentions.",
            "If intentional, document WHY. Otherwise move their key to a sealed/delayed role.")
    if not p["people"].get("helper"):
        add("info", "No Bitcoin-competent helper named",
            "A grieving family is a target for \u201cwallet support\u201d scammers.",
            "Name one, and write in the runbook that nobody legitimate will ever call or email to validate the wallet.")
    mech = p["inheritance"].get("mechanism") or ""
    if not mech or mech == "Not decided yet":
        add("warning", "Inheritance mechanism undecided",
            "The plan documents the vault but not the succession — where most inheritances fail.",
            "Choose: distributed keys via trustee, on-chain timelock decay, an assisted program, or a documented combination.")
    if any_timelock and not p["inheritance"].get("heartbeat"):
        add("critical", "Timelocked path with no refresh routine",
            "The clock applies to each coin and only resets via confirmed on-chain transactions. Miss it, and the recovery path opens while you are alive.",
            "Set an annual consolidation habit and a calendar reminder further out than one missed year.")
    if "Collaborative" in mech:
        add("info", "Assisted custody is part of the plan",
            "Providers can ease recovery, but their disappearance must not make recovery impossible.",
            "Test the exit: rehearse recovery without the provider at least once.")

    if (p["rehearsal"].get("restoreDrill") or "").startswith("Not"):
        add("critical", "Restore drill never done",
            "Nobody has proven a physical backup actually restores onto a blank signer. Untested backups are stories.",
            "Restore one key from steel, on a blank device, before calling this plan finished.")
    if (p["rehearsal"].get("familyWalkthrough") or "").startswith("Not"):
        add("warning", "Family has never walked the recovery path",
            "The plan exists only in your head until someone else can find the instructions and the map without you.",
            "Once, while everyone is calm: have the heir open the runbook and locate the descriptor unaided.")
    if (p["signing"].get("testSpend") or "").startswith("Not yet"):
        add("critical", "No test spend completed",
            "The signing procedure has never been exercised end-to-end.",
            "Send a small amount through the full cycle: build PSBT, cross the gap, sign, verify, broadcast.")
    if p["signing"].get("medium") == "USB stick (last resort)":
        add("info", "USB crosses the air gap",
            "USB is a tunnel: it carries arbitrary data both ways.",
            "Prefer QR (UR/animated) or SD where the signer supports it; dedicate the stick and decode on both sides otherwise.")

    out.extend(extra_risks(p))
    if not out:
        add("info", "No structural weaknesses detected",
            "Based on what is documented. This review checks structure, not execution.",
            "Keep the rehearsal log current.")
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda f: order[f["sev"]])


def recovery_routes(v):
    keys = [{"name": k.get("label") or f"Key {i+1}", "where": k.get("locations") or "location not documented"}
            for i, k in enumerate(v.get("keys") or [])]
    m, n = int(v.get("m") or 0), len(keys)
    if m < 1 or not n or m > n:
        return []
    # Bound work and memory even for large, imported key inventories.
    from itertools import combinations, islice
    return [list(route) for route in islice(combinations(keys, m), 10)]


def _short(value, limit):
    """Shorten untrusted plan text for compact diagram labels."""
    value = str(value or "")
    return value if len(value) <= limit else value[:max(0, limit - 1)] + "…"



# --------------------------------------------------------------------------
# Recovery-guide text, rendered inside the desktop app after decryption
# --------------------------------------------------------------------------
def build_runbook_text(p):
    L = []
    a = L.append
    a("=" * 72)
    a("INHERITANCE RUNBOOK — generated from the sealed plan file")
    a("=" * 72)
    a(f"Plan:     {p['meta'].get('planName') or '—'}")
    a(f"Owner:    {p['meta'].get('owner') or '—'}")
    a(f"Prepared: {p['meta'].get('created') or '—'}")
    a(f"Jurisdiction: {p['meta'].get('jurisdiction') or 'Not recorded'}")
    a(f"Legal notes: {p['meta'].get('legalNotes') or 'Not recorded'}")
    a("")
    a("READ FIRST — THE WARNING THAT MATTERS")
    a("-" * 72)
    a("Nobody legitimate will ever email or call you to \u201cvalidate\u201d or \u201crecover\u201d")
    a("this wallet. Anyone who does is a thief. Move slowly, verify everything,")
    a("and send a small test transaction before moving any real amount.")
    a("")
    a("1 · WHO TO CONTACT")
    a("-" * 72)
    for label, key in [("Executor / next of kin", "executor"),
                       ("Trustee (holds the map)", "trustee"),
                       ("Technical helper (holds NO keys)", "helper")]:
        if p["people"].get(key):
            a(f"  {label}: {p['people'][key]}")
    for i, h in enumerate(p["people"].get("heirs") or []):
        bits = [h.get("name"), h.get("relation"), h.get("role"), h.get("contact")]
        a(f"  Heir {i+1}: {' · '.join(b for b in bits if b)}")
    a("")
    a("2 · WHAT EXISTS")
    a("-" * 72)
    if not p["vaults"]:
        a("  No vaults documented.")
    for i, v in enumerate(p["vaults"]):
        a(f"  VAULT: {v.get('name') or ('Vault %d' % (i+1))}")
        setup_label = {"single": "Single-signature (one signing key)",
                       "multi": "Multisignature (several separate signing keys)",
                       "unknown": "Signing setup not yet identified"}.get(v.get("setupType"))
        if setup_label:
            a(f"    Signing setup: {setup_label}")
        if v.get("backupCopyArrangement"):
            copies = {"one": "One known backup location", "several": "Copies in more than one place",
                      "unsure": "Backup-copy arrangement not yet known"}.get(v["backupCopyArrangement"], "Not recorded")
            a(f"    Copies of the same key backup: {copies}")
        if v.get("tier"):
            a(f"    Purpose:     {v['tier']}")
        if v.get("m") and v.get("n"):
            a(f"    Quorum:      {v['m']}-of-{v['n']} (recorded primary rule; verify the actual policy and any delayed paths)")
        if v.get("script"):
            a(f"    Script:      {v['script']}")
        if v.get("coordinator"):
            a(f"    Coordinator: {v['coordinator']}")
        if (v.get("timelock") or {}).get("enabled"):
            a(f"    Timelock:    {v['timelock'].get('delay') or 'Yes — details not recorded'}")
        if v.get("notes"):
            a(f"    Notes:       {v['notes']}")
        for ki, k in enumerate(v.get("keys") or []):
            parts = []
            if k.get("device"):
                parts.append("Signer: " + k["device"])
            if k.get("media"):
                parts.append("Backup: " + k["media"])
            if k.get("locations"):
                parts.append("Where: " + k["locations"])
            if k.get("passphrase"):
                parts.append("Seed-passphrase backup status: " + k["passphrase"])
            a(f"    Key {ki+1} — {k.get('label') or ''}: " + "  |  ".join(parts))
        routes = recovery_routes(v)
        if routes:
            a(f"    First {len(routes)} primary-key combinations (illustrative, not an eligibility check):")
            for c in routes[:10]:
                a("      " + "  +  ".join(f"{k['name']} ({k['where']})" for k in c))
        a("")
    needs_wallet_config = any(v.get("setupType") == "multi" or int(v.get("n") or 0) > 1 or
                              (v.get("timelock") or {}).get("enabled") for v in p["vaults"])
    a("3 · WALLET CONFIGURATION & ADDRESS CHECKS")
    a("-" * 72)
    if needs_wallet_config:
        a("This setup may require its descriptor/configuration to rebuild the wallet")
        a("and spending policy. Seeds alone are NOT enough for multisig. Copies live at:")
    else:
        a("Use the tested wallet restore instructions for this setup. A configuration copy")
        a("may help; descriptors are essential for multisig and some complex policies. Copies, if recorded:")
    dlocs = p["backups"].get("descriptorLocations") or []
    if dlocs:
        for d in dlocs:
            a(f"  [ ] {d.get('where','')}" + (f" ({d.get('format')})" if d.get("format") else ""))
    else:
        a("  ⚠ Not documented — ask the trustee; check with each key backup.")
    if p["backups"].get("watchOnly"):
        a(f"  Watch-only wallet: {p['backups']['watchOnly']}")
    if p["backups"].get("rescanHeight"):
        a(f"  Rescan from:       {p['backups']['rescanHeight']}")
    if p["backups"].get("testedSoftware"):
        a(f"  Software that worked: {p['backups']['testedSoftware']}")
    if (p["backups"].get("sampleAddresses") or "").startswith("Yes"):
        a("  Verification addresses: recorded with the descriptor copies — a restored")
        a("  wallet must reproduce them.")
    a("")
    a("4 · HOW RECOVERY WORKS")
    a("-" * 72)
    a(p["inheritance"].get("mechanism") or "Not documented.")
    if p["inheritance"].get("releaseConditions"):
        a(p["inheritance"]["releaseConditions"])
    if p["inheritance"].get("letterLocation"):
        a(f"Sealed instructions: {p['inheritance']['letterLocation']}")
    if p["inheritance"].get("legalDocs"):
        a(f"Legal documents: {p['inheritance']['legalDocs']}")
    a("")
    a("5 · RECOVERY PROCEDURE")
    a("-" * 72)
    a("Generic PSBT flow — adapt to the coordinator named above. The technical")
    a("helper must verify the actual policy, eligible path and current software before starting.")
    restore_step = ("Locate a descriptor/configuration copy. Import it into the named coordinator (or a verified compatible tool) "
                    "to rebuild the watch-only wallet. Rescan from the recorded height, then check a known receiving address."
                    if needs_wallet_config else
                    "Follow the recorded wallet-specific restore instructions. If a configuration copy is listed, use a verified compatible tool. "
                    "Rescan from the recorded height and check a known receiving address.")
    steps = [
        "Gather the required number of keys for the quorum — each from its own "
        "location, ideally with the people named above. Never enter seeds into a "
        "website or give them to anyone who contacts you.",
        restore_step,
        "Create a SMALL test transaction to a destination the family fully controls. "
        "Cross to the signing device(s) by " + (p["signing"].get("medium") or "the recorded method") + ".",
        "On each signer: verify destination, amount, and fee on the device screen. "
        "If anything differs from what the coordinator showed — stop.",
        "Collect the required signatures (one signer per session; never load a quorum "
        "of seeds onto one machine), finalize, and broadcast from the online machine.",
        "Only after the test confirms on-chain: repeat for the real amounts, "
        "preferably into a fresh wallet the heirs control.",
    ]
    for i, s in enumerate(steps, 1):
        a(f"  {i}. {s}")
    rit = [label for val, label in RITUAL if val in (p["signing"].get("verifyRitual") or [])]
    if rit:
        a("")
        a("Owner's standing verification ritual:")
        for r in rit:
            a(f"  · {r}")
    a("")
    a("6 · MAINTENANCE (WHILE THE OWNER IS ALIVE)")
    a("-" * 72)
    if p["inheritance"].get("heartbeat"):
        a(f"Timelock refresh: {p['inheritance']['heartbeat']}")
    if p["inheritance"].get("canary"):
        a(f"Canary: {p['inheritance']['canary']}")
    reh = []
    if p["rehearsal"].get("restoreDrill"):
        reh.append("Restore drill: " + p["rehearsal"]["restoreDrill"])
    if p["rehearsal"].get("familyWalkthrough"):
        reh.append("Family walkthrough: " + p["rehearsal"]["familyWalkthrough"])
    if p["rehearsal"].get("testSpendDate"):
        reh.append("Last test spend: " + p["rehearsal"]["testSpendDate"])
    if reh:
        a("Rehearsal status: " + " · ".join(reh))
    if p["rehearsal"].get("notes"):
        a("Rehearsal notes: " + p["rehearsal"]["notes"])
    if p.get("ownerNotes"):
        a("")
        a("7 · OWNER'S NOTES")
        a("-" * 72)
        a(p["ownerNotes"])
    a("")
    a("— Generated by Vault Folio (offline). This runbook contains no keys.")
    a("  Untested backups are stories: rehearse before it matters.")
    for vault in p.get("vaults", []):
        for key in ("customArchitecture", "profileSource", "profileReviewed"):
            if vault.get(key):
                a(f"{vault.get('name', 'Vault')} — {key}: {vault[key]}")
    a(extra_runbook(p))
    return "\n".join(L)


# In-app Canvas diagrams
def canvas_quorum(cv, v, vi):
    keys = list(v.get("keys") or [])
    n = int(v.get("n") or len(keys) or 0)
    m = int(v.get("m") or 0)
    if n <= 0:
        return
    while len(keys) < n:
        keys.append({})
    per_row = min(n, 4)
    rows = (n + per_row - 1) // per_row
    bw, bh, gap, mx = 158, 96, 16, 20
    w = mx * 2 + per_row * bw + (per_row - 1) * gap
    h = 64 + rows * (bh + gap) - gap + 8
    cv.configure(width=w, height=h)
    title = f"VAULT {vi + 1}" + (f" — {v.get('name')}" if v.get("name") else "")
    cv.create_text(mx, 24, anchor="w", text=_short(title, 46),
                   font=("Courier", 10, "bold"), fill="#0a0a0a")
    is_single = v.get("setupType") == "single" or (m == 1 and n == 1)
    q = "SINGLE SIGNATURE" if is_single else (f"{m}-OF-{n} MULTISIG" if m else f"{n} KEYS")
    cv.create_text(w - mx, 24, anchor="e", text=q, font=("Courier", 9, "bold"), fill="#b3282d")
    if is_single:
        caption = "ONE SIGNING KEY AUTHORIZES A SPEND; COPIES ARE BACKUPS, NOT EXTRA KEYS"
    else:
        caption = f"ANY {m} OF THESE {n} KEYS MUST AGREE BEFORE A SINGLE COIN CAN MOVE" if m else "KEY DETAILS TO BE CONFIRMED"
    if is_single or m:
        cv.create_text(w / 2, 46, text=caption, font=("Courier", 7), fill="#555555")
        cv.create_line(mx, 53, w - mx, 53, fill="#0a0a0a")
    for i in range(n):
        r, c = divmod(i, per_row)
        x = mx + c * (bw + gap)
        y = 64 + r * (bh + gap)
        k = keys[i]
        documented = any(k.get(f) for f in ("label", "device", "locations"))
        cv.create_rectangle(x, y, x + bw, y + bh, fill="#ffffff", outline="#0a0a0a",
                            dash=() if documented else (4, 3))
        cv.create_text(x + 10, y + 18, anchor="w", text=f"KEY {i + 1}", font=("Courier", 7), fill="#6b6b6b")
        cv.create_text(x + 10, y + 37, anchor="w", text=_short(k.get("label") or "(undocumented)", 18),
                       font=("Courier", 9, "bold"), fill="#0a0a0a")
        if k.get("device"):
            cv.create_text(x + 10, y + 55, anchor="w", text="signs with: " + _short(k["device"], 18),
                           font=("Courier", 7), fill="#333333")
        if k.get("locations"):
            cv.create_text(x + 10, y + 71, anchor="w", text="backup: " + _short(k["locations"], 22),
                           font=("Courier", 7), fill="#2e6b4f")
        if not documented:
            cv.create_text(x + 10, y + 71, anchor="w", text="document this key in the plan",
                           font=("Courier", 7), fill="#b3282d")


def canvas_psbt_flow(cv, medium):
    w, h, wall = 700, 226, 352
    med = _short(medium or "QR codes / removable media, as recorded in the plan", 40)
    cv.configure(width=w, height=h)
    cv.create_text(24, 22, anchor="w", text="ONLINE SIDE — the everyday machine",
                   font=("Courier", 8), fill="#6b6b6b")
    cv.create_text(w - 24, 22, anchor="e", text="AIR-GAPPED SIDE — never touches a network",
                   font=("Courier", 8), fill="#6b6b6b")
    cv.create_line(wall, 12, wall, h - 34, fill="#b3282d", width=2, dash=(6, 5))
    cv.create_text(wall, h - 16, text="THE AIR GAP — only this crosses: " + med,
                   font=("Courier", 7), fill="#b3282d")

    def box(x, y, bw, bh, title, subs):
        cv.create_rectangle(x, y, x + bw, y + bh, fill="#ffffff", outline="#0a0a0a")
        cv.create_text(x + 12, y + 24, anchor="w", text=title, font=("Courier", 8, "bold"), fill="#0a0a0a")
        ty = y + 42
        for line in subs:
            cv.create_text(x + 12, ty, anchor="w", text=line, font=("Courier", 7), fill="#333333")
            ty += 13

    box(24, 44, 252, 74, "1 · WATCH-ONLY COORDINATOR",
        ["Builds the unsigned transaction (PSBT).", "Sees balances and addresses — cannot sign."])
    box(424, 44, 252, 74, "2 · SIGNING DEVICE",
        ["Check address, amount, fee on ITS screen.", "If anything differs — stop. Then sign."])
    box(24, 140, 252, 60, "4 · FINALIZE & BROADCAST",
        ["The signed PSBT returns here and is sent", "to the Bitcoin network."])
    cv.create_line(276, 81, 418, 81, fill="#0a0a0a", width=1, arrow="last")
    cv.create_text(347, 72, text="unsigned PSBT", font=("Courier", 7), fill="#0a0a0a")
    cv.create_line(550, 118, 550, 170, 282, 170, fill="#0a0a0a", width=1, arrow="last")
    cv.create_text(416, 160, text="signed PSBT — 3", font=("Courier", 7), fill="#0a0a0a")


# --------------------------------------------------------------------------
# GUI — tkinter, no browser engine anywhere
# --------------------------------------------------------------------------
INK, PAPER, PAPER2, LINE, FLAG, OK = "#0a0a0a", "#fafaf8", "#f2f1ec", "#c9c7bf", "#b3282d", "#2e6b4f"
F_SERIF = ("Georgia", 22)
F_H2 = ("Georgia", 17)
F_BODY = ("Helvetica", 11)
F_MONO = ("Courier", 10)
F_MONO_B = ("Courier", 10, "bold")


class ScrollFrame(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=PAPER, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=PAPER)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


def folio_label(parent, text):
    return tk.Label(parent, text=text.upper(), font=("Courier", 9), fg="#6b6b6b", bg=PAPER, anchor="w")


class App(tk.Tk):
    def __init__(self, *, test_mode=False):
        super().__init__()
        self.title(f"{APP_NAME} — Cold Storage Plan & Inheritance File")
        self.geometry("980x780")
        self.configure(bg=PAPER)
        self.plan = blank_plan()
        self.active_plan = None
        self.dirty = False
        self._locked = False
        self.test_mode = test_mode
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_gate()
        self.after(15_000, self._guard_tick)

    # ---- window plumbing --------------------------------------------------
    def clear(self):
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()

    def clear_session(self):
        prompt = ("Clear this test session? All entered data will be discarded and cannot be saved. "
                  "This drops app references, not a guaranteed RAM wipe." if self.test_mode else
                  "Clear this session? Save an encrypted copy first if needed. "
                  "Unsaved changes will be lost. This drops app references, not a guaranteed RAM wipe.")
        if not messagebox.askyesno(APP_NAME, prompt):
            return
        discard_plan(self.active_plan)
        self.active_plan = None
        self.dirty = False
        home_screen(self)

    def on_close(self):
        if self.dirty and not messagebox.askyesno(APP_NAME, "Unexported work will be lost. Quit anyway?"):
            return
        discard_plan(self.active_plan)
        self.active_plan = None
        self.destroy()

    def header(self, status="OFFLINE / RAM CHECKS PASSED", ok=True):
        if self.test_mode:
            status, ok = "TEST ONLY · NO PLAN FILE OPEN/SAVE · RAM PATH CHECK SKIPPED", False
        bar = tk.Frame(self, bg=PAPER, highlightthickness=1, highlightbackground=INK)
        bar.pack(fill="x")
        tk.Label(bar, text=f"{APP_NAME} · Cold Storage Plan & Inheritance File",
                 font=("Georgia", 12), bg=PAPER, fg=INK).pack(side="left", padx=16, pady=8)
        tk.Button(bar, text="CLEAR SESSION", command=self.clear_session,
                  font=("Courier", 8)).pack(side="right", padx=8)
        dot = "●" if ok else "●"
        tk.Label(bar, text=f"{dot}  {status}", font=("Courier", 9),
                 bg=PAPER, fg=(OK if ok else FLAG)).pack(side="right", padx=16)

    # ---- air-gap gate -----------------------------------------------------
    def show_gate(self):
        if self.test_mode:
            # This mode is limited to synthetic questionnaire/UI exploration.
            # It never opens files or exposes credential/export controls.
            self.lift_gate()
            return
        self.clear()
        f = tk.Frame(self, bg=INK)
        f.pack(fill="both", expand=True)
        box = tk.Frame(f, bg="#111111", highlightthickness=1, highlightbackground="#444444")
        box.place(relx=0.5, rely=0.5, anchor="center", width=660)
        tk.Label(box, text="VAULT FOLIO · AIR-GAP GATE", font=("Courier", 9),
                 fg="#8a8a84", bg="#111111").pack(anchor="w", padx=36, pady=(28, 10))
        tk.Label(box, text="Offline, nonpersistent session required.", font=("Georgia", 20),
                 fg=PAPER, bg="#111111").pack(anchor="w", padx=36)
        tk.Label(box, font=F_BODY, fg="#b9b9b4", bg="#111111", justify="left", wraplength=580,
                 text="Vault Folio handles the map to your cold storage. The app opens only when the OS reports "
                      "no default route, no active network interface, and no Wi-Fi or Bluetooth hardware. "
                      "RAM-backed system paths, disabled swap and process dump protection are also required. "
                      "An unavailable check blocks use; this is not proof against a compromised OS.").pack(
            anchor="w", padx=36, pady=(10, 16))
        self.gate_list = tk.Frame(box, bg="#111111")
        self.gate_list.pack(fill="x", padx=36)
        tk.Label(box, font=("Helvetica", 9), fg="#8a8a84", bg="#111111", justify="left", wraplength=580,
                 text="Remove Wi-Fi and Bluetooth hardware and disconnect all network cables/adapters. "
                      + GATE_HINT).pack(anchor="w", padx=36, pady=(14, 6))
        btns = tk.Frame(box, bg="#111111")
        btns.pack(anchor="w", padx=36, pady=(6, 30))
        tk.Button(btns, text="RE-CHECK ENVIRONMENT", font=F_MONO_B, bg=PAPER, fg=INK,
                  relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self.run_gate).pack(side="left")
        self.run_gate()

    def _gate_row(self, ok, text):
        color = {True: OK, False: FLAG, None: "#8a8a84"}[ok]
        mark = {True: "■ PASS", False: "■ FAIL", None: "■ BLOCKED"}[ok]
        row = tk.Frame(self.gate_list, bg="#111111")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=mark, font=F_MONO, fg=color, bg="#111111").pack(side="left")
        tk.Label(row, text=text, font=F_BODY, fg="#cfcfca", bg="#111111",
                 anchor="w", justify="left", wraplength=500).pack(side="left", padx=10)

    def run_gate(self):
        for w in self.gate_list.winfo_children():
            w.destroy()
        self._gate_row(None, "Reading local network and adapter state…")
        self.update_idletasks()
        # OS checks can take seconds on some platforms — keep the UI alive
        threading.Thread(target=lambda: self._gate_probe(environment_report(test_mode=self.test_mode)),
                         daemon=True).start()

    def _gate_probe(self, rep):
        self.after(0, lambda: self._render_gate(rep))

    def _render_gate(self, rep):
        for w in self.gate_list.winfo_children():
            w.destroy()

        route = rep["route"]
        self._gate_row(route is False, "No default route." if route is False else
                       "Default route detected or route check unavailable.")
        active = rep["active_network"]
        self._gate_row(active == [], "No active network interface." if active == [] else
                       "Active network interface detected or interface check unavailable.")
        wp = rep["wifi_present"]
        self._gate_row(wp == [], "No Wi-Fi hardware detected." if wp == [] else
                       "Wi-Fi hardware detected or check unavailable.")
        bt = rep["bluetooth"]
        self._gate_row(bt == [], "No Bluetooth hardware detected." if bt == [] else
                       "Bluetooth hardware detected or check unavailable.")

        memory = rep.get("memory", {})
        memory_status = None if memory.get("path_check_skipped") else memory.get("safe") is True
        self._gate_row(memory_status, memory.get("detail", "RAM checks unavailable."))
        safe = environment_is_safe(rep, test_mode=self.test_mode)
        if safe:
            self.lift_gate()

    def lift_gate(self):
        home_screen(self)

    # ---- mid-session guard ------------------------------------------------
    def _guard_tick(self):
        if not self._locked and not self.test_mode:
            threading.Thread(target=self._guard_probe, daemon=True).start()
        self.after(15_000, self._guard_tick)

    def _guard_probe(self):
        try:
            rep = environment_report(test_mode=self.test_mode)
            safe = environment_is_safe(rep, test_mode=self.test_mode)
        except Exception:
            safe = False
        self.after(0, lambda: self._apply_guard_result(safe))

    def _apply_guard_result(self, safe):
        if not safe and not self._locked:
            self._locked = True
            LockOverlay(self)


class LockOverlay(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.configure(bg=INK)
        self.overrideredirect(True)
        self.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}+0+0")
        self.grab_set()
        box = tk.Frame(self, bg="#111111", highlightthickness=1, highlightbackground="#444444")
        box.place(relx=0.5, rely=0.5, anchor="center", width=560)
        tk.Label(box, text="SESSION LOCKED", font=("Courier", 9), fg="#8a8a84",
                 bg="#111111").pack(anchor="w", padx=32, pady=(24, 8))
        tk.Label(box, text="Unsafe environment detected.", font=F_H2, fg=PAPER, bg="#111111").pack(anchor="w", padx=32)
        tk.Label(box, font=F_BODY, fg="#b9b9b4", bg="#111111", justify="left", wraplength=490,
                 text="A network, radio, persistent-memory risk or failed check was detected. Disable/remove it and re-check. Your unsaved plan remains in memory.").pack(anchor="w", padx=32, pady=(10, 14))
        tk.Button(box, text="RE-CHECK HARDWARE AND RESUME", font=F_MONO_B, bg=PAPER, fg=INK,
                  relief="flat", padx=16, pady=8, cursor="hand2", command=self.try_resume).pack(
            anchor="w", padx=32, pady=(0, 26))

    def try_resume(self):
        threading.Thread(target=self._check_resume_environment, daemon=True).start()

    def _check_resume_environment(self):
        try:
            rep = environment_report()
            safe = environment_is_safe(rep)
        except Exception:
            safe = False
        self.app.after(0, lambda: self._resume_result(safe))

    def _resume_result(self, safe):
        if safe:
            self.app._locked = False
            self.destroy()
        else:
            messagebox.showwarning(APP_NAME, "A network connection, radio adapter, or unavailable hardware check still blocks use.", parent=self)


# --------------------------------------------------------------------------
# Home, open-file flow, heir view
# --------------------------------------------------------------------------
def getp(obj, path):
    for k in path.split("."):
        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
    return obj if not isinstance(obj, dict) else (obj or "")


def setp(obj, path, val):
    ks = path.split(".")
    for k in ks[:-1]:
        obj = obj.setdefault(k, {})
    obj[ks[-1]] = val


def home_screen(app):
    app.clear()
    discard_plan(app.active_plan)
    app.active_plan = None
    app.dirty = False
    app.opened_format = None
    app.header()
    f = ScrollFrame(app)
    f.pack(fill="both", expand=True)
    inner = f.inner
    pad = tk.Frame(inner, bg=PAPER)
    pad.pack(fill="both", expand=True, padx=60, pady=40)

    folio_label(pad, "Registry · Cold storage succession · Local network checks active").pack(anchor="w")
    tk.Label(pad, text="The plan is the part that\nhas to survive you.", font=("Georgia", 26),
             bg=PAPER, fg=INK, justify="left").pack(anchor="w", pady=(8, 16))
    if app.test_mode:
        tk.Label(pad, text="TEST MODE — SYNTHETIC DATA ONLY. ENVIRONMENT CHECKS ARE SKIPPED. "
                 "OPENING AND SAVING PLAN FILES ARE DISABLED. Enter no real inheritance details.",
                 font=F_MONO_B, bg="#ffe0dc", fg=FLAG, justify="left", wraplength=680,
                 padx=12, pady=10).pack(fill="x", pady=(0, 14))
    tk.Label(pad, font=F_BODY, bg=PAPER, fg="#2e2e2e", justify="left", wraplength=680,
             text="Vault Folio walks you through documenting how your Bitcoin cold storage is built — "
                  "the quorum, the keys, the backups, the signing procedure, the inheritance path — then "
                  "seals it into one encrypted file. That file is the brain of the plan: family, executor, "
                  "or counsel open it years later and see exactly how to rebuild and recover what you built.").pack(anchor="w")
    tk.Label(pad, font=F_BODY, bg=PAPER, fg="#2e2e2e", justify="left", wraplength=680,
             text="It creates no keys. It signs nothing. It never asks for seed words — never enter them. "
                  "It stores the map, not the treasure.").pack(anchor="w", pady=(10, 0))

    modes = tk.Frame(pad, bg=PAPER)
    modes.pack(fill="x", pady=26)

    def mode(parent, folio, title, desc, btn, cmd, primary, enabled=True):
        fr = tk.Frame(parent, bg=PAPER, highlightthickness=1, highlightbackground=INK)
        fr.pack(side="left", fill="both", expand=True, padx=(0, 1))
        tk.Label(fr, text=folio.upper(), font=("Courier", 8), fg="#6b6b6b", bg=PAPER).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(fr, text=title, font=F_H2, bg=PAPER, fg=INK).pack(anchor="w", padx=18)
        tk.Label(fr, text=desc, font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER,
                 justify="left", wraplength=330).pack(anchor="w", padx=18, pady=(6, 12))
        tk.Button(fr, text=btn, font=F_MONO_B, relief="flat", padx=14, pady=8, cursor="hand2",
                  bg=(INK if primary else PAPER), fg=(PAPER if primary else INK),
                  highlightthickness=1, highlightbackground=INK,
                  state=("normal" if enabled else "disabled"), command=cmd).pack(
                      anchor="w", padx=18, pady=(0, 16))

    mode(modes, "Mode · 01 · Open", "Plan file opening disabled" if app.test_mode else "Open a cold storage plan file",
         "Choose a .csp / .json plan file and enter its passphrase. Owners edit and re-seal. "
         "Family, executors, and counsel get the guided recovery runbook." if not app.test_mode else
         "Opening files and entering unlock credentials are unavailable in test mode.",
         "DISABLED IN TEST MODE" if app.test_mode else "OPEN PLAN FILE (.CSP)",
         lambda: open_file_flow(app), True, enabled=not app.test_mode)
    mode(modes, "Mode · 02 · Owner", "Create a test questionnaire" if app.test_mode else "Create a new plan",
         "A short setup interview fills the plan. You then edit the full layout. "
         "It never asks for a seed or a key." if not app.test_mode else
         "Explore the questionnaire with synthetic answers. Test mode never opens or saves guide files.",
         "START TEST QUESTIONNAIRE" if app.test_mode else "START SETUP INTERVIEW",
         lambda: start_phase1(app, lambda plan: start_wizard(app, plan), lambda: home_screen(app)), False)

    tk.Label(pad, text="WHAT THE FILE CONTAINS — AND WHAT IT NEVER CONTAINS", font=F_MONO_B,
             bg=PAPER, fg=INK).pack(anchor="w", pady=(14, 6))
    rows = [("Quorum structure and script types", "Seed words / private keys"),
            ("Which signer guards each key; where backups live", "Full xpub strings (descriptor copies live with the backups)"),
            ("Descriptor-copy locations, rescan height, tested software", "Passphrases to seeds"),
            ("Inheritance mechanism, trustee, heirs, release conditions", "Street-precise hiding places"),
            ("Rehearsal log: restore drills, test spends", "Anything a thief could spend with directly")]
    for a, b in rows:
        r = tk.Frame(pad, bg=PAPER, highlightthickness=1, highlightbackground=LINE)
        r.pack(fill="x", pady=1)
        tk.Label(r, text=a, font=("Helvetica", 9), bg=PAPER, fg=INK, anchor="w",
                 wraplength=330, justify="left", width=46).pack(side="left", padx=10, pady=6)
        tk.Label(r, text=b, font=("Helvetica", 9), bg=PAPER, fg=FLAG, anchor="w",
                 wraplength=330, justify="left").pack(side="left", padx=10, pady=6)


def open_file_flow(app):
    if app.test_mode:
        messagebox.showwarning(APP_NAME, "File opening is disabled in test mode. Use synthetic questionnaire data only.")
        return
    if not environment_is_safe(environment_report(), test_mode=False):
        messagebox.showerror(APP_NAME, "Offline / RAM-session checks failed. Nothing opened.")
        return
    path = filedialog.askopenfilename(
        title="Open cold storage plan file",
        filetypes=[("Cold storage plan", "*.csp *.csp.json *.json"), ("All files", "*.*")])
    if not path:
        return
    try:
        if os.path.getsize(path) > MAX_PLAN_BYTES:
            raise ValueError("File is too large.")
        with open(path, encoding="utf-8") as f:
            env = json.load(f)
    except Exception:
        messagebox.showerror(APP_NAME, "Not a readable JSON file.")
        return
    app.opened_format = env.get("magic") if isinstance(env, dict) else None
    if isinstance(env, dict) and env.get("magic") == HARDWARE_MAGIC:
        open_hardware(app, env, lambda plan: open_choice(app, plan),
                      lambda: environment_is_safe(environment_report(), test_mode=False))
        return
    if isinstance(env, dict) and env.get("magic") == ENC_MAGIC:
        pw = simpledialog.askstring(APP_NAME, "This plan file is sealed.\nEnter its passphrase:",
                                    show="*", parent=app)
        if pw is None:
            return
        try:
            plan = decrypt_plan(env, pw)
        except ValueError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        pw = None  # drop reference
        if not environment_is_safe(environment_report(), test_mode=False):
            discard_plan(plan)
            messagebox.showerror(APP_NAME, "Environment became unsafe. Nothing opened.")
            return
        open_choice(app, plan)
    else:
        messagebox.showerror(APP_NAME, "Only encrypted Vault Folio JSON plan files can be opened.")


def open_choice(app, plan):
    try:
        plan = prepare_plan(plan, blank_plan())
    except ValueError as exc:
        messagebox.showerror(APP_NAME, str(exc))
        return
    app.active_plan = plan
    dlg = tk.Toplevel(app)
    dlg.configure(bg=PAPER)
    dlg.title(APP_NAME)
    dlg.grab_set()
    tk.Label(dlg, text="Plan opened: " + (plan["meta"].get("planName") or "untitled"),
             font=F_H2, bg=PAPER, fg=INK).pack(padx=24, pady=(20, 4), anchor="w")
    tk.Label(dlg, text="Choose how to open this guide. Viewing makes no changes; editing saves a new encrypted copy.", font=F_BODY, bg=PAPER, fg="#2e2e2e").pack(padx=24, anchor="w")
    row = tk.Frame(dlg, bg=PAPER)
    row.pack(padx=24, pady=18, anchor="w")
    tk.Button(row, text="PLAN EDITOR — UPDATE & RE-ENCRYPT", font=F_MONO_B, bg=INK, fg=PAPER, relief="flat",
              padx=12, pady=8, cursor="hand2",
              command=lambda: (dlg.destroy(), start_wizard(app, plan))).pack(side="left", padx=(0, 8))
    tk.Button(row, text="BENEFICIARY VIEW — STEP-BY-STEP GUIDE", font=F_MONO_B, bg=PAPER, fg=INK, relief="flat",
              highlightthickness=1, highlightbackground=INK, padx=12, pady=8, cursor="hand2",
              command=lambda: (dlg.destroy(), show_heir(app, plan))).pack(side="left")


def show_heir(app, plan):
    show_beneficiary(app, plan, lambda: home_screen(app), build_runbook_text)


# --------------------------------------------------------------------------
# Desktop questionnaire wizard
# --------------------------------------------------------------------------
STEP_DEFS = [
    ("start", "Read this first"),
    ("identity", "Plan & owner"),
    ("people", "Executors, trustees, heirs"),
    ("custodians", "Lawyers & backup custodians"),
    ("vaults", "Vault architecture & keys"),
    ("signing", "How spending works"),
    ("backups", "Descriptor & config backups"),
    ("inventory", "Backup inventory & hints"),
    ("paths", "Alternate recovery paths"),
    ("access", "Journal & watch-only access"),
    ("inheritance", "Inheritance mechanism"),
    ("rehearsal", "Has it been tested?"),
    ("instructions", "Family recovery steps"),
    ("review", "Risk review"),
    ("export", "Encrypt & export"),
]

STEP_INTROS = {
    "identity": "Name this plan and its owner. This document describes the structure so the right people can "
                "rebuild or recover it. It must never contain seed words, private keys, or xpubs-by-value.",
    "people": "Who must be able to act when you cannot? Separate technical assistance from financial control: "
              "a helper can guide recovery without holding any key.",
    "vaults": "Describe each wallet in ordinary language first. The guided questions branch for one-key and "
              "multisignature setups; uncertain rules stay marked unknown. Add signing-device and backup details afterward.",
    "signing": "Record how a transaction is actually signed, so a helper can reproduce it years from now. "
               "The signer is a disposable tool — the procedure is what must survive.",
    "backups": "Some setups, especially multisignature and timed policies, need a wallet configuration or output "
               "descriptor to recover correctly. Record what the tested recovery procedure requires; never type the descriptor here.",
    "inheritance": "Bitcoin cannot read a death certificate. Only two mechanisms release coins: a human holding "
                   "a missing key who agrees to use it, or a timelock that matures. Strong plans use both.",
    "rehearsal": "An untested backup is a story. This log is what turns a document into a plan. "
                 "Answer honestly — the risk review reads these.",
    "review": "The failure simulator: it reads what you documented and flags the classic ways cold-storage "
              "plans and inheritances actually die.",
}


class Wizard:
    def __init__(self, app, plan):
        self.app = app
        self.plan = ensure_sections(plan)
        self.app.active_plan = self.plan
        self.step = 0
        self.vars = {}
        self.vault_intake = None
        app.clear()
        app.header(status="PLAN EDITOR · SAVE ENCRYPTED TO KEEP CHANGES")

        shell = tk.Frame(app, bg=PAPER)
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=PAPER2, highlightthickness=1, highlightbackground=LINE)
        self.sidebar.pack(side="left", fill="y")
        for i, (_, title) in enumerate(STEP_DEFS):
            b = tk.Button(self.sidebar, text=f"{i + 1:02d}  {title}", font=("Courier", 9), anchor="w",
                          relief="flat", padx=14, pady=8, cursor="hand2", bg=PAPER2, fg="#6b6b6b",
                          activebackground=INK, activeforeground=PAPER,
                          command=lambda n=i: self.goto(n))
            b.pack(fill="x")
        self.step_buttons = list(self.sidebar.winfo_children())

        right = tk.Frame(shell, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)
        self.content = ScrollFrame(right)
        self.content.pack(fill="both", expand=True)

        nav = tk.Frame(right, bg=PAPER, highlightthickness=1, highlightbackground=LINE)
        nav.pack(fill="x")
        self.back_btn = tk.Button(nav, text="← BACK / EXIT", font=F_MONO, bg=PAPER, fg=INK, relief="flat",
                                  padx=14, pady=8, cursor="hand2", command=self.back)
        self.back_btn.pack(side="left", padx=8, pady=6)
        self.pos_lbl = tk.Label(nav, text="", font=("Courier", 9), bg=PAPER, fg="#6b6b6b")
        self.pos_lbl.pack(side="left", expand=True)
        self.next_btn = tk.Button(nav, text="CONTINUE →", font=F_MONO_B, bg=INK, fg=PAPER, relief="flat",
                                  padx=14, pady=8, cursor="hand2", command=self.forward)
        self.next_btn.pack(side="right", padx=8, pady=6)

        self.render()

    # ---- navigation -------------------------------------------------------
    def goto(self, n):
        if self.vault_intake is not None and n != self.step:
            return
        self.step = n
        self.render()

    def back(self):
        if STEP_DEFS[self.step][0] == "vaults" and self.vault_intake is not None:
            if self.vault_intake["index"] > 0:
                self.vault_intake["index"] -= 1
                self.render()
            elif messagebox.askyesno(APP_NAME, "Discard this unfinished wallet interview?"):
                self.plan["vaults"].remove(self.vault_intake["vault"])
                self.vault_intake = None
                for button in self.step_buttons:
                    button.configure(state="normal")
                self.mark_dirty()
                self.step = max(0, self.step - 1)
                self.render()
            return
        if self.step == 0:
            if not self.app.dirty or messagebox.askyesno(APP_NAME, "Leave the wizard? Unexported work will be lost."):
                home_screen(self.app)
        else:
            self.step -= 1
            self.render()

    def forward(self):
        if STEP_DEFS[self.step][0] == "vaults" and self.vault_intake is not None:
            self.advance_vault_intake()
            return
        if self.step < len(STEP_DEFS) - 1:
            self.step += 1
            self.render()
        else:
            if self.app.dirty and not messagebox.askyesno(APP_NAME, "Leave without saving your changes to an encrypted file?"):
                return
            home_screen(self.app)

    def mark_dirty(self, *_):
        self.app.dirty = True

    # ---- form helpers -----------------------------------------------------
    def _label(self, parent, text, hint=""):
        tk.Label(parent, text=text.upper(), font=("Courier", 9), fg="#2e2e2e", bg=PAPER,
                 anchor="w").pack(anchor="w", pady=(12, 2))
        if hint:
            tk.Label(parent, text=hint, font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w")

    def entry(self, parent, label, path, hint=""):
        self._label(parent, label, "")
        v = tk.StringVar(value=str(getp(self.plan, path) or ""))
        v.trace_add("write", lambda *_: (setp(self.plan, path, v.get()), self.mark_dirty()))
        tk.Entry(parent, textvariable=v, font=F_BODY, bg="#ffffff", fg=INK, relief="solid",
                 bd=1, highlightthickness=0).pack(fill="x")
        if hint:
            tk.Label(parent, text=hint, font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w", pady=(2, 0))
        return v

    def combo(self, parent, label, path, options, hint=""):
        self._label(parent, label, "")
        v = tk.StringVar(value=str(getp(self.plan, path) or ""))
        cb = ttk.Combobox(parent, textvariable=v, values=options, state="readonly", font=F_BODY)
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda *_: (setp(self.plan, path, v.get()), self.mark_dirty()))
        if hint:
            tk.Label(parent, text=hint, font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w", pady=(2, 0))
        return v

    def text(self, parent, label, path, hint=""):
        self._label(parent, label, "")
        t = tk.Text(parent, height=4, font=F_BODY, bg="#ffffff", fg=INK, relief="solid", bd=1,
                    wrap="word", highlightthickness=0)
        t.insert("1.0", str(getp(self.plan, path) or ""))
        t.pack(fill="x")

        def sync(*_):
            setp(self.plan, path, t.get("1.0", "end-1c"))
            self.mark_dirty()
        t.bind("<KeyRelease>", sync)
        if hint:
            tk.Label(parent, text=hint, font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w", pady=(2, 0))
        return t

    def checkboxes(self, parent, label, path, pairs):
        self._label(parent, label)
        cur = getp(self.plan, path) or []
        for val, lab in pairs:
            v = tk.BooleanVar(value=val in cur)

            def toggle(val=val, v=v):
                lst = getp(self.plan, path) or []
                if v.get() and val not in lst:
                    lst.append(val)
                elif not v.get() and val in lst:
                    lst.remove(val)
                setp(self.plan, path, lst)
                self.mark_dirty()
            tk.Checkbutton(parent, text=lab, variable=v, font=("Helvetica", 10), bg=PAPER, fg=INK,
                           activebackground=PAPER, selectcolor="#ffffff", anchor="w", justify="left",
                           wraplength=620, command=toggle).pack(anchor="w")

    # ---- page scaffolding -------------------------------------------------
    def page(self, title, intro=""):
        c = self.content.inner
        for w in c.winfo_children():
            w.destroy()
        for i, b in enumerate(self.step_buttons):
            b.configure(bg=(INK if i == self.step else PAPER2),
                        fg=(PAPER if i == self.step else "#6b6b6b"))
        self.pos_lbl.configure(text=f"SECTION {self.step + 1} OF {len(STEP_DEFS)}")
        self.back_btn.configure(text="← BACK / EXIT")
        self.next_btn.configure(text=("DONE" if self.step == len(STEP_DEFS)-1 else "CONTINUE →"))
        pad = tk.Frame(c, bg=PAPER)
        pad.pack(fill="both", expand=True, padx=44, pady=28)
        folio_label(pad, f"Section {self.step + 1} of {len(STEP_DEFS)}").pack(anchor="w")
        tk.Label(pad, text=title, font=F_H2, bg=PAPER, fg=INK, anchor="w").pack(anchor="w", pady=(4, 6))
        if intro:
            tk.Label(pad, text=intro, font=F_BODY, bg=PAPER, fg="#2e2e2e", justify="left",
                     wraplength=640, anchor="w").pack(anchor="w")
        tk.Frame(pad, bg=LINE, height=1).pack(fill="x", pady=14)
        tk.Label(pad,
                 text="STRUCTURE AND STORAGE LOCATIONS ONLY — never enter seed words, private keys, seed passphrases, xpubs, wallet descriptors, or full signing plans.",
                 font=("Helvetica", 9, "bold"), fg=FLAG, bg=PAPER, justify="left",
                 wraplength=640, anchor="w").pack(anchor="w", pady=(0, 10))
        return pad

    def note(self, parent, text, warn=False):
        fr = tk.Frame(parent, bg=PAPER2, highlightthickness=2,
                      highlightbackground=(FLAG if warn else INK))
        fr.pack(fill="x", pady=10)
        tk.Label(fr, text=text, font=("Helvetica", 9), bg=PAPER2, fg="#2e2e2e", justify="left",
                 wraplength=600).pack(anchor="w", padx=12, pady=10)

    def render(self):
        sid = STEP_DEFS[self.step][0]
        getattr(self, "page_" + sid)()

    # ---- folio 00 ---------------------------------------------------------
    def page_start(self):
        pad = self.page("Ground rules")
        rules = [
            "I will enter structural descriptions and storage locations only — no seeds, keys, seed passphrases, xpubs, or wallet descriptors",
            "I am using a machine with no Wi-Fi or Bluetooth hardware and no network connection",
            "I understand nothing is saved until I export the encrypted file at the end",
            "The encrypted file is a map: whoever holds it learns the STRUCTURE, but still cannot spend",
        ]
        for r in rules:
            fr = tk.Frame(pad, bg=PAPER, highlightthickness=1, highlightbackground=LINE)
            fr.pack(fill="x", pady=2)
            tk.Label(fr, text="□  " + r, font=F_BODY, bg=PAPER, fg=INK, anchor="w").pack(padx=12, pady=8, anchor="w")
        self.note(pad, "Estimated time: 30–60 minutes if your setup exists; longer if this questionnaire "
                       "reveals it is still a story. That is the point of the exercise.")
        tk.Label(pad, text="REQUIRED NONPERSISTENT SESSION", font=F_MONO_B,
                 bg=PAPER, fg=INK).pack(anchor="w", pady=(18, 6))
        hygiene = [
            "Use a trusted nonpersistent live Linux session with swap and hibernation disabled. "
            "Writable system, home and temporary paths must be RAM-backed and offline checks must pass.",
            "Copy vault-folio.py and every folio_*.py companion module together. "
            "The app saves only ciphertext, using a temporary encrypted sibling for atomic replacement.",
            "Verify first with synthetic data: python3 -B vault-folio.py --self-test",
            "Clear the session and fully shut down when finished. Neither action guarantees secure RAM erasure.",
        ]
        for h in hygiene:
            tk.Label(pad, text="·  " + h, font=("Helvetica", 9), bg=PAPER, fg="#2e2e2e",
                     anchor="w", wraplength=640, justify="left").pack(anchor="w", pady=2)

    # ---- folio 01 ---------------------------------------------------------
    def page_identity(self):
        pad = self.page("Plan & owner", STEP_INTROS["identity"])
        self.entry(pad, "Plan name", "meta.planName", "Something your executor would recognize.")
        self.entry(pad, "Owner", "meta.owner")
        self.entry(pad, "Date prepared", "meta.created")
        self.entry(pad, "Jurisdiction / legal context", "meta.jurisdiction",
                   "Country/state, and whether a will or trust references this plan. The will should point to "
                   "this file — it should never contain seeds or hiding places.")
        self.text(pad, "Legal notes (optional)", "meta.legalNotes")

    # ---- folio 02 ---------------------------------------------------------
    def page_people(self):
        pad = self.page("Executors, trustees, heirs", STEP_INTROS["people"])
        self.entry(pad, "Executor / next of kin", "people.executor",
                   "Finds the plan and starts the process. Need not be technical.")
        self.entry(pad, "Trustee / guardian of the map", "people.trustee",
                   "Ideally holds the location map and (optionally) one delayed/recovery key, sealed — never a live quorum.")
        self.entry(pad, "Bitcoin-competent helper", "people.helper",
                   "A technical person who holds NO keys. If they hold no key, their compromise cannot spend.")

        tk.Label(pad, text="HEIRS / BENEFICIARIES", font=F_MONO_B, bg=PAPER, fg=INK).pack(anchor="w", pady=(22, 6))
        self.heirs_box = tk.Frame(pad, bg=PAPER)
        self.heirs_box.pack(fill="x")
        self.draw_heirs()
        tk.Button(pad, text="+ ADD AN HEIR", font=F_MONO, bg=PAPER, fg=INK, relief="solid", bd=1,
                  cursor="hand2", command=self.add_heir).pack(anchor="w", pady=8)

    def draw_heirs(self):
        for w in self.heirs_box.winfo_children():
            w.destroy()
        heirs = self.plan["people"]["heirs"]
        for i, h in enumerate(heirs):
            fr = tk.LabelFrame(self.heirs_box, text=f"  HEIR {i+1}  ", font=F_MONO, bg="#ffffff",
                               fg=INK, relief="solid", bd=1)
            fr.pack(fill="x", pady=4)
            inner = tk.Frame(fr, bg="#ffffff")
            inner.pack(fill="x", padx=10, pady=8)

            def row(lbl, key, opts=None, hint=""):
                tk.Label(inner, text=lbl.upper(), font=("Courier", 8), bg="#ffffff", fg="#6b6b6b",
                         anchor="w").pack(anchor="w")
                if opts:
                    v = tk.StringVar(value=h.get(key, ""))
                    cb = ttk.Combobox(inner, textvariable=v, values=opts, state="readonly", font=("Helvetica", 10))
                    cb.pack(fill="x")
                    cb.bind("<<ComboboxSelected>>", lambda *_: (h.__setitem__(key, v.get()), self.mark_dirty()))
                else:
                    v = tk.StringVar(value=h.get(key, ""))
                    v.trace_add("write", lambda *_: (h.__setitem__(key, v.get()), self.mark_dirty()))
                    tk.Entry(inner, textvariable=v, font=("Helvetica", 10), relief="solid", bd=1).pack(fill="x")
                if hint:
                    tk.Label(inner, text=hint, font=("Helvetica", 8), bg="#ffffff", fg="#6b6b6b",
                             anchor="w", wraplength=560, justify="left").pack(anchor="w")

            row("Name", "name")
            row("Relationship", "relation")
            row("Role in recovery", "role", hint="e.g. holds delayed-path key B (sealed, with attorney)")
            row("Do they hold any spending-capable key today?", "holdsKeyNow",
                ["No", "Yes — intentional co-signer", "Yes — inheritance key, not usable yet"],
                hint="The default answer should be No. An heir holding a live key now can be targeted or coerced.")
            row("How they are reached / found", "contact")
            tk.Button(fr, text="REMOVE", font=("Courier", 8), bg="#ffffff", fg=FLAG, relief="flat",
                      cursor="hand2", command=lambda i=i: self.del_heir(i)).pack(anchor="e", padx=10, pady=(0, 8))

    def add_heir(self):
        self.plan["people"]["heirs"].append({})
        self.mark_dirty()
        self.draw_heirs()

    def del_heir(self, i):
        self.plan["people"]["heirs"].pop(i)
        self.mark_dirty()
        self.draw_heirs()

    def record_page(self, title, section):
        pad = self.page(title,
                        "Add as many records as needed. Use recognizable aliases and clues; exact locations are optional. "
                        "Use hints by default. Optional direct access details belong only in the dedicated access section. "
                        "Never enter Bitcoin seed words or private keys.")
        if section == "backupRecords":
            self.note(pad, "SLIP39 shares and Seed XOR parts reconstruct ONE signing key; they are not multisig signers. "
                           "Keep the separate location clues needed to find this encrypted package outside it too.")
        if section == "accessRecords":
            self.note(pad, "Choose hints or optional direct access details for journals, watch-only wallets and documents. "
                           "Direct credentials appear in the decrypted heir guide. Never use these fields for Bitcoin seeds, "
                           "private keys or wallet seed passphrases. Switching to hint-only removes a previously entered direct credential.")
        if section == "lawyers":
            self.note(pad, "Record agreed access and release instructions, not assumed legal powers. "
                           "Opening the package does not authorize spending bitcoin.")
        container = tk.Frame(pad, bg=PAPER)
        container.pack(fill="x")
        rows = self.plan[section]
        def redraw():
            for widget in container.winfo_children():
                widget.destroy()
            for i, record in enumerate(rows):
                frame = ttk.LabelFrame(container, text=f"Record {i + 1}")
                frame.pack(fill="x", pady=8)
                fields = record_fields(section, record)
                for key, label, options in fields:
                    tk.Label(frame, text=label, anchor="w", wraplength=580).pack(anchor="w", padx=8, pady=(6, 0))
                    value = tk.StringVar(value=record.get(key, ""))
                    def update(*_, row=record, name=key, var=value):
                        row[name] = var.get()
                        if name == "mode" and var.get() != "Direct access details inside encrypted guide":
                            row.pop("directAccess", None)
                        self.mark_dirty()
                    value.trace_add("write", update)
                    widget = ttk.Combobox(frame, textvariable=value, values=options) if options else ttk.Entry(frame, textvariable=value)
                    widget.pack(fill="x", padx=8)
                    if key == "directAccess":
                        widget.configure(show="*")
                    # Hold Tk variable alive for the lifetime of the field.
                    widget._folio_variable = value
                    if key in ("scheme", "kind", "mode"):
                        widget.bind("<<ComboboxSelected>>", lambda *_: redraw())
                def remove(index=i):
                    if messagebox.askyesno(APP_NAME, "Remove this record?", parent=self.app):
                        rows.pop(index)
                        self.mark_dirty()
                        redraw()
                ttk.Button(frame, text="Remove record", command=remove).pack(anchor="w", padx=8, pady=8)
        def add():
            rows.append({"mode": "Hint only"} if section == "accessRecords" else {})
            self.mark_dirty()
            redraw()
        redraw()
        ttk.Button(pad, text="+ Add another record", command=add).pack(anchor="w", pady=10)

    def page_custodians(self):
        self.record_page("Lawyers, trustees & backup custodians", "lawyers")

    def page_inventory(self):
        self.record_page("Backup inventory & family location hints", "backupRecords")

    def page_instructions(self):
        self.record_page("Your step-by-step instructions for family", "instructions")

    def page_access(self):
        self.record_page("EntropyLab journal, watch-only wallet & access instructions", "accessRecords")

    def page_paths(self):
        self.record_page("Alternate recovery paths & dependencies", "recoveryPaths")

    # ---- folio 03: vaults (nested keys) -----------------------------------
    def page_vaults(self):
        pad = self.page("Vault architecture & keys", STEP_INTROS["vaults"])
        if self.vault_intake is not None:
            self.render_vault_intake(pad)
            return
        if not self.plan["vaults"]:
            self.begin_vault_intake()
            return
        self.note(pad, "Rule: never record seed words, xprvs, or full xpub strings here. A key entry describes "
                       "WHICH key it is, WHAT signs with it, and WHERE its backups live — nothing that can spend.")
        self.note(pad, "Start with a guided interview. It asks one question at a time, explains unfamiliar terms, "
                       "and adds a draft wallet section as you answer. You can inspect and edit the full folio afterward. "
                       "Choose “I’m not sure” whenever needed; the app will not guess your wallet rules.")
        self.vaults_box = tk.Frame(pad, bg=PAPER)
        self.vaults_box.pack(fill="x")
        self.draw_vaults()
        tk.Button(pad, text="+ ADD A VAULT", font=F_MONO, bg=PAPER, fg=INK, relief="solid", bd=1,
                  cursor="hand2", command=self.begin_vault_intake).pack(anchor="w", pady=10)

    def begin_vault_intake(self):
        vault = {"intakeId": uuid.uuid4().hex,
                 "name": "New wallet setup", "m": "", "n": "", "script": "Not sure yet",
                 "coordinator": "", "timelock": {"enabled": False, "delay": ""}, "keys": [],
                 "intakeAnswers": {}}
        self.plan["vaults"].append(vault)
        self.vault_intake = {"vault": vault, "answers": vault["intakeAnswers"], "index": 0}
        for i, button in enumerate(self.step_buttons):
            button.configure(state=("normal" if i == self.step else "disabled"))
        self.mark_dirty()
        self.render()

    def vault_intake_questions(self):
        a = self.vault_intake["answers"]
        questions = [
            ("structure", "How is this wallet set up?",
             "This means how many separate signing keys are needed to spend. Several copies of one backup are still one key.",
             "choice", [("single", "One key can authorize a spend (single-signature)"),
                        ("multi", "Several separate keys are required (multisignature)"),
                        ("unsure", "I’m not sure")]),
        ]
        structure = a.get("structure")
        if structure == "unsure":
            questions.append(("structure_detail", "Do you know whether one key or several keys are required?",
                              "If you cannot tell from your wallet setup, choose “I’m not sure.”", "choice",
                              [("single", "One key"), ("multi", "Several keys together"),
                               ("unsure", "I’m not sure")]))
        resolved = a.get("structure_detail") if structure == "unsure" else structure
        questions.append(("name", "What name would help your family recognize this wallet?",
                          "For example, “Household savings.” You can change it later.", "text", None))
        if resolved == "single":
            questions.append(("backup_copies", "Are copies of this key’s backup kept in more than one place?",
                              "These are copies of the same key, not additional signing keys.", "choice",
                              [("one", "No, one known copy"), ("several", "Yes, more than one place"),
                               ("unsure", "I’m not sure")]))
        elif resolved == "multi":
            questions.extend([
                ("n", "How many separate signing keys are there?",
                 "Count distinct keys, not backup copies. Enter a number from 2 to 100, or choose “I’m not sure.”", "number", None),
                ("m", "How many of those keys must work together to spend?",
                 "This is the threshold, often written as “2 of 3.” Enter the number needed, or choose “I’m not sure.”", "number", None),
            ])
        questions.extend([
            ("coordinator", "Which app or service do you use to view or coordinate this wallet?",
             "This is the watch-only or coordinating software, not a signing key. Choose “I’m not sure” if the name is unfamiliar.",
             "choice", [(x, x) for x in COORDS] + [("Other / undecided", "I’m not sure")]),
            ("delayed_path", "Does the wallet have another spending route that becomes available after a delay?",
             "This might be written into the Bitcoin wallet policy, or arranged through a provider. A date written in this guide does not lock bitcoin.",
             "choice", [("yes", "Yes"), ("no", "No"), ("unsure", "I’m not sure")]),
        ])
        if a.get("delayed_path") == "yes":
            questions.append(("delayed_kind", "What controls that delayed route?",
                              "Choose the closest description. If unknown, the folio will leave it for later clarification.", "choice",
                              [("onchain", "A delay built into the Bitcoin wallet policy"),
                               ("provider", "A provider, trustee, or other person releases access"),
                               ("unsure", "I’m not sure")]))
            if a.get("delayed_kind") == "onchain":
                questions.append(("delay", "What delay and starting event are documented?",
                                  "For example, “12 months after the last wallet activity.” Leave blank if unknown. Do not treat this as a verified policy.", "text", None))
        return questions

    def render_vault_intake(self, pad):
        questions = self.vault_intake_questions()
        idx = min(self.vault_intake["index"], len(questions) - 1)
        key, title, help_text, kind, options = questions[idx]
        self.pos_lbl.configure(text=f"WALLET QUESTION {idx + 1} OF {len(questions)}")
        self.back_btn.configure(text=("← PREVIOUS QUESTION" if idx else "← CANCEL WALLET"))
        self.next_btn.configure(text=("ADD WALLET TO PLAN →" if idx == len(questions) - 1 else "NEXT QUESTION →"))
        card = tk.Frame(pad, bg="#ffffff", highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="x", pady=(8, 12))
        tk.Label(card, text=f"QUESTION {idx + 1} OF {len(questions)}", font=F_MONO_B,
                 bg="#ffffff", fg=OK).pack(anchor="w", padx=20, pady=(18, 8))
        bar = tk.Frame(card, bg=LINE, height=5)
        bar.pack(fill="x", padx=20, pady=(0, 14))
        tk.Frame(bar, bg=OK).place(relx=0, rely=0, relwidth=(idx + 1) / len(questions), relheight=1)
        tk.Label(card, text=title, font=F_H2, bg="#ffffff", fg=INK, anchor="w", justify="left",
                 wraplength=640).pack(anchor="w", padx=20, pady=(2, 8))
        tk.Label(card, text=help_text, font=F_BODY, bg="#ffffff", fg="#2e2e2e", anchor="w", justify="left",
                 wraplength=640).pack(anchor="w", padx=20, pady=(0, 18))
        self.intake_value = tk.StringVar(value=str(self.vault_intake["answers"].get(key, "")))
        if kind == "choice":
            for value, label in options:
                tk.Radiobutton(card, text=label, value=value, variable=self.intake_value,
                               font=F_BODY, bg="#ffffff", activebackground="#ffffff", selectcolor=PAPER2,
                               anchor="w", justify="left", wraplength=620).pack(anchor="w", padx=20, pady=6)
        else:
            answer_entry = tk.Entry(card, textvariable=self.intake_value, font=F_BODY, bg="#ffffff", fg=INK,
                                    relief="solid", bd=1)
            answer_entry.pack(fill="x", padx=20, pady=(0, 8))
            answer_entry.bind("<Return>", lambda _event: (self.advance_vault_intake(), "break")[1])
            if kind == "number":
                tk.Radiobutton(card, text="I’m not sure", value="unsure", variable=self.intake_value,
                               font=F_BODY, bg="#ffffff", activebackground="#ffffff", selectcolor=PAPER2,
                               anchor="w").pack(anchor="w", padx=20, pady=(0, 16))
        vault = self.vault_intake["vault"]
        summary = tk.LabelFrame(pad, text="  YOUR WALLET SUMMARY  ", font=F_MONO,
                                bg="#ffffff", fg=INK, relief="solid", bd=1)
        summary.pack(fill="x", pady=(22, 4))
        setup_label = {"single": "Single-signature", "multi": "Multisignature",
                       "unknown": "Not identified yet"}.get(vault.get("setupType"), "Waiting for your answer")
        quorum = (f"{vault['m']}-of-{vault['n']}" if vault.get("m") and vault.get("n")
                  else ("Threshold not known yet" if vault.get("setupType") == "multi" else "Not applicable yet"))
        for line in (f"Name: {vault.get('name') or 'Not named yet'}",
                     f"Signing setup: {setup_label}", f"Required keys: {quorum}",
                     f"Wallet app/service: {vault.get('coordinator') or 'Not answered yet'}"):
            tk.Label(summary, text=line, font=F_BODY, bg="#ffffff", fg=INK,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w", padx=12, pady=3)
        tk.Label(pad, text="DRAFT FOLIO BUILDS IN MEMORY AS YOU ANSWER · NOTHING IS SAVED YET",
                 font=("Courier", 8), bg=PAPER, fg="#6b6b6b").pack(anchor="w", pady=(24, 0))

    def advance_vault_intake(self):
        questions = self.vault_intake_questions()
        idx = self.vault_intake["index"]
        key, _title, _help, kind, _options = questions[idx]
        answer = self.intake_value.get().strip()
        if kind == "choice" and not answer:
            messagebox.showinfo(APP_NAME, "Choose an answer, including “I’m not sure.”")
            return
        if kind == "number" and answer != "unsure":
            minimum = 2 if key == "n" else 1
            if not answer.isdigit() or not minimum <= int(answer) <= 100:
                messagebox.showinfo(APP_NAME, f"Enter a whole number from {minimum} to 100, or choose “I’m not sure.”")
                return
            answer = int(answer)
        if key in ("m", "n"):
            n = self.vault_intake["answers"].get("n")
            m = self.vault_intake["answers"].get("m")
            if key == "m" and isinstance(n, int) and isinstance(answer, int) and answer > n:
                messagebox.showinfo(APP_NAME, "The required key count cannot exceed the total key count.")
                return
            if key == "n" and isinstance(m, int) and isinstance(answer, int) and m > answer:
                messagebox.showinfo(APP_NAME, "The total key count cannot be less than the required key count.")
                return
        answers = self.vault_intake["answers"]
        old_value = answers.get(key)
        answers[key] = answer
        vault = self.vault_intake["vault"]
        resolved = answers.get("structure_detail") if answers.get("structure") == "unsure" else answers.get("structure")
        if key == "structure" and old_value != answer:
            for stale in ("structure_detail", "backup_copies", "n", "m", "structure_unknown"):
                answers.pop(stale, None)
        elif key == "structure_detail" and old_value != answer:
            for stale in ("backup_copies", "n", "m", "structure_unknown"):
                answers.pop(stale, None)
        elif key == "delayed_path" and old_value != answer:
            answers.pop("delayed_kind", None)
            answers.pop("delay", None)
        elif key == "delayed_kind" and old_value != answer:
            answers.pop("delay", None)
        vault["name"] = answers.get("name") or "New wallet setup"
        vault["coordinator"] = answers.get("coordinator", "")
        vault["intakeAnswers"] = answers
        resolved = resolved if resolved in ("single", "multi") else "unknown"
        vault["setupType"] = resolved
        if resolved == "single":
            vault.update({"m": 1, "n": 1, "script": "Single-signature (one key)"})
            if not vault.get("keys"):
                vault["keys"] = [{"label": "Key A"}]
            if "backup_copies" in answers:
                vault["backupCopyArrangement"] = answers["backup_copies"]
        elif resolved == "multi":
            vault.pop("backupCopyArrangement", None)
            vault["n"] = answers.get("n") if isinstance(answers.get("n"), int) else ""
            vault["m"] = answers.get("m") if isinstance(answers.get("m"), int) else ""
            vault["script"] = "Not sure yet"
            count = answers.get("n")
            if isinstance(count, int):
                old_keys = vault.get("keys", [])
                vault["keys"] = (old_keys + [{"label": f"Key {i + 1}"} for i in range(len(old_keys), count)])[:count]
            else:
                vault["keys"] = []
        else:
            vault.pop("backupCopyArrangement", None)
            vault["m"], vault["n"], vault["script"] = "", "", "Not sure yet"
            vault["keys"] = []
        delayed = answers.get("delayed_path")
        delayed_kind = answers.get("delayed_kind")
        vault["timelock"] = {"enabled": delayed == "yes" and delayed_kind == "onchain",
                              "delay": answers.get("delay", "")}
        self.mark_dirty()
        if idx + 1 >= len(self.vault_intake_questions()):
            if answers.get("delayed_path") == "yes":
                mechanism = {"provider": "Provider-enforced off-chain delay",
                             "onchain": "Bitcoin on-chain relative timelock"}.get(answers.get("delayed_kind"))
                path = {"label": f"{vault['name']} delayed route", "vault": vault["name"],
                        "sourceVaultId": vault["intakeId"]}
                if mechanism:
                    path["mechanism"] = mechanism
                    if answers.get("delay"):
                        path["delay"] = answers["delay"]
                else:
                    path["mechanism"] = "Other / custom"
                    path["dependencies"] = (
                        "A delayed spending route was reported, but its mechanism is unknown. "
                        "Confirm whether it is on-chain or provider-controlled. This guide does not enforce a release date.")
                self.plan["recoveryPaths"].append(path)
            self.vault_intake = None
            for button in self.step_buttons:
                button.configure(state="normal")
            self.render()
        else:
            self.vault_intake["index"] = idx + 1
            self.render()

    def draw_vaults(self):
        for w in self.vaults_box.winfo_children():
            w.destroy()
        for vi, v in enumerate(self.plan["vaults"]):
            self.draw_vault(self.vaults_box, v, vi)

    def draw_vault(self, parent, v, vi):
        title = f"  VAULT {vi+1}" + (f" — {v['name']}" if v.get("name") else "") + \
                (f"  ·  {v['m']}-of-{v['n']}" if v.get("m") and v.get("n") else "")
        fr = tk.LabelFrame(parent, text=title, font=F_MONO, bg="#ffffff", fg=INK, relief="solid", bd=1)
        fr.pack(fill="x", pady=6)
        inner = tk.Frame(fr, bg="#ffffff")
        inner.pack(fill="x", padx=12, pady=10)

        def row(lbl, key, opts=None, hint="", obj=None):
            obj = obj if obj is not None else v
            tk.Label(inner, text=lbl.upper(), font=("Courier", 8), bg="#ffffff", fg="#6b6b6b",
                     anchor="w").pack(anchor="w", pady=(8, 0))
            if opts:
                var = tk.StringVar(value=obj.get(key, ""))
                cb = ttk.Combobox(inner, textvariable=var, values=opts, state="readonly", font=("Helvetica", 10))
                cb.pack(fill="x")
                cb.bind("<<ComboboxSelected>>", lambda *_: (obj.__setitem__(key, var.get()),
                                                            self.mark_dirty(), self._maybe_redraw_vault(key)))
            else:
                var = tk.StringVar(value=str(obj.get(key, "")))
                var.trace_add("write", lambda *_: (obj.__setitem__(key, var.get()), self.mark_dirty()))
                tk.Entry(inner, textvariable=var, font=("Helvetica", 10), relief="solid", bd=1).pack(fill="x")
            if hint:
                tk.Label(inner, text=hint, font=("Helvetica", 8), bg="#ffffff", fg="#6b6b6b",
                         anchor="w", wraplength=580, justify="left").pack(anchor="w")

        row("Vault name", "name")
        row("Preset source / guide revision (optional)", "profileSource")
        row("Custom architecture / provider details", "customArchitecture")
        row("Purpose / tier", "tier", TIERS,
            "Theft-resistance and inheritance want opposite shapes. A small timelocked family pile plus a "
            "larger no-timelock deep vault beats one script trying to do both.")

        qrow = tk.Frame(inner, bg="#ffffff")
        tk.Label(inner, text="QUORUM  (M of N)", font=("Courier", 8), bg="#ffffff", fg="#6b6b6b",
                 anchor="w").pack(anchor="w", pady=(8, 0))
        qrow.pack(fill="x")
        vm = tk.StringVar(value=str(v.get("m", "")))
        vn = tk.StringVar(value=str(v.get("n", "")))
        vm.trace_add("write", lambda *_: (v.__setitem__("m", int(vm.get()) if vm.get().isdigit() else ""), self.mark_dirty()))
        vn.trace_add("write", lambda *_: (v.__setitem__("n", int(vn.get()) if vn.get().isdigit() else ""), self.mark_dirty()))
        tk.Entry(qrow, textvariable=vm, width=5, font=("Helvetica", 10), relief="solid", bd=1).pack(side="left")
        tk.Label(qrow, text=" OF ", font=F_MONO, bg="#ffffff").pack(side="left")
        tk.Entry(qrow, textvariable=vn, width=5, font=("Helvetica", 10), relief="solid", bd=1).pack(side="left")
        tk.Label(inner, text="2-of-3 if a normal family must operate it. 3-of-5 when losing one site must not "
                             "matter. 3-of-7 is the loss-extreme — and a poor inheritance experience.",
                 font=("Helvetica", 8), bg="#ffffff", fg="#6b6b6b", anchor="w", wraplength=580,
                 justify="left").pack(anchor="w")

        row("Script type", "script", SCRIPTS)
        row("Coordinator software", "coordinator", COORDS,
            "The coordinator builds transactions and holds the watch-only wallet. It must be replaceable.")

        tk.Label(inner, text="TIMELOCKED RECOVERY PATH?", font=("Courier", 8), bg="#ffffff",
                 fg="#6b6b6b", anchor="w").pack(anchor="w", pady=(8, 0))
        tl = v.get("timelock") or {}
        tlv = tk.StringVar(value=("yes" if tl.get("enabled") else ("no" if v.get("timelock") else "")))
        trow = tk.Frame(inner, bg="#ffffff")
        trow.pack(fill="x")
        for val, lab in [("no", "No timelock"), ("yes", "Has timelock")]:
            tk.Radiobutton(trow, text=lab, value=val, variable=tlv, font=("Helvetica", 10),
                           bg="#ffffff", activebackground="#ffffff", selectcolor="#ffffff",
                           command=lambda: self._set_timelock(v, tlv.get())).pack(side="left", padx=(0, 16))
        if tl.get("enabled"):
            tk.Label(inner, text="TIMELOCK DETAILS", font=("Courier", 8), bg="#ffffff",
                     fg="#6b6b6b", anchor="w").pack(anchor="w", pady=(6, 0))
            dv = tk.StringVar(value=tl.get("delay", ""))
            dv.trace_add("write", lambda *_: (tl.__setitem__("delay", dv.get()), self.mark_dirty()))
            tk.Entry(inner, textvariable=dv, font=("Helvetica", 10), relief="solid", bd=1).pack(fill="x")
            tk.Label(inner, text="Prefer relative timelocks (OP_CSV): \u201cif these coins sit still, something is "
                                 "wrong.\u201d Absolute dates open on the date even if you are actively spending.",
                     font=("Helvetica", 8), bg="#ffffff", fg="#6b6b6b", anchor="w", wraplength=580,
                     justify="left").pack(anchor="w")

        row("Notes", "notes", hint="Do not mix personal, trust, and business coins under one descriptor. "
                                   "Legal ownership should match who can sign.")

        # nested keys
        kf = tk.Frame(fr, bg="#ffffff")
        kf.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(kf, text=f"KEYS IN THIS VAULT ({len(v.get('keys') or [])}"
                          + (f" of {v['n']} expected" if v.get("n") else "") + ")",
                 font=F_MONO_B, bg="#ffffff", fg=INK, anchor="w").pack(anchor="w", pady=(4, 4))
        for ki, k in enumerate(v.get("keys") or []):
            self.draw_key(kf, k, ki, v)
        tk.Button(kf, text="+ ADD A KEY", font=("Courier", 9), bg="#ffffff", fg=INK, relief="solid", bd=1,
                  cursor="hand2",
                  command=lambda: (v.setdefault("keys", []).append({}), self.mark_dirty(),
                                   self.draw_vaults())).pack(anchor="w", pady=6)
        tk.Button(fr, text="REMOVE VAULT", font=("Courier", 8), bg="#ffffff", fg=FLAG, relief="flat",
                  cursor="hand2", command=lambda i=vi: self.remove_vault(i)).pack(anchor="e", padx=10, pady=(0, 8))

    def remove_vault(self, index):
        vault = self.plan["vaults"][index]
        if not messagebox.askyesno(APP_NAME, f"Remove {vault.get('name') or 'this wallet'} and its linked intake-created recovery path?",
                                   parent=self.app):
            return
        source_id = vault.get("intakeId")
        self.plan["vaults"].pop(index)
        if source_id:
            self.plan["recoveryPaths"] = [row for row in self.plan["recoveryPaths"]
                                           if row.get("sourceVaultId") != source_id]
        self.mark_dirty()
        self.draw_vaults()

    def _set_timelock(self, v, val):
        v["timelock"] = {"enabled": val == "yes", "delay": (v.get("timelock") or {}).get("delay", "")}
        self.mark_dirty()
        self.draw_vaults()

    def _maybe_redraw_vault(self, key):
        if key == "device":
            self.draw_vaults()

    def draw_key(self, parent, k, ki, vault):
        fr = tk.LabelFrame(parent, text=f"  KEY {ki+1}" + (f" — {k['label']}" if k.get("label") else ""),
                           font=("Courier", 9), bg=PAPER, fg=INK, relief="solid", bd=1)
        fr.pack(fill="x", pady=4)
        inner = tk.Frame(fr, bg=PAPER)
        inner.pack(fill="x", padx=10, pady=6)

        def row(lbl, key, opts=None, hint=""):
            tk.Label(inner, text=lbl.upper(), font=("Courier", 8), bg=PAPER, fg="#6b6b6b",
                     anchor="w").pack(anchor="w", pady=(6, 0))
            if opts:
                var = tk.StringVar(value=k.get(key, ""))
                cb = ttk.Combobox(inner, textvariable=var, values=opts, state="readonly", font=("Helvetica", 10))
                cb.pack(fill="x")
                cb.bind("<<ComboboxSelected>>", lambda *_: (k.__setitem__(key, var.get()), self.mark_dirty(),
                                                            self._maybe_redraw_vault(key)))
            else:
                var = tk.StringVar(value=k.get(key, ""))
                var.trace_add("write", lambda *_: (k.__setitem__(key, var.get()), self.mark_dirty()))
                tk.Entry(inner, textvariable=var, font=("Helvetica", 10), relief="solid", bd=1).pack(fill="x")
            if hint:
                tk.Label(inner, text=hint, font=("Helvetica", 8), bg=PAPER, fg=("#b3282d" if hint.startswith("⚠") else "#6b6b6b"),
                         anchor="w", wraplength=540, justify="left").pack(anchor="w")

        row("Label", "label", hint="e.g. Key A — home signer")
        dev_hint = ""
        if k.get("device") == "COLDCARD (see warning)":
            dev_hint = "⚠ After the 2026 entropy incident, do not generate NEW seeds on this brand; only import user-supplied (dice) entropy, or prefer another signer."
        row("Signing device", "device", DEVICES, dev_hint)
        row("How this key was generated", "generation", GENMETHODS,
            "Best practice: each key gets its OWN ceremony — its own boot, its own dice. Seven keys from one "
            "RNG in one sitting share one failure.")
        row("Backup medium", "media", MEDIA,
            "Steel is the canonical backup for words. Paper alone is not. Discs are a good extra and a bad only.")
        row("Backup location(s)", "locations",
            hint="Separate multiple locations with semicolons. Two copies of key A are still only key A — do not "
                 "\u201cback up\u201d your way into a spendable set in one building.")
        row("Seed-passphrase backup status (never enter the passphrase)", "passphrase", PASSPHRASE,
            "Choose only where it is stored. Never type seed words or the actual seed passphrase into this tool.")
        tk.Button(fr, text="REMOVE", font=("Courier", 8), bg=PAPER, fg=FLAG, relief="flat", cursor="hand2",
                  command=lambda: (vault["keys"].pop(ki), self.mark_dirty(),
                                   self.draw_vaults())).pack(anchor="e", padx=10, pady=(0, 6))

    # ---- folio 04 ---------------------------------------------------------
    def page_signing(self):
        pad = self.page("How spending works", STEP_INTROS["signing"])
        self.combo(pad, "How does the unsigned PSBT cross the air gap?", "signing.medium",
                   ["QR codes (UR / animated)", "SD card", "USB stick (last resort)", "Not decided"],
                   "QR is slower than a cable — that is the point. USB is a tunnel.")
        self.checkboxes(pad, "Verification ritual — which checks are part of every spend?",
                        "signing.verifyRitual", RITUAL)
        self.combo(pad, "Has a full test spend been completed with this setup?", "signing.testSpend",
                   ["Yes — small amount, full cycle, verified", "Yes — but not since last software upgrade",
                    "Not yet (plan incomplete until done)"],
                   "A test spend is part of the setup, not a demonstration.")
        self.text(pad, "Signing procedure notes", "signing.coordinatorNotes")

    # ---- folio 05 ---------------------------------------------------------
    def page_backups(self):
        pad = self.page("Descriptor & configuration backups", STEP_INTROS["backups"])
        tk.Label(pad, text="DESCRIPTOR / WALLET-CONFIGURATION COPIES", font=F_MONO_B, bg=PAPER, fg=INK).pack(anchor="w")
        tk.Label(pad, text="For multisignature and timed policies, this copy may be essential to rebuild the wallet. "
                           "For a simple single-key setup, follow its tested restore instructions and record any "
                           "configuration copies that are actually needed.", font=("Helvetica", 9), fg="#6b6b6b",
                 bg=PAPER, wraplength=620, justify="left").pack(anchor="w", pady=(2, 8))
        self.dloc_box = tk.Frame(pad, bg=PAPER)
        self.dloc_box.pack(fill="x")
        self.draw_dlocs()
        tk.Button(pad, text="+ ADD A COPY LOCATION", font=F_MONO, bg=PAPER, fg=INK, relief="solid", bd=1,
                  cursor="hand2",
                  command=lambda: (self.plan["backups"]["descriptorLocations"].append({}),
                                   self.mark_dirty(), self.draw_dlocs())).pack(anchor="w", pady=8)
        self.entry(pad, "Watch-only setup", "backups.watchOnly",
                   "Where the family can SEE the coins without being able to move them.")
        self.entry(pad, "Wallet birthday / rescan height", "backups.rescanHeight",
                   "A wrong birthday that skips the deposit block is how people decide the coins are gone. "
                   "\u201cStart at genesis\u201d is acceptable and slow.")
        self.combo(pad, "Have 2–3 previously used receiving addresses been recorded somewhere safe?",
                   "backups.sampleAddresses",
                   ["Yes — recorded with the descriptor copies", "Not yet"],
                   "They let a recovery be verified before any real spend.")
        self.entry(pad, "Software + versions that successfully signed a test transaction",
                   "backups.testedSoftware")

    def draw_dlocs(self):
        for w in self.dloc_box.winfo_children():
            w.destroy()
        for i, d in enumerate(self.plan["backups"]["descriptorLocations"]):
            fr = tk.Frame(self.dloc_box, bg="#ffffff", highlightthickness=1, highlightbackground=LINE)
            fr.pack(fill="x", pady=2)
            tk.Label(fr, text="WHERE", font=("Courier", 8), bg="#ffffff", fg="#6b6b6b").grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))
            v1 = tk.StringVar(value=d.get("where", ""))
            v1.trace_add("write", lambda *_: (d.__setitem__("where", v1.get()), self.mark_dirty()))
            tk.Entry(fr, textvariable=v1, font=("Helvetica", 10), relief="solid", bd=1).grid(row=1, column=0, sticky="ew", padx=8)
            tk.Label(fr, text="FORMAT", font=("Courier", 8), bg="#ffffff", fg="#6b6b6b").grid(row=0, column=1, sticky="w", padx=8, pady=(6, 0))
            v2 = tk.StringVar(value=d.get("format", ""))
            cb = ttk.Combobox(fr, textvariable=v2, font=("Helvetica", 10), state="readonly",
                              values=["Printed paper", "Plaintext digital file", "Encrypted digital file",
                                      "Wallet descriptor export (BSMS / Core / Sparrow)"], width=26)
            cb.grid(row=1, column=1, sticky="ew", padx=8)
            cb.bind("<<ComboboxSelected>>", lambda *_: (d.__setitem__("format", v2.get()), self.mark_dirty()))
            tk.Button(fr, text="✕", font=("Courier", 9), bg="#ffffff", fg=FLAG, relief="flat", cursor="hand2",
                      command=lambda i=i: (self.plan["backups"]["descriptorLocations"].pop(i),
                                           self.mark_dirty(), self.draw_dlocs())).grid(row=1, column=2, padx=8)
            fr.columnconfigure(0, weight=3)
            fr.columnconfigure(1, weight=2)

    # ---- folio 06 ---------------------------------------------------------
    def page_inheritance(self):
        pad = self.page("Inheritance mechanism", STEP_INTROS["inheritance"])
        self.combo(pad, "Primary inheritance mechanism", "inheritance.mechanism", MECHANISMS)
        self.text(pad, "Release conditions — when and how heirs gain access", "inheritance.releaseConditions",
                  "e.g. Trustee releases sealed key B on presentation of death certificate; timelocked path "
                  "opens after 18 months of inactivity on the family vault…")
        self.entry(pad, "If timelocks are used — the refresh routine", "inheritance.heartbeat",
                   "The timer resets when coins move to yourself under the same policy. Put the reminder further "
                   "out than one missed year.")
        self.entry(pad, "Legal documents referencing this plan", "inheritance.legalDocs",
                   "The will names that instructions exist and who holds them — never the seeds.")
        self.entry(pad, "Where the sealed instruction letter lives", "inheritance.letterLocation")
        self.text(pad, "Canary / liveness signal (optional)", "inheritance.canary",
                  "e.g. one small watched UTXO on the family descriptor; if it moves, someone is spending that "
                  "policy. An alarm, not a dead-man switch.")

    # ---- folio 07 ---------------------------------------------------------
    def page_rehearsal(self):
        pad = self.page("Has it actually been tested?", STEP_INTROS["rehearsal"])
        self.combo(pad, "Restore drill: one key restored from its physical backup onto a blank signer?",
                   "rehearsal.restoreDrill", YESNO3)
        self.combo(pad, "Family walkthrough: has the spouse/heir opened these instructions and found the "
                        "descriptor without your help?", "rehearsal.familyWalkthrough",
                   ["Yes — they found everything unaided", "They know the plan exists", "Not yet"])
        self.entry(pad, "Date of last full test spend", "rehearsal.testSpendDate")
        self.text(pad, "Rehearsal notes / what went wrong and was fixed", "rehearsal.notes")

    # ---- folio 08: review -------------------------------------------------
    def page_review(self):
        pad = self.page("Risk review", STEP_INTROS["review"])
        findings = analyze_plan(self.plan)
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in findings:
            counts[f["sev"]] += 1
        tk.Label(pad, text=f"{counts['critical']} CRITICAL · {counts['warning']} WARNINGS · {counts['info']} NOTES",
                 font=F_MONO_B, bg=PAPER, fg=INK).pack(anchor="w", pady=(0, 10))
        colors = {"critical": FLAG, "warning": "#8a6408", "info": "#6b6b6b"}
        for f in findings:
            fr = tk.Frame(pad, bg="#ffffff", highlightthickness=2, highlightbackground=colors[f["sev"]])
            fr.pack(fill="x", pady=3)
            tk.Label(fr, text=f["sev"].upper(), font=("Courier", 8, "bold"), bg="#ffffff",
                     fg=colors[f["sev"]]).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(fr, text=f["title"], font=("Helvetica", 11, "bold"), bg="#ffffff", fg=INK,
                     anchor="w", wraplength=600, justify="left").pack(anchor="w", padx=12)
            body = f["detail"] + (("\n→ " + f["fix"]) if f["fix"] else "")
            tk.Label(fr, text=body, font=("Helvetica", 9), bg="#ffffff", fg="#2e2e2e", anchor="w",
                     wraplength=600, justify="left").pack(anchor="w", padx=12, pady=(2, 10))
        self.text(pad, "Owner notes (encrypted with the plan)", "ownerNotes")

    # ---- folio 09: export -------------------------------------------------
    def page_export(self):
        pad = self.page("Encrypt & export the inheritance file")
        if self.app.test_mode:
            tk.Label(pad, text="TEST MODE — EXPORT DISABLED", font=F_MONO_B,
                     bg="#ffe0dc", fg=FLAG, padx=12, pady=10).pack(anchor="w", fill="x", pady=12)
            tk.Label(pad, text="This run skips all environment checks. Do not enter real plan "
                     "details. Opening files, entering unlock credentials, using YubiKeys, and saving are disabled. "
                     "Close the app to discard synthetic test answers; this is not guaranteed RAM erasure.",
                     font=F_BODY, bg=PAPER, fg=INK, justify="left", wraplength=620).pack(anchor="w", pady=8)
            return
        self.note(pad, "Choose any independent unlock methods for this guide. Give a passphrase or enrolled YubiKey "
                       "to your lawyer if desired. Keep the program, encrypted file, and non-secret discovery instructions "
                       "where family can find them. Release conditions are instructions, not a software-enforced time lock.")
        add_export_controls(pad, self.app, self.plan,
                            lambda: environment_is_safe(environment_report()))

        # --- preview: the pictures the family will see ---------------------
        if self.plan["vaults"]:
            tk.Label(pad, text="SETUP DIAGRAM PREVIEW · CHECK THIS AGAINST YOUR WALLET", font=F_MONO_B,
                     bg=PAPER, fg=INK).pack(anchor="w", pady=(20, 6))
            for vi, v in enumerate(self.plan["vaults"]):
                cv = tk.Canvas(pad, bg=PAPER, highlightthickness=0)
                canvas_quorum(cv, v, vi)
                cv.pack(anchor="w", pady=(0, 10))
            cv2 = tk.Canvas(pad, bg=PAPER, highlightthickness=0)
            canvas_psbt_flow(cv2, self.plan["signing"].get("medium"))
            cv2.pack(anchor="w", pady=(0, 6))

        tk.Label(pad, text="WHERE COPIES OF THE ENCRYPTED FILE SHOULD LIVE", font=F_MONO_B,
                 bg=PAPER, fg=INK).pack(anchor="w", pady=(20, 6))
        for item in ["With the trustee / executor (they also need to know the passphrase exists, and who holds it)",
                     "With the attorney, attached to the estate documents",
                     "On the watch-only machine, next to the descriptor copies",
                     "In at least one geographically separate location"]:
            tk.Label(pad, text="□  " + item, font=F_BODY, bg=PAPER, fg=INK, anchor="w").pack(anchor="w", pady=2)
        tk.Label(pad, text="To update the plan later: reopen this app, open your encrypted file, edit, and "
                           "export a fresh sealed copy. Saving briefly creates an encrypted temporary sibling "
                           "beside the chosen file for atomic replacement.",
                 font=("Helvetica", 9), fg="#6b6b6b", bg=PAPER, justify="left", wraplength=620).pack(anchor="w", pady=14)


def start_wizard(app, plan):
    Wizard(app, plan)


# --------------------------------------------------------------------------
def self_test():
    """Headless verification: crypto roundtrip, tamper detection, risk engine."""
    plan = blank_plan()
    plan["meta"]["planName"] = "Self Test"
    plan["vaults"] = [{"name": "T", "m": 2, "n": 3, "keys": [
        {"label": "A", "device": "SeedSigner (stateless QR)",
         "generation": "Dice / coins / cards + offline calculator (EntropyLab)",
         "media": "Steel / metal plate", "locations": "home safe",
         "passphrase": "Stored at a separate site"},
        {"label": "B", "device": "Jade (stateless mode)",
         "generation": "Dice / coins / cards + offline calculator (EntropyLab)",
         "media": "Steel / metal plate", "locations": "bank box",
         "passphrase": "None — explicit record of that"},
        {"label": "C", "device": "BitBox02-class (secure element)",
         "generation": "Device RNG (device-generated)",
         "media": "Steel / metal plate", "locations": "trustee",
         "passphrase": "None — explicit record of that"}]}]
    env = encrypt_plan(plan, "correct horse battery staple")
    assert env["magic"] == ENC_MAGIC
    back = decrypt_plan(env, "correct horse battery staple")
    assert back["meta"]["planName"] == "Self Test"
    try:
        decrypt_plan(env, "wrong passphrase")
        raise SystemExit("SELF-TEST FAILED: wrong passphrase was accepted")
    except ValueError:
        pass
    tampered = json.loads(json.dumps(env))
    tampered["data"] = tampered["data"][:-4] + "AAAA"
    try:
        decrypt_plan(tampered, "correct horse battery staple")
        raise SystemExit("SELF-TEST FAILED: tampered ciphertext was accepted")
    except ValueError:
        pass
    assert len(recovery_routes(plan["vaults"][0])) == 3  # 2-of-3 -> C(3,2)
    analyze_plan(plan)  # must not raise
    rb = build_runbook_text(plan)
    assert "READ FIRST" in rb
    print("Vault Folio self-test: OK")
    print("  crypto:  AES-256-GCM + PBKDF2-SHA-256(600k) roundtrip, wrong-key and tamper rejected")
    print("  logic:   risk engine, recovery routes, text runbook (GUI diagrams are not exercised here)")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    harden_process()  # RAM gate blocks if this cannot be established.
    test_mode = "--test-only-synthetic-questionnaire" in sys.argv
    app = App(test_mode=test_mode)
    app.mainloop()


if __name__ == "__main__":
    main()
