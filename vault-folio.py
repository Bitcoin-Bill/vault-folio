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
          python3 vault-folio.py --ubuntu-test   (installed Ubuntu: skip the air-gap lock, full encrypted save)
          python3 vault-folio.py --self-test   (headless crypto/risk check)
"""

import base64
import copy
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

import folio_ui as ui
import folio_theme as themes
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
from folio_security import reseal_preserving_methods
from folio_storage import save_encrypted
from folio_synthetic import TEST_MARKER, load_synthetic_plan, save_synthetic_plan

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


def disable_networking():
    """Ask the OS to drop networking. Returns a short result line."""
    if PLATFORM != "Linux":
        return "This button only turns networking off on Linux."
    nm = _run(["nmcli", "networking", "off"], timeout=8.0)
    if default_route_exists() is True:
        _run(["pkexec", "ip", "route", "del", "default"], timeout=30.0)
    if default_route_exists() is False:
        return "Networking is off and the default route is gone. Checking again."
    if nm is None:
        return "Could not turn networking off. The route is still there."
    return "Asked NetworkManager to stop. The route is still there."


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
    if p.get("amendments"):
        a("")
        a("NOTES ADDED ON TOP OF THE SAVED GUIDE")
        a("-" * 72)
        for i, note in enumerate(p["amendments"], 1):
            a(f"  {i}. {note}")
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
# Scale-aware card layout shared by the canvas diagrams: text is wrapped with
# real font metrics and card heights measured from the (possibly scaled)
# fonts, so text never spills its card. Canvas text items must NOT use the
# width= option — Tk reserves phantom vertical space for it.
from tkinter import font as _tkfont

def _font_obj(cv, font):
    """Cached tkfont.Font for measuring. Cache lives on the root so it dies
    with its interpreter (tests create and destroy many roots)."""
    root = cv._root()
    cache = getattr(root, "_folio_font_obj_cache", None)
    if cache is None:
        cache = root._folio_font_obj_cache = {}
    if font not in cache:
        styles = set(str(extra) for extra in font[2:])
        cache[font] = _tkfont.Font(
            root=root, family=font[0], size=font[1],
            weight=("bold" if "bold" in styles else "normal"),
            slant=("italic" if "italic" in styles else "roman"),
            underline=bool("underline" in styles),
            overstrike=bool("overstrike" in styles))
    return cache[font]


def _font_px(font):
    try:
        return abs(int(font[1]))
    except (IndexError, TypeError, ValueError):
        return 10


def _line_height(cv, font):
    return _font_obj(cv, font).metrics("linespace")


def _wrap_exact(cv, text, font, pixel_width):
    """Wrap text to a pixel width using measured glyph widths."""
    measure = _font_obj(cv, font).measure
    words = str(text or "Not recorded").split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if line and measure(candidate) > pixel_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\n".join(lines or ["Not recorded"]), max(1, len(lines))


def draw_card(cv, x, y, w, rows, *, outline=None, dash=(), tag=None,
              pad_top=14, row_gap=8, pad_bottom=14):
    """Draw a card whose height fits its scaled, wrapped text. Returns new y."""
    outline = INK if outline is None else outline
    measured = []
    height = pad_top + pad_bottom
    for text, font, fill in rows:
        wrapped, count = _wrap_exact(cv, text, font, w - 28)
        measured.append((wrapped, font, fill, count))
        height += count * _line_height(cv, font) + row_gap
    height -= row_gap
    tags = (tag,) if tag else ()
    cv.create_rectangle(x, y, x + w, y + height, fill=WHITE, outline=outline,
                        dash=dash, tags=tags)
    ty = y + pad_top
    for wrapped, font, fill, count in measured:
        cv.create_text(x + 14, ty, anchor="nw", text=wrapped,
                       font=font, fill=fill, tags=tags)
        ty += count * _line_height(cv, font) + row_gap
    return y + height


def canvas_quorum(cv, v, vi):
    """Readable, wrapped signer cards sized for the app's large interface scale."""
    keys = list(v.get("keys") or [])
    try:
        n = int(v.get("n") or len(keys) or 0)
        m = int(v.get("m") or 0)
    except (TypeError, ValueError):
        n, m = len(keys), 0
    if n <= 0:
        return
    n = min(n, 30)
    while len(keys) < n:
        keys.append({})
    width, x, cardw = 760, 18, 724
    title_font = themes.F("Courier", 10, "bold")
    body_font = themes.F("Helvetica", 10)
    title = f"VAULT {vi + 1}" + (f" — {v.get('name')}" if v.get("name") else "")
    q = "SINGLE SIGNATURE" if (v.get("setupType") == "single" or (m == 1 and n == 1)) else (f"{m}-OF-{n} MULTISIG" if m else f"{n} KEYS")
    caption = ("ONE SIGNING KEY AUTHORIZES A SPEND; COPIES ARE BACKUPS, NOT EXTRA KEYS"
               if q == "SINGLE SIGNATURE" else
               (f"ANY {m} OF THESE {n} KEYS MUST AGREE BEFORE A SINGLE COIN CAN MOVE" if m else "KEY DETAILS TO BE CONFIRMED"))
    y = 16
    cv.delete("all")
    title_wrapped, title_lines = _wrap_exact(cv, title, title_font, cardw)
    q_wrapped, q_lines = _wrap_exact(cv, q, title_font, cardw)
    cap, cap_lines = _wrap_exact(cv, caption, body_font, cardw)
    cv.create_text(x, y, anchor="nw", text=title_wrapped, font=title_font, fill=INK)
    y += title_lines * _line_height(cv, title_font)
    cv.create_text(x, y, anchor="nw", text=q_wrapped, font=title_font, fill=FLAG)
    y += q_lines * _line_height(cv, title_font)
    cv.create_text(x, y, anchor="nw", text=cap, font=body_font, fill=DIM)
    y += cap_lines * _line_height(cv, body_font) + 6
    cv.create_line(x, y, width - x, y, fill=INK)
    y += 12
    for i, key in enumerate(keys[:n]):
        documented = any(key.get(f) for f in ("label", "device", "locations"))
        rows = [(f"KEY {i + 1} · {key.get('label') or '(undocumented)'}", title_font, INK)]
        if key.get("device"):
            rows.append(("Signs with: " + str(key["device"]), body_font, INK_SOFT))
        if key.get("locations"):
            rows.append(("Backup place: " + str(key["locations"]), body_font, OK))
        if not documented:
            rows.append(("Document this key in the plan", body_font, FLAG))
        y = draw_card(cv, x, y, cardw, rows, dash=() if documented else (4, 3)) + 10
    cv.configure(width=width, height=min(y + 8, 680), scrollregion=(0, 0, width, y + 8))


def canvas_family_map(cv, plan):
    """One-column clickable map for setup, signers, people, and numbered steps."""
    people = plan.get("people") or {}
    vault = (plan.get("vaults") or [{}])[0]
    keys = list(vault.get("keys") or [])
    try:
        n = int(vault.get("n") or len(keys) or 1)
    except (TypeError, ValueError):
        n = len(keys) or 1
    n = max(1, min(n, 30))
    m = vault.get("m") or ""
    while len(keys) < n:
        keys.append({})

    def backup_details(key):
        """Read holder and location details from inventory records for this signer."""
        key_label = str(key.get("label") or "").strip()
        vault_name = str(vault.get("name") or "").strip()
        aliases = {value.casefold() for value in (
            key_label,
            f"{vault_name} / {key_label}" if vault_name and key_label else "",
            f"{vault_name}: {key_label}" if vault_name and key_label else "",
        ) if value}
        related = []
        for record in plan.get("backupRecords") or []:
            ref = str(record.get("vault") or "").strip().casefold()
            record_label = str(record.get("label") or "").strip().casefold()
            padded = " " + record_label.replace("/", " ").replace(":", " ").replace("-", " ") + " "
            has_label = bool(key_label and (" " + key_label.casefold() + " ") in padded)
            if ref in aliases or record_label in aliases or (vault_name and ref == vault_name.casefold() and has_label):
                related.append(record)
        holders, places = [], [str(key.get("locations") or "").strip()]
        for record in related:
            for candidate in (record.get("custodian"), record.get("locator")):
                candidate = str(candidate or "").strip()
                if candidate and candidate.casefold() not in {h.casefold() for h in holders}:
                    holders.append(candidate)
            location = str(record.get("location") or "").strip()
            if location and location.casefold() not in {p.casefold() for p in places}:
                places.append(location)
        return ("; ".join(holders) or "Not recorded",
                "; ".join(value for value in places if value) or "Not recorded")

    width, x, cardw = 760, 18, 724
    y = 16
    cv.delete("all")
    clickable = []

    rule = f"{m}-of-{n}" if m else (vault.get("setupType") or f"{n} keys")
    y = draw_card(cv, x, y, cardw, [
        ("SETUP · " + str(vault.get("name") or "Unnamed setup"), themes.F("Courier", 11, "bold"), INK),
        (str(rule).upper() + " · click a card", themes.F("Courier", 9, "bold"), FLAG),
    ], tag="setup") + 12
    clickable.append("setup")
    cv.tag_bind("setup", "<Button-1>", lambda _e, v=vault: show_tree_detail("This setup", [
        ("Name", v.get("name") or "Unnamed setup"), ("Rule", rule),
        ("Type", v.get("setupType") or "Not recorded"),
        ("Delay", (v.get("timelock") or {}).get("delay") or "None recorded")]))

    for i, key in enumerate(keys[:n]):
        holder, place = backup_details(key)
        tag = f"key{i}"
        documented = any(key.get(f) for f in ("label", "device", "locations"))
        y = draw_card(cv, x, y, cardw, [
            (f"KEY {i + 1} · {key.get('label') or 'Not named'}", themes.F("Courier", 10, "bold"), INK),
            ("Holder: " + holder, themes.F("Helvetica", 10), INK),
            ("Place: " + place, themes.F("Helvetica", 10), OK),
        ], dash=() if documented else (4, 3), tag=tag) + 10
        clickable.append(tag)
        cv.tag_bind(tag, "<Button-1>", lambda _e, k=key, ix=i, h=holder, p=place: show_tree_detail(
            f"Key {ix + 1}", [("Label", k.get("label") or "Not named"), ("Holder", h),
                              ("Place", p), ("Device", k.get("device") or "Not recorded")]))

    people_cards = [("FIRST CONTACT", people.get("executor") or "Not named"),
                    ("INSTRUCTIONS HOLDER", people.get("trustee") or "Not named")]
    heirs = [str(row.get("name") or "").strip() for row in people.get("heirs") or []]
    people_cards.extend(("HEIR", name) for name in heirs if name)
    if not any(heirs):
        people_cards.append(("HEIR", "Not named"))
    lawyers = [str(row.get("name") or row.get("firm") or "").strip() for row in plan.get("lawyers") or []]
    people_cards.extend(("LAWYER", name) for name in lawyers if name)
    if not any(lawyers):
        people_cards.append(("LAWYER", "Not named"))

    cv.create_text(x, y + 12, anchor="w", text="PEOPLE",
                   font=themes.F("Courier", 10, "bold"), fill=HINT)
    y += 28
    for i, (label, value) in enumerate(people_cards):
        tag = f"person{i}"
        y = draw_card(cv, x, y, cardw, [
            (label + ": " + str(value or "Not named"), themes.F("Helvetica", 10, "bold"), INK),
        ], tag=tag) + 8
        clickable.append(tag)
        cv.tag_bind(tag, "<Button-1>", lambda _e, title=label, who=value: show_tree_detail(title, [("Name", who)]))

    cv.create_text(x, y + 12, anchor="w", text="NUMBERED GUIDE STEPS",
                   font=themes.F("Courier", 10, "bold"), fill=HINT)
    y += 28
    for number, title, detail in heir_steps_for(plan):
        y = draw_card(cv, x, y, cardw, [
            (f"{number} · {title}", themes.F("Courier", 9, "bold"), INK),
            (detail, themes.F("Helvetica", 9), INK),
        ], outline=LINE) + 8

    cv.configure(width=width, height=min(680, max(400, y + 16)), bg=PAPER,
                 highlightthickness=0, scrollregion=(0, 0, width, y + 16))
    for tag in clickable:
        cv.tag_bind(tag, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind(tag, "<Leave>", lambda _e: cv.configure(cursor=""))
    return y + 16


def heir_steps_for(plan):
    """Build concise heir steps from names and locations already in the guide."""
    people = plan.get("people") or {}
    vault = (plan.get("vaults") or [{}])[0]
    contact = people.get("executor") or "the first contact named in the guide"
    where = (plan.get("inheritance") or {}).get("letterLocation") or "the place named for the sealed guide"
    rule = f"{vault.get('m')} of {vault.get('n')}" if vault.get("m") and vault.get("n") else (vault.get("setupType") or "the recorded rule")
    vault_name = str(vault.get("name") or "").strip()
    if vault_name:
        rule = f"{vault_name}: {rule}"
    keys = vault.get("keys") or []
    labels = [str(key.get("label") or "").strip() for key in keys]
    labels = [label for label in labels if label]
    places = [str(key.get("locations") or "").strip() for key in keys]
    places = [place for place in places if place]
    named_keys = ", ".join(labels) or "the signer labels in the guide"
    named_places = ", ".join(dict.fromkeys(places)) or "the places named on each key"
    return [
        ("1", "Read this first", "This guide has no seed and cannot spend bitcoin."),
        ("2", "Contact " + contact, "Use a route the family already knows."),
        ("3", "Find the guide", where),
        ("4", "Follow " + str(rule), "Required signer labels: " + named_keys + ". Copies of one key still count as one key."),
        ("5", "Collect backups", "Use the recorded locations: " + named_places + ". Do not gather every secret on one computer."),
    ]


def show_tree_detail(title, rows):
    window = tk.Toplevel()
    window.title(title)
    window.configure(bg=PAPER)
    tk.Label(window, text=title, font=themes.F("Georgia", 18), bg=PAPER, fg=INK).pack(anchor="w", padx=18, pady=(16, 8))
    for label, value in rows:
        tk.Label(window, text=label, font=themes.F("Courier", 9), fg=HINT, bg=PAPER).pack(anchor="w", padx=18)
        tk.Label(window, text=value, font=themes.F("Helvetica", 13), bg=PAPER, fg=INK, wraplength=420, justify="left").pack(anchor="w", padx=18, pady=(0, 8))
    tk.Label(window, text="This is a location and role note. It is not a seed.", font=themes.F("Courier", 9),
             fg=FLAG, bg=PAPER).pack(anchor="w", padx=18, pady=(4, 8))
    ui.btn_primary(window, "CLOSE", window.destroy).pack(anchor="e", padx=18, pady=(0, 16))
    ui.center_window(window, window.master)


def canvas_psbt_flow(cv, medium):
    """Large, vertically ordered signing flow with room for scaled text."""
    w, wall = 900, 450
    med = str(medium or "QR codes / removable media, as recorded in the plan")
    head_font = themes.F("Courier", 9, "bold")
    body_font = themes.F("Helvetica", 10)
    gap_font = themes.F("Courier", 9)
    cv.delete("all")
    cv.create_text(24, 20, anchor="w", text="ONLINE SIDE — the everyday machine",
                   font=head_font, fill=HINT)
    cv.create_text(w - 24, 20, anchor="e", text="AIR-GAPPED SIDE — never touches a network",
                   font=head_font, fill=HINT)
    boxes = [
        (24, "1 · WATCH-ONLY COORDINATOR",
         "Builds the unsigned transaction. Sees balances and addresses; cannot sign."),
        (484, "2 · SIGNING DEVICE",
         "Check address, amount, and fee on its screen. Stop if anything differs."),
    ]
    row1_bottom = 0
    for bx, title, detail in boxes:
        row1_bottom = max(row1_bottom, draw_card(cv, bx, 58, 392, [
            (title, head_font, INK), (detail, body_font, INK_SOFT)]))
    y3 = row1_bottom + 36
    row3_bottom = draw_card(cv, 24, y3, 392, [
        ("4 · FINALIZE & BROADCAST", head_font, INK),
        ("The signed transaction returns here and is sent to the Bitcoin network.",
         body_font, INK_SOFT)])
    mid = 58 + (row1_bottom - 58) // 2
    cv.create_line(424, mid, 476, mid, fill=INK, width=2, arrow="last")
    cv.create_text(450, mid - 16, text="unsigned PSBT", font=themes.F("Courier", 8), fill=INK)
    gap_text, gap_lines = _wrap_exact(cv, "THE AIR GAP — only this crosses: " + med,
                                      gap_font, w - 48)
    gap_y = row3_bottom + 30
    cv.create_line(wall, 42, wall, gap_y - 8, fill=FLAG, width=2, dash=(6, 5))
    cv.create_text(24, gap_y, anchor="nw", text=gap_text, font=gap_font, fill=FLAG)
    signed = [(680, row1_bottom), (680, row1_bottom + 18), (440, row1_bottom + 18),
              (440, y3 + 18), (424, y3 + 18)]
    cv.create_line(*signed, fill=INK, width=2, arrow="last")
    cv.create_text(555, row1_bottom + 8, text="signed PSBT · 3", font=themes.F("Courier", 8), fill=INK)
    height = gap_y + gap_lines * _line_height(cv, gap_font) + 16
    cv.configure(width=w, height=height, bg=PAPER, scrollregion=(0, 0, w, height))


# --------------------------------------------------------------------------
# GUI — tkinter, no browser engine anywhere
# --------------------------------------------------------------------------
INK, PAPER, PAPER2, LINE, FLAG, OK = "#0a0a0a", "#fafaf8", "#f2f1ec", "#c9c7bf", "#b3282d", "#2e6b4f"
F_SERIF = ("Georgia", 22)
F_H2 = ("Georgia", 17)
F_BODY = ("Helvetica", 11)
F_MONO = ("Courier", 10)
F_MONO_B = ("Courier", 10, "bold")
themes.install(globals())   # after the font constants so scale bases are captured
themes.install(ui.__dict__)


class ScrollFrame(ui.ScrollFrame):
    """Kept for existing screens. Wheel routing lives in folio_ui."""


def folio_label(parent, text):
    return tk.Label(parent, text=text.upper(), font=themes.F("Courier", 9), fg=HINT, bg=PAPER, anchor="w")


class App(tk.Tk):
    def __init__(self, *, test_mode=False, ubuntu_test=False):
        super().__init__()
        self.title(f"{APP_NAME} — Cold Storage Plan & Inheritance File")
        self.geometry("1280x900")
        self.minsize(1100, 760)
        self.configure(bg=PAPER)
        try:
            self.tk.call("tk", "scaling", 1.8)
        except tk.TclError:
            pass
        ui.init_style(self)
        ui.install_scrolling(self)
        self.plan = blank_plan()
        self.active_plan = None
        self.dirty = False
        self._locked = False
        self.test_mode = test_mode
        self.guide_path = None    # file the open guide came from
        self.guide_env = None     # original envelope (public parts)
        self.guide_dek = None     # data key from the open; lets notes re-seal losslessly
        self.saved_snapshot = None  # copy of the plan as last saved; cleared with the session
        self.ubuntu_test = ubuntu_test
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_gate()
        self.after(15_000, self._guard_tick)

    # ---- window plumbing --------------------------------------------------
    def clear(self):
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()

    def clear_session(self):
        prompt = ("Clear this synthetic test session? Unsaved answers will be discarded. Any saved test file "
                  "remains at its chosen destination. This drops app references, not a guaranteed RAM wipe." if self.test_mode else
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
            status, ok = "TEST ONLY · SYNTHETIC FILES · ENVIRONMENT CHECKS SKIPPED", False
        elif self.ubuntu_test:
            status, ok = "UBUNTU TEST · AIR-GAP LOCK SKIPPED · NOT AN OFFLINE SESSION", False
        bar = tk.Frame(self, bg=PAPER, highlightthickness=1, highlightbackground=INK)
        bar.pack(fill="x")
        tk.Label(bar, text=f"{APP_NAME} · Cold Storage Plan & Inheritance File",
                 font=themes.F("Georgia", 12), bg=PAPER, fg=INK).pack(side="left", padx=16, pady=8)
        tk.Button(bar, text="CLEAR SESSION", command=self.clear_session,
                  font=themes.F("Courier", 8)).pack(side="right", padx=8)
        tk.Button(bar, text="SETTINGS", command=lambda: themes.open_settings(self),
                  font=themes.F("Courier", 8)).pack(side="right", padx=8)
        dot = "●" if ok else "●"
        tk.Label(bar, text=f"{dot}  {status}", font=themes.F("Courier", 9),
                 bg=PAPER, fg=(OK if ok else FLAG)).pack(side="right", padx=16)
        warn = tk.Frame(self, bg=WARN_BG, highlightthickness=1, highlightbackground=FLAG)
        warn.pack(fill="x")
        tk.Label(warn, text="NEVER ENTER A SEED, A SEED PHRASE, OR A PRIVATE KEY. A device name such as SeedSigner is fine.",
                 font=themes.F("Courier", 10), bg=WARN_BG, fg=FLAG, anchor="w",
                 wraplength=1100, justify="left").pack(fill="x", padx=16, pady=6)

    # ---- air-gap gate -----------------------------------------------------
    def show_gate(self):
        if self.test_mode or self.ubuntu_test:
            self.lift_gate()
            return
        self.clear()
        f = tk.Frame(self, bg=INK)
        f.pack(fill="both", expand=True)
        box = tk.Frame(f, bg="#111111", highlightthickness=1, highlightbackground="#444444")
        box.place(relx=0.5, rely=0.5, anchor="center", width=660)
        tk.Label(box, text="VAULT FOLIO · AIR-GAP GATE", font=themes.F("Courier", 9),
                 fg="#8a8a84", bg="#111111").pack(anchor="w", padx=36, pady=(28, 10))
        tk.Label(box, text="Never enter a seed, a seed phrase, or a private key.",
                 font=themes.F("Courier", 10), fg="#ffb4b4", bg="#111111", wraplength=580,
                 justify="left").pack(anchor="w", padx=36, pady=(0, 8))
        tk.Label(box, text="Offline, nonpersistent session required.", font=themes.F("Georgia", 20),
                 fg=PAPER, bg="#111111").pack(anchor="w", padx=36)
        tk.Label(box, font=F_BODY, fg="#b9b9b4", bg="#111111", justify="left", wraplength=580,
                 text="Vault Folio handles the map to your cold storage. The app opens only when the OS reports "
                      "no default route, no active network interface, and no Wi-Fi or Bluetooth hardware. "
                      "RAM-backed system paths, disabled swap and process dump protection are also required. "
                      "An unavailable check blocks use; this is not proof against a compromised OS.").pack(
            anchor="w", padx=36, pady=(10, 16))
        self.gate_list = tk.Frame(box, bg="#111111")
        self.gate_list.pack(fill="x", padx=36)
        tk.Label(box, font=themes.F("Helvetica", 9), fg="#8a8a84", bg="#111111", justify="left", wraplength=580,
                 text="A route can remain after the Wi-Fi card is removed. This screen can turn networking off and check again. "
                      "It cannot remove Bluetooth hardware or put an installed home folder in RAM.").pack(
            anchor="w", padx=36, pady=(14, 6))
        btns = tk.Frame(box, bg="#111111")
        btns.pack(anchor="w", padx=36, pady=(6, 30))
        tk.Button(btns, text="TURN NETWORKING OFF AND CHECK", font=F_MONO_B, bg=PAPER, fg=INK,
                  relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self.offer_disable_network).pack(side="left")
        tk.Button(btns, text="CHECK AGAIN", font=F_MONO_B, bg="#111111", fg=PAPER,
                  relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self.run_gate).pack(side="left", padx=(8, 0))
        self.run_gate()

    def offer_disable_network(self):
        if not messagebox.askokcancel(
                APP_NAME,
                "Turn networking off and delete the default route, then check again?\n\n"
                "This lasts until you turn networking back on. It does not remove Bluetooth hardware "
                "and does not make a disk-backed home folder RAM-only."):
            return
        messagebox.showinfo(APP_NAME, disable_networking())
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
        if not self._locked and not self.test_mode and not self.ubuntu_test:
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
        self.configure(bg="#0a0a0a")  # fixed: lock screen ignores session themes
        self.overrideredirect(True)
        self.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}+0+0")
        self.grab_set()
        box = tk.Frame(self, bg="#111111", highlightthickness=1, highlightbackground="#444444")
        box.place(relx=0.5, rely=0.5, anchor="center", width=560)
        tk.Label(box, text="SESSION LOCKED", font=themes.F("Courier", 9), fg="#8a8a84",
                 bg="#111111").pack(anchor="w", padx=32, pady=(24, 8))
        tk.Label(box, text="Unsafe environment detected.", font=F_H2, fg=PAPER, bg="#111111").pack(anchor="w", padx=32)
        tk.Label(box, font=F_BODY, fg="#b9b9b4", bg="#111111", justify="left", wraplength=490,
                 text="A network, radio, persistent-memory risk or failed check was detected. Disable/remove it and re-check. Your unsaved plan remains in memory.").pack(anchor="w", padx=32, pady=(10, 14))
        tk.Button(box, text="RE-CHECK HARDWARE AND RESUME", font=F_MONO_B, bg="#fafaf8", fg="#0a0a0a",  # fixed palette
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
    app.guide_path = None
    app.guide_env = None
    app.guide_dek = None
    discard_plan(getattr(app, "saved_snapshot", None))  # CLEAR SESSION means it
    app.saved_snapshot = None
    app.header()
    frame = ScrollFrame(app)
    frame.pack(fill="both", expand=True)
    pad = tk.Frame(frame.inner, bg=PAPER)
    pad.pack(fill="both", expand=True, padx=56, pady=32)

    folio_label(pad, "Vault Folio · Cold storage inheritance guide").pack(anchor="w")
    tk.Label(pad, text="The plan is the part that has to survive you.", font=themes.F("Georgia", 26),
             bg=PAPER, fg=INK, justify="left", wraplength=820).pack(anchor="w", pady=(8, 18))
    if app.test_mode:
        tk.Label(pad, text="TEST MODE — SYNTHETIC DATA ONLY. ENVIRONMENT CHECKS ARE SKIPPED. "
                 "Only marked test files can be opened or saved. Enter no real inheritance details.",
                 font=F_MONO_B, bg=TEST_BG, fg=FLAG, justify="left", wraplength=760,
                 padx=12, pady=10).pack(fill="x", pady=(0, 14))
    elif app.ubuntu_test:
        tk.Label(pad, text="UBUNTU TEST — the air-gap lock is skipped. Encrypted save and the full guide are available. "
                 "This is not an offline session. Do not enter a real plan on a networked machine.",
                 font=F_MONO_B, bg=TEST_BG, fg=FLAG, justify="left", wraplength=760,
                 padx=12, pady=10).pack(fill="x", pady=(0, 14))

    def action(title, sentence, button_text, command, primary):
        card = tk.Frame(pad, bg=WHITE, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="x", pady=8)
        tk.Label(card, text=title, font=F_H2, bg=WHITE, fg=INK).pack(
            anchor="w", padx=18, pady=(14, 2))
        tk.Label(card, text=sentence, font=F_BODY, bg=WHITE, fg=BODY_TEXT,
                 anchor="w", justify="left", wraplength=760).pack(
            anchor="w", padx=18, pady=(0, 12))
        tk.Button(card, text=button_text, font=F_MONO_B, relief="flat",
                  padx=16, pady=10, cursor="hand2", bg=(INK if primary else PAPER2),
                  fg=(PAPER if primary else INK), highlightthickness=1,
                  highlightbackground=LINE, command=command).pack(
            anchor="w", padx=18, pady=(0, 14))

    action(
        "Open a guide",
        "Open an encrypted guide to read or update its instructions." if not app.test_mode else
        "Open a marked synthetic test guide only.",
        "OPEN TEST GUIDE" if app.test_mode else "OPEN GUIDE",
        lambda: open_file_flow(app), True,
    )
    action(
        "Start a guide",
        "Nine plain sheets. Answer what you can — the risk review flags what is missing." if not app.test_mode else
        "Use invented answers to try the sheets and save flow.",
        "START TEST GUIDE" if app.test_mode else "START THE GUIDE",
        lambda: start_wizard(app, blank_plan()),
        False,
    )



def open_file_flow(app):
    if app.test_mode:
        path = filedialog.askopenfilename(
            parent=app, title="Open synthetic test guide",
            filetypes=[("Vault Folio test guide", "*.csp.json *.json"), ("All files", "*.*")])
        if not path:
            return
        password = simpledialog.askstring(APP_NAME, "Enter the synthetic test passphrase:", show="*", parent=app)
        if password is None:
            return
        try:
            plan, guide_env, guide_dek = load_synthetic_plan(path, password, return_details=True)
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
            messagebox.showerror(APP_NAME, "Could not open this marked synthetic test guide.", parent=app)
            return
        finally:
            password = None
        app.opened_format = "VAULTFOLIO/2 · SYNTHETIC TEST"
        app.guide_path = path
        app.guide_env = guide_env
        app.guide_dek = guide_dek
        open_choice(app, plan)
        return
    if not app.ubuntu_test and not environment_is_safe(environment_report(), test_mode=False):
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
    app.guide_path = path
    if isinstance(env, dict) and env.get("magic") == HARDWARE_MAGIC:
        def opened_v2(result, _env=env):
            plan, dek = result
            app.guide_env = _env
            app.guide_dek = dek
            open_choice(app, plan)

        open_hardware(app, env, opened_v2,
                      lambda: app.ubuntu_test or environment_is_safe(environment_report(), test_mode=False),
                      return_key=True)
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
        if not app.ubuntu_test and not environment_is_safe(environment_report(), test_mode=False):
            discard_plan(plan)
            messagebox.showerror(APP_NAME, "Environment became unsafe. Nothing opened.")
            return
        open_choice(app, plan)
    else:
        messagebox.showerror(APP_NAME, "Only encrypted Vault Folio JSON plan files can be opened.")


def confirm_alter_saved_guide(app, plan):
    """A saved guide is not an open draft. Changing it needs a warning and the passphrase."""
    if not messagebox.askokcancel(
            APP_NAME,
            "This is a confirmed sealed guide.\n\n"
            "Viewing and adding heir notes does not change the recorded setup. "
            "Altering it can change what the family later relies on.\n\n"
            "Continue only if you mean to change the recorded guide. "
            "You will need this guide's passphrase. Nothing is changed until you save a new encrypted copy.",
            parent=app):
        return
    path = getattr(app, "guide_path", None)
    if path and not app.test_mode:
        pw = simpledialog.askstring(APP_NAME, "Enter this guide's passphrase to unlock changes:", show="*", parent=app)
        if not pw:
            return
        try:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    current = json.load(handle)
            except (OSError, UnicodeError, ValueError) as read_error:
                messagebox.showerror(
                    APP_NAME,
                    "The saved guide file could not be read (" + str(read_error) + "). "
                    "The guide was not opened for changes.", parent=app)
                return
            if isinstance(current, dict) and current.get("magic") == HARDWARE_MAGIC:
                from folio_security import open_package
                methods = current.get("methods") or []
                passphrase_indexes = [i for i, item in enumerate(methods)
                                      if (item.get("meta") or {}).get("kind") == "passphrase"]
                if not passphrase_indexes:
                    messagebox.showerror(
                        APP_NAME,
                        "This guide has no passphrase unlock method (for example, it is "
                        "YubiKey-only). Editing is verified by passphrase, so this guide "
                        "cannot be opened for changes here.", parent=app)
                    return
                last_error = None
                for index in passphrase_indexes:
                    try:
                        open_package(current, method_index=index, credential=pw)
                        last_error = None
                        break
                    except ValueError as exc:
                        last_error = exc
                if last_error is not None:
                    raise last_error
            else:
                decrypt_plan(current, pw)
        except (ValueError, TypeError):
            messagebox.showerror(APP_NAME, "That passphrase does not open this file. The guide was not opened for changes.", parent=app)
            return
        finally:
            pw = None
    start_wizard(app, plan)


def save_guide_notes(app, plan):
    """Persist beneficiary notes/checklist into the file the guide came from.

    A V2 envelope is re-sealed with the SAME data key and method set, so
    every configured unlock method keeps working and no credential is asked
    for. A legacy V1 file is re-sealed only after the entered passphrase is
    verified to open the current file, so a typo can never re-key it.
    """
    path = getattr(app, "guide_path", None)
    if not path:
        messagebox.showinfo(APP_NAME, "Open the encrypted file again, then save the notes.", parent=app)
        return
    env = getattr(app, "guide_env", None)
    dek = getattr(app, "guide_dek", None)
    try:
        if env is not None and dek is not None:
            save_encrypted(path, reseal_preserving_methods(plan, env, dek))
        else:
            pw = simpledialog.askstring(APP_NAME, "Enter this guide's passphrase to save the notes:",
                                        show="*", parent=app)
            if not pw:
                return
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    current = json.load(handle)
                decrypt_plan(current, pw)  # verify BEFORE anything is overwritten
                envelope = encrypt_plan(plan, pw)
            except (OSError, ValueError, TypeError, UnicodeError):
                messagebox.showerror(APP_NAME, "That passphrase does not open this file. Nothing was saved.", parent=app)
                return
            finally:
                pw = None
            save_encrypted(path, envelope)
    except Exception as exc:
        messagebox.showerror(APP_NAME, str(exc), parent=app)
        return
    if getattr(app, "saved_snapshot", None) is not None:
        discard_plan(app.saved_snapshot)  # "saved" now means the file with these notes
        app.saved_snapshot = copy.deepcopy(plan)
    messagebox.showinfo(APP_NAME, "Notes and checklist saved. Every existing unlock method still opens the file.", parent=app)


def open_choice(app, plan):
    is_synthetic_test = (isinstance(plan, dict) and isinstance(plan.get("meta"), dict)
                         and plan["meta"].get(TEST_MARKER) is True)
    if is_synthetic_test and not app.test_mode:
        discard_plan(plan)
        messagebox.showwarning(APP_NAME, "This is a synthetic test file. Open it only in synthetic test mode.", parent=app)
        return
    if app.test_mode and not is_synthetic_test:
        discard_plan(plan)
        messagebox.showwarning(APP_NAME, "Test mode opens only marked synthetic test files.", parent=app)
        return
    try:
        plan = prepare_plan(plan, blank_plan())
    except ValueError as exc:
        messagebox.showerror(APP_NAME, str(exc))
        return
    app.active_plan = plan
    plan.pop("savedOriginal", None)  # legacy dead key from an earlier editor build
    if getattr(app, "guide_path", None):
        app.saved_snapshot = copy.deepcopy(plan)
    dlg = tk.Toplevel(app)
    dlg.configure(bg=PAPER, highlightthickness=1, highlightbackground=INK)
    dlg.title(APP_NAME)
    dlg.grab_set()
    tk.Label(dlg, text="Guide opened: " + (plan["meta"].get("planName") or "untitled"),
             font=F_H2, bg=PAPER, fg=INK).pack(padx=24, pady=(20, 4), anchor="w")
    tk.Label(dlg, text="Choose how to open this guide. Viewing makes no changes; editing saves a new encrypted copy.",
             font=F_BODY, bg=PAPER, fg=BODY_TEXT, wraplength=560, justify="left").pack(padx=24, anchor="w")
    row = tk.Frame(dlg, bg=PAPER)
    row.pack(padx=24, pady=18, anchor="w")
    tk.Button(row, text="HEIR VIEW — READ & FOLLOW", font=F_MONO_B, bg=INK, fg=PAPER, relief="flat",
              padx=12, pady=8, cursor="hand2",
              command=lambda: (dlg.destroy(), show_heir(app, plan))).pack(side="left", padx=(0, 8))
    tk.Button(row, text="EDITOR VIEW — CHANGES", font=F_MONO_B, bg=PAPER, fg=FLAG, relief="flat",
              highlightthickness=1, highlightbackground=FLAG, padx=12, pady=8, cursor="hand2",
              command=lambda: (dlg.destroy(), confirm_alter_saved_guide(app, plan))).pack(side="left")
    ui.btn_secondary(dlg, "CANCEL — DO NOT OPEN",
                     lambda: (dlg.destroy(), home_screen(app))).pack(padx=24, pady=(0, 18), anchor="w")
    ui.center_window(dlg, app)


def show_heir(app, plan, close=None, close_label=None, edit_to_editor=True):
    def draw_diagrams(box, current_plan):
        tk.Label(box, text="ONE-PAGE FAMILY MAP · CLICK SETUP, KEY, OR PERSON CARDS",
                 font=themes.F("Courier", 9), bg=PAPER, fg=HINT).pack(anchor="w", pady=(0, 6))
        family_map = tk.Frame(box, bg=PAPER)
        family_map.pack(fill="both", expand=True)
        cv = tk.Canvas(family_map, bg=PAPER, highlightthickness=0)
        ybar = tk.Scrollbar(family_map, orient="vertical", command=cv.yview)
        xbar = tk.Scrollbar(family_map, orient="horizontal", command=cv.xview)
        cv.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        canvas_family_map(cv, current_plan)
        cv.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        family_map.rowconfigure(0, weight=1)
        family_map.columnconfigure(0, weight=1)
    show_beneficiary(app, plan, close or (lambda: home_screen(app)), build_runbook_text, draw_diagrams,
                     save_plan=lambda current: save_guide_notes(app, current),
                     edit_plan=(lambda: confirm_alter_saved_guide(app, plan)) if edit_to_editor else None,
                     close_label=close_label or 'CLOSE GUIDE & CLEAR SESSION')


# --------------------------------------------------------------------------
# Desktop questionnaire wizard
# --------------------------------------------------------------------------
STEP_DEFS = [
    ("start", "Start"),
    ("identity", "Plan & owner"),
    ("people", "People"),
    ("custodians", "Custodians"),
    ("vaults", "Vaults"),
    ("signing", "Signing"),
    ("backups", "Wallet map"),
    ("inventory", "Backups"),
    ("paths", "Recovery paths"),
    ("access", "Access"),
    ("inheritance", "Inheritance"),
    ("rehearsal", "Rehearsal"),
    ("instructions", "Family steps"),
    ("review", "Risk review"),
    ("export", "Export"),
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
        self._build_chrome()

    def _build_chrome(self):
        """(Re)build the editor chrome around the current state and render.

        Split from __init__ so returning from the heir preview can restore the
        exact same wizard — current step, vault interview, pending answers —
        instead of starting a fresh one."""
        app = self.app
        app.clear()
        app.header(status="PLAN EDITOR · CHANGES ARE NOT SAVED UNTIL YOU RE-ENCRYPT")
        if getattr(app, "guide_path", None):
            tk.Label(app, text="SAVED GUIDE · Editing changes what the family will later rely on. "
                     "Nothing is written until you save a new encrypted copy.",
                     font=F_MONO_B, bg="#fff1f2", fg=FLAG, wraplength=980, justify="left",
                     padx=16, pady=10).pack(fill="x")

        shell = tk.Frame(app, bg=PAPER)
        shell.pack(fill="both", expand=True)

        self.sidebar = ScrollFrame(shell, bg=PAPER2)
        self.sidebar.configure(width=245)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.sidebar.canvas.configure(width=225, bg=PAPER2)
        self.sidebar.inner.configure(bg=PAPER2)
        for i, (_, title) in enumerate(STEP_DEFS):
            b = tk.Button(self.sidebar.inner, text=f"{i + 1:02d}  {title}", font=themes.F("Courier", 9),
                          anchor="w", justify="left", wraplength=205,
                          relief="flat", padx=14, pady=8, cursor="hand2", bg=PAPER2, fg=HINT,
                          activebackground=INK, activeforeground=PAPER,
                          command=lambda n=i: self.goto(n))
            b.pack(fill="x")
        self.step_buttons = list(self.sidebar.inner.winfo_children())

        right = tk.Frame(shell, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)
        self.content = ScrollFrame(right)
        self.content.pack(fill="both", expand=True)

        nav = tk.Frame(right, bg=PAPER, highlightthickness=1, highlightbackground=LINE)
        nav.pack(fill="x")
        self.back_btn = ui.btn_secondary(nav, "← BACK / EXIT", self.back)
        self.back_btn.pack(side="left", padx=8, pady=6)
        ui.btn_secondary(nav, "HEIR VIEW", self.to_heir).pack(side="left", padx=8, pady=6)
        if getattr(self.app, "saved_snapshot", None):
            ui.btn_secondary(nav, "RESET TO SAVED", self.reset_to_saved).pack(side="left", padx=8, pady=6)
        self.pos_lbl = tk.Label(nav, text="", font=themes.F("Courier", 9), bg=PAPER, fg=HINT)
        self.pos_lbl.pack(side="left", expand=True)
        self.next_btn = ui.btn_primary(nav, "CONTINUE →", self.forward)
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
                self.stash_vault_intake_answer()
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

    def to_heir(self):
        """Preview the guide as the family will see it, without losing edits."""
        was_dirty = self.app.dirty
        self.stash_vault_intake_answer()

        def back_to_editor():
            self._build_chrome()  # same wizard: step, interview and edits intact
            self.app.dirty = was_dirty

        show_heir(self.app, self.plan, close=back_to_editor,
                  close_label="← BACK TO EDITOR", edit_to_editor=False)

    def reset_to_saved(self):
        snapshot = getattr(self.app, "saved_snapshot", None)
        if not snapshot:
            return
        if not messagebox.askokcancel(APP_NAME, "Discard additions made in this session and return to the saved guide?", parent=self.app):
            return
        self.plan.clear()
        self.plan.update(copy.deepcopy(snapshot))
        self.app.active_plan = self.plan
        self.app.dirty = False
        self.render()

    def stash_vault_intake_answer(self):
        """Keep uncommitted widget text in memory, separately for each question."""
        if self.vault_intake is not None and getattr(self, "intake_value", None) is not None:
            questions = self.vault_intake_questions()
            idx = min(self.vault_intake["index"], len(questions) - 1)
            key = questions[idx][0]
            self.vault_intake.setdefault("pending", {})[key] = self.intake_value.get()

    def mark_dirty(self, *_):
        self.app.dirty = True

    def saved_value(self, path):
        snapshot = getattr(self.app, "saved_snapshot", None)
        if not snapshot:
            return None
        return getp(snapshot, path)

    def lock_saved(self, widget, path):
        """Make a saved entry read-only and explain why on interaction.

        Entry/Combobox use state='readonly' (disabled would swallow events,
        so the explanation could never fire). tk.Text has no readonly state,
        so edits are blocked at the event level while selection stays live."""
        saved = self.saved_value(path)
        if saved in (None, ""):
            return False

        warned = {"clicked": False}

        def warn(_event=None):
            messagebox.showwarning(
                APP_NAME,
                "This entry was saved with the guide and is locked.\n\n"
                "You can add a note below. You cannot replace or delete a saved entry.",
                parent=self.app)

        def warn_once(_event=None):
            if not warned["clicked"]:
                warned["clicked"] = True
                warn()

        _NAV_KEYS = {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
                     "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R",
                     "Alt_L", "Alt_R", "Escape"}

        def block(event=None):
            if event is not None:
                if event.keysym in _NAV_KEYS or (
                        event.state & 0x4 and event.keysym in {"c", "C", "Insert"}):
                    return None  # only copy combos and navigation pass through
            warn()
            return "break"

        if isinstance(widget, tk.Text):
            widget.bind("<Key>", block)
            widget.bind("<<Cut>>", block)      # Ctrl+X otherwise slips past <Key>
            widget.bind("<<Clear>>", block)
            widget.bind("<<Paste>>", block)
            widget.bind("<Button-2>", block)  # middle-click paste on X11
            widget.bind("<Button-1>", warn_once)
        elif isinstance(widget, ttk.Combobox):
            # readonly blocks typing but BY DESIGN still allows picking another
            # dropdown option (mouse or arrow keys) — revert every such change.
            try:
                widget.configure(state="readonly")
            except tk.TclError:
                pass
            locked_value = widget.get()
            combo_pass = {"Tab", "Escape", "Shift_L", "Shift_R", "Control_L",
                          "Control_R", "Alt_L", "Alt_R"}  # no arrows: they change the value

            def revert(_event=None):
                if widget.get() != locked_value:
                    widget.set(locked_value)
                    warn()

            def block_keys(event=None):
                if event is not None and ((event.state & 0x4) or event.keysym in combo_pass):
                    return None  # copy combos and focus movement still work
                warn()
                return "break"

            widget.bind("<<ComboboxSelected>>", revert)
            widget.bind("<Key>", block_keys)
            widget.bind("<Button-1>", warn_once)
        else:
            try:
                widget.configure(state="readonly")
            except tk.TclError:
                pass
            widget.bind("<Button-1>", warn_once)
            widget.bind("<Key>", warn)
        return True

    # ---- form helpers -----------------------------------------------------
    def _label(self, parent, text, hint=""):
        tk.Label(parent, text=text.upper(), font=themes.F("Courier", 9), fg=BODY_TEXT, bg=PAPER,
                 anchor="w").pack(anchor="w", pady=(12, 2))
        tk.Label(parent, text=hint or "Add a short note only; never enter seeds, private keys, or descriptors.",
                 font=themes.F("Helvetica", 9), fg=HINT, bg=PAPER,
                 anchor="w", justify="left", wraplength=720).pack(anchor="w", pady=(0, 3))

    def entry(self, parent, label, path, hint=""):
        self._label(parent, label, hint)
        v = tk.StringVar(value=str(getp(self.plan, path) or ""))
        self.vars[path] = v  # keep the Tcl variable alive: a locked field attaches no trace, so without this the StringVar is garbage-collected and the entry shows blank
        e = tk.Entry(parent, textvariable=v, font=F_BODY, bg=WHITE, fg=INK, relief="solid", bd=1)
        ui.focusable(e)
        e.pack(fill="x", ipady=3)
        if not self.lock_saved(e, path):
            v.trace_add("write", lambda *_: (setp(self.plan, path, v.get()), self.mark_dirty()))
        e.bind("<Return>", lambda _event: (self.forward(), "break")[1])
        return v

    def combo(self, parent, label, path, options, hint=""):
        self._label(parent, label, hint)
        v = tk.StringVar(value=str(getp(self.plan, path) or ""))
        self.vars[path] = v  # keep the Tcl variable alive: a locked combobox attaches no binding closure, so without this the StringVar is garbage-collected and the combo shows blank
        cb = ttk.Combobox(parent, textvariable=v, values=options, state="readonly", font=F_BODY)
        cb.pack(fill="x")
        if not self.lock_saved(cb, path):
            cb.bind("<<ComboboxSelected>>", lambda *_: (setp(self.plan, path, v.get()), self.mark_dirty()))
        return v

    def text(self, parent, label, path, hint=""):
        self._label(parent, label, hint)
        t = tk.Text(parent, height=4, font=F_BODY, bg=WHITE, fg=INK, relief="solid", bd=1,
                    wrap="word")
        ui.focusable(t)
        t.insert("1.0", str(getp(self.plan, path) or ""))
        t.pack(fill="x")
        if self.lock_saved(t, path):
            return t

        def sync(*_):
            setp(self.plan, path, t.get("1.0", "end-1c"))
            self.mark_dirty()
        t.bind("<KeyRelease>", sync)
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
            tk.Checkbutton(parent, text=lab, variable=v, font=themes.F("Helvetica", 10), bg=PAPER, fg=INK,
                           activebackground=PAPER, selectcolor=WHITE, anchor="w", justify="left",
                           wraplength=620, command=toggle).pack(anchor="w")

    # ---- page scaffolding -------------------------------------------------
    def page(self, title, intro=""):
        c = self.content.inner
        for w in c.winfo_children():
            w.destroy()
        self.content.scroll_to_top()
        for i, b in enumerate(self.step_buttons):
            b.configure(bg=(INK if i == self.step else PAPER2),
                        fg=(PAPER if i == self.step else HINT))
        self.pos_lbl.configure(text=f"SECTION {self.step + 1} OF {len(STEP_DEFS)}")
        self.back_btn.configure(text="← BACK / EXIT")
        self.next_btn.configure(text=("DONE" if self.step == len(STEP_DEFS)-1 else "CONTINUE →"))
        pad = tk.Frame(c, bg=PAPER)
        pad.pack(fill="both", expand=True, padx=44, pady=28)
        folio_label(pad, f"Section {self.step + 1} of {len(STEP_DEFS)}").pack(anchor="w")
        tk.Label(pad, text=title, font=F_H2, bg=PAPER, fg=INK, anchor="w").pack(anchor="w", pady=(4, 6))
        if intro:
            tk.Label(pad, text=intro, font=F_BODY, bg=PAPER, fg=BODY_TEXT, justify="left",
                     wraplength=640, anchor="w").pack(anchor="w")
        tk.Frame(pad, bg=LINE, height=1).pack(fill="x", pady=14)
        tk.Label(pad,
                 text="STRUCTURE AND STORAGE LOCATIONS ONLY — never enter seed words, private keys, seed passphrases, xpubs, wallet descriptors, or full signing plans.",
                 font=themes.F("Helvetica", 9, "bold"), fg=FLAG, bg=PAPER, justify="left",
                 wraplength=640, anchor="w").pack(anchor="w", pady=(0, 10))
        if getattr(self.app, "saved_snapshot", None):
            tk.Label(pad, text="SAVED ENTRIES ARE LOCKED. Add a note. Reset returns to the saved copy.",
                     font=F_MONO_B, bg="#fff1f2", fg=FLAG, wraplength=680, justify="left",
                     padx=12, pady=8).pack(anchor="w", fill="x", pady=(0, 8))
            note = tk.Text(pad, height=3, font=F_BODY, bg=WHITE, fg=INK, relief="solid", bd=1, wrap="word")
            note.pack(fill="x")
            def add_note():
                text = note.get("1.0", "end-1c").strip()
                if not text:
                    return
                if not messagebox.askokcancel(APP_NAME, "Add this note on top of the saved guide? Saved entries stay unchanged.", parent=self.app):
                    return
                self.plan.setdefault("amendments", []).append(text)
                self.mark_dirty()
                note.delete("1.0", "end")
                messagebox.showinfo(APP_NAME, "Note added. Save an encrypted copy to keep it.", parent=self.app)
            ui.btn_secondary(pad, "ADD NOTE TO SAVED GUIDE", add_note, anchor="w", pady=6)
        return pad

    def note(self, parent, text, warn=False):
        fr = tk.Frame(parent, bg=PAPER2, highlightthickness=2,
                      highlightbackground=(FLAG if warn else INK))
        fr.pack(fill="x", pady=10)
        tk.Label(fr, text=text, font=themes.F("Helvetica", 9), bg=PAPER2, fg=BODY_TEXT, justify="left",
                 wraplength=600).pack(anchor="w", padx=12, pady=10)

    def render(self):
        sid = STEP_DEFS[self.step][0]
        getattr(self, "page_" + sid)()
        self.content.canvas.yview_moveto(0)

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
            tk.Label(fr, text="□  " + r, font=F_BODY, bg=PAPER, fg=INK, anchor="w",
                     justify="left", wraplength=620).pack(padx=12, pady=8, anchor="w")
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
            tk.Label(pad, text="·  " + h, font=themes.F("Helvetica", 9), bg=PAPER, fg=BODY_TEXT,
                     anchor="w", wraplength=640, justify="left").pack(anchor="w", pady=2)

    # ---- folio 01 ---------------------------------------------------------
    def page_identity(self):
        pad = self.page("Plan & owner", STEP_INTROS["identity"])
        self.entry(pad, "Plan name", "meta.planName", "Something your executor would recognize.")
        self.entry(pad, "Owner", "meta.owner", "Whose plan this is — the name the family knows you by.")
        self.entry(pad, "Date prepared", "meta.created", "YYYY-MM-DD. Refresh it whenever you make real changes.")
        self.entry(pad, "Jurisdiction / legal context", "meta.jurisdiction",
                   "Country/state, and whether a will or trust references this plan. The will should point to "
                   "this file — it should never contain seeds or hiding places.")
        self.text(pad, "Legal notes (optional)", "meta.legalNotes",
                  "Anything a lawyer wrote that affects this plan. Context, not secrets.")

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
        ui.btn_secondary(pad, "+ ADD AN HEIR", self.add_heir, anchor="w", pady=8)

    def draw_heirs(self):
        for w in self.heirs_box.winfo_children():
            w.destroy()
        heirs = self.plan["people"]["heirs"]
        for i, h in enumerate(heirs):
            fr = tk.LabelFrame(self.heirs_box, text=f"  HEIR {i+1}  ", font=F_MONO, bg=WHITE,
                               fg=INK, relief="solid", bd=1)
            fr.pack(fill="x", pady=4)
            inner = tk.Frame(fr, bg=WHITE)
            inner.pack(fill="x", padx=10, pady=8)

            def row(lbl, key, opts=None, hint=""):
                tk.Label(inner, text=lbl.upper(), font=themes.F("Courier", 8), bg=WHITE, fg=HINT,
                         anchor="w").pack(anchor="w")
                tk.Label(inner, text=hint or "Use a short note; never enter seeds or private keys.",
                         font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT, anchor="w",
                         wraplength=700, justify="left").pack(anchor="w")
                if opts:
                    v = tk.StringVar(value=h.get(key, ""))
                    cb = ttk.Combobox(inner, textvariable=v, values=opts, state="readonly", font=themes.F("Helvetica", 10))
                    cb.pack(fill="x")
                    cb.bind("<<ComboboxSelected>>", lambda *_: (h.__setitem__(key, v.get()), self.mark_dirty()))
                else:
                    v = tk.StringVar(value=h.get(key, ""))
                    v.trace_add("write", lambda *_: (h.__setitem__(key, v.get()), self.mark_dirty()))
                    tk.Entry(inner, textvariable=v, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(fill="x")

            row("Name", "name")
            row("Relationship", "relation")
            row("Role in recovery", "role", hint="e.g. holds delayed-path key B (sealed, with attorney)")
            row("Do they hold any spending-capable key today?", "holdsKeyNow",
                ["No", "Yes — intentional co-signer", "Yes — inheritance key, not usable yet"],
                hint="The default answer should be No. An heir holding a live key now can be targeted or coerced.")
            row("How they are reached / found", "contact")
            tk.Button(fr, text="REMOVE", font=themes.F("Courier", 8), bg=WHITE, fg=FLAG, relief="flat",
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
                frame = ui.card(container, pady=8)
                header = tk.Frame(frame, bg=WHITE)
                header.pack(fill="x", padx=12, pady=(10, 2))
                ui.badge(header, f"Record {i + 1}", HINT).pack(side="left")
                def remove(index=i, section_name=section):
                    saved_rows = (getattr(self.app, "saved_snapshot", None) or {}).get(section_name) or []
                    if index < len(saved_rows):
                        messagebox.showwarning(APP_NAME, "A saved record cannot be deleted. Add a note instead.", parent=self.app)
                        return
                    if messagebox.askyesno(APP_NAME, "Remove this unsaved record?", parent=self.app):
                        rows.pop(index)
                        self.mark_dirty()
                        redraw()
                ui.btn_danger(header, "REMOVE", remove, side="right")
                fields = record_fields(section, record)
                for key, label, options in fields:
                    tk.Label(frame, text=label, font=themes.F("Helvetica", 9), fg=BODY_TEXT, bg=WHITE,
                             anchor="w", wraplength=700).pack(anchor="w", padx=12, pady=(6, 0))
                    tk.Label(frame, text="Use a short, recognizable note; never enter a seed or private key.",
                             font=themes.F("Helvetica", 8), fg=HINT, bg=WHITE,
                             anchor="w", wraplength=700, justify="left").pack(anchor="w", padx=12)
                    value = tk.StringVar(value=record.get(key, ""))
                    def update(*_, row=record, name=key, var=value):
                        row[name] = var.get()
                        if name == "mode" and var.get() != "Direct access details inside encrypted guide":
                            row.pop("directAccess", None)
                        self.mark_dirty()
                    value.trace_add("write", update)
                    widget = ttk.Combobox(frame, textvariable=value, values=options) if options else ttk.Entry(frame, textvariable=value)
                    widget.pack(fill="x", padx=12)
                    if key == "directAccess":
                        widget.configure(show="*")
                    # Hold Tk variable alive for the lifetime of the field.
                    widget._folio_variable = value
                    if key in ("scheme", "kind", "mode"):
                        widget.bind("<<ComboboxSelected>>", lambda *_: redraw())
                tk.Frame(frame, bg=WHITE, height=10).pack()  # bottom breathing room
        def add():
            rows.append({"mode": "Hint only"} if section == "accessRecords" else {})
            self.mark_dirty()
            redraw()
        redraw()
        ui.btn_secondary(pad, "+ ADD ANOTHER RECORD", add, anchor="w", pady=10)

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
        ui.btn_secondary(pad, "+ ADD A VAULT", self.begin_vault_intake, anchor="w", pady=10)

    def begin_vault_intake(self):
        vault = {"intakeId": uuid.uuid4().hex,
                 "name": "New wallet setup", "m": "", "n": "", "script": "Not sure yet",
                 "coordinator": "", "timelock": {"enabled": False, "delay": ""}, "keys": [],
                 "intakeAnswers": {}}
        self.plan["vaults"].append(vault)
        self.vault_intake = {"vault": vault, "answers": vault["intakeAnswers"], "index": 0, "pending": {}}
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
        card = tk.Frame(pad, bg=WHITE, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="x", pady=(8, 12))
        tk.Label(card, text=f"QUESTION {idx + 1} OF {len(questions)}", font=F_MONO_B,
                 bg=WHITE, fg=OK).pack(anchor="w", padx=20, pady=(18, 8))
        bar = tk.Frame(card, bg=LINE, height=5)
        bar.pack(fill="x", padx=20, pady=(0, 14))
        tk.Frame(bar, bg=OK).place(relx=0, rely=0, relwidth=(idx + 1) / len(questions), relheight=1)
        tk.Label(card, text=title, font=F_H2, bg=WHITE, fg=INK, anchor="w", justify="left",
                 wraplength=640).pack(anchor="w", padx=20, pady=(2, 8))
        tk.Label(card, text=help_text, font=F_BODY, bg=WHITE, fg=BODY_TEXT, anchor="w", justify="left",
                 wraplength=640).pack(anchor="w", padx=20, pady=(0, 18))
        pending = self.vault_intake.setdefault("pending", {})
        self.intake_value = tk.StringVar(value=str(pending.get(
            key, self.vault_intake["answers"].get(key, ""))))
        if kind == "choice":
            for value, label in options:
                tk.Radiobutton(card, text=label, value=value, variable=self.intake_value,
                               font=F_BODY, bg=WHITE, activebackground=WHITE, selectcolor=PAPER2,
                               anchor="w", justify="left", wraplength=620).pack(anchor="w", padx=20, pady=6)
        else:
            answer_entry = tk.Entry(card, textvariable=self.intake_value, font=F_BODY, bg=WHITE, fg=INK,
                                    relief="solid", bd=1)
            answer_entry.pack(fill="x", padx=20, pady=(0, 8))
            answer_entry.bind("<Return>", lambda _event: (self.advance_vault_intake(), "break")[1])
            if kind == "number":
                tk.Radiobutton(card, text="I’m not sure", value="unsure", variable=self.intake_value,
                               font=F_BODY, bg=WHITE, activebackground=WHITE, selectcolor=PAPER2,
                               anchor="w").pack(anchor="w", padx=20, pady=(0, 16))
        vault = self.vault_intake["vault"]
        summary = tk.LabelFrame(pad, text="  YOUR WALLET SUMMARY  ", font=F_MONO,
                                bg=WHITE, fg=INK, relief="solid", bd=1)
        summary.pack(fill="x", pady=(22, 4))
        setup_label = {"single": "Single-signature", "multi": "Multisignature",
                       "unknown": "Not identified yet"}.get(vault.get("setupType"), "Waiting for your answer")
        quorum = (f"{vault['m']}-of-{vault['n']}" if vault.get("m") and vault.get("n")
                  else ("Threshold not known yet" if vault.get("setupType") == "multi" else "Not applicable yet"))
        for line in (f"Name: {vault.get('name') or 'Not named yet'}",
                     f"Signing setup: {setup_label}", f"Required keys: {quorum}",
                     f"Wallet app/service: {vault.get('coordinator') or 'Not answered yet'}"):
            tk.Label(summary, text=line, font=F_BODY, bg=WHITE, fg=INK,
                     anchor="w", justify="left", wraplength=620).pack(anchor="w", padx=12, pady=3)
        tk.Label(pad, text="DRAFT FOLIO BUILDS IN MEMORY AS YOU ANSWER · NOTHING IS SAVED YET",
                 font=themes.F("Courier", 8), bg=PAPER, fg=HINT).pack(anchor="w", pady=(24, 0))

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
        self.vault_intake.setdefault("pending", {}).pop(key, None)  # only this answer was committed
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
        fr = tk.LabelFrame(parent, text=title, font=F_MONO, bg=WHITE, fg=INK, relief="solid", bd=1)
        fr.pack(fill="x", pady=6)
        inner = tk.Frame(fr, bg=WHITE)
        inner.pack(fill="x", padx=12, pady=10)

        def row(lbl, key, opts=None, hint="", obj=None):
            obj = obj if obj is not None else v
            tk.Label(inner, text=lbl.upper(), font=themes.F("Courier", 8), bg=WHITE, fg=HINT,
                     anchor="w").pack(anchor="w", pady=(8, 0))
            tk.Label(inner, text=hint or "Use a short note; never enter seeds, keys, or descriptors.",
                     font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT,
                     anchor="w", wraplength=700, justify="left").pack(anchor="w")
            if opts:
                var = tk.StringVar(value=obj.get(key, ""))
                cb = ttk.Combobox(inner, textvariable=var, values=opts, state="readonly", font=themes.F("Helvetica", 10))
                cb.pack(fill="x")
                cb.bind("<<ComboboxSelected>>", lambda *_: (obj.__setitem__(key, var.get()),
                                                            self.mark_dirty(), self._maybe_redraw_vault(key)))
            else:
                var = tk.StringVar(value=str(obj.get(key, "")))
                var.trace_add("write", lambda *_: (obj.__setitem__(key, var.get()), self.mark_dirty()))
                tk.Entry(inner, textvariable=var, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(fill="x")

        row("Vault name", "name")
        row("Preset source / guide revision (optional)", "profileSource")
        row("Custom architecture / provider details", "customArchitecture")
        row("Purpose / tier", "tier", TIERS,
            "Theft-resistance and inheritance want opposite shapes. A small timelocked family pile plus a "
            "larger no-timelock deep vault beats one script trying to do both.")

        qrow = tk.Frame(inner, bg=WHITE)
        tk.Label(inner, text="QUORUM  (M of N)", font=themes.F("Courier", 8), bg=WHITE, fg=HINT,
                 anchor="w").pack(anchor="w", pady=(8, 0))
        tk.Label(inner, text="M is the required signer count; N is the total signer count.",
                 font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT, anchor="w").pack(anchor="w")
        qrow.pack(fill="x")
        vm = tk.StringVar(value=str(v.get("m", "")))
        vn = tk.StringVar(value=str(v.get("n", "")))
        vm.trace_add("write", lambda *_: (v.__setitem__("m", int(vm.get()) if vm.get().isdigit() else ""), self.mark_dirty()))
        vn.trace_add("write", lambda *_: (v.__setitem__("n", int(vn.get()) if vn.get().isdigit() else ""), self.mark_dirty()))
        tk.Entry(qrow, textvariable=vm, width=8, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(side="left", fill="x", expand=True)
        tk.Label(qrow, text=" OF ", font=F_MONO, bg=WHITE).pack(side="left")
        tk.Entry(qrow, textvariable=vn, width=8, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(side="left", fill="x", expand=True)
        tk.Label(inner, text="2-of-3 if a normal family must operate it. 3-of-5 when losing one site must not "
                             "matter. 3-of-7 is the loss-extreme — and a poor inheritance experience.",
                 font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT, anchor="w", wraplength=580,
                 justify="left").pack(anchor="w")

        row("Script type", "script", SCRIPTS)
        row("Coordinator software", "coordinator", COORDS,
            "The coordinator builds transactions and holds the watch-only wallet. It must be replaceable.")

        tk.Label(inner, text="TIMELOCKED RECOVERY PATH?", font=themes.F("Courier", 8), bg=WHITE,
                 fg=HINT, anchor="w").pack(anchor="w", pady=(8, 0))
        tk.Label(inner, text="Record whether this policy has a delayed spending path.",
                 font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT, anchor="w").pack(anchor="w")
        tl = v.get("timelock") or {}
        tlv = tk.StringVar(value=("yes" if tl.get("enabled") else ("no" if v.get("timelock") else "")))
        trow = tk.Frame(inner, bg=WHITE)
        trow.pack(fill="x")
        for val, lab in [("no", "No timelock"), ("yes", "Has timelock")]:
            tk.Radiobutton(trow, text=lab, value=val, variable=tlv, font=themes.F("Helvetica", 10),
                           bg=WHITE, activebackground=WHITE, selectcolor=WHITE,
                           command=lambda: self._set_timelock(v, tlv.get())).pack(side="left", padx=(0, 16))
        if tl.get("enabled"):
            tk.Label(inner, text="TIMELOCK DETAILS", font=themes.F("Courier", 8), bg=WHITE,
                     fg=HINT, anchor="w").pack(anchor="w", pady=(6, 0))
            tk.Label(inner, text="Prefer relative timelocks (OP_CSV): if the coins stay still, the path matures. "
                                 "Absolute dates mature on schedule, even if spending is active.",
                     font=themes.F("Helvetica", 8), bg=WHITE, fg=HINT, anchor="w", wraplength=700,
                     justify="left").pack(anchor="w")
            dv = tk.StringVar(value=tl.get("delay", ""))
            dv.trace_add("write", lambda *_: (tl.__setitem__("delay", dv.get()), self.mark_dirty()))
            tk.Entry(inner, textvariable=dv, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(fill="x")

        row("Notes", "notes", hint="Do not mix personal, trust, and business coins under one descriptor. "
                                   "Legal ownership should match who can sign.")

        # nested keys
        kf = tk.Frame(fr, bg=WHITE)
        kf.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(kf, text=f"KEYS IN THIS VAULT ({len(v.get('keys') or [])}"
                          + (f" of {v['n']} expected" if v.get("n") else "") + ")",
                 font=F_MONO_B, bg=WHITE, fg=INK, anchor="w").pack(anchor="w", pady=(4, 4))
        for ki, k in enumerate(v.get("keys") or []):
            self.draw_key(kf, k, ki, v)
        ui.btn_secondary(kf, "+ ADD A KEY",
                         lambda: (v.setdefault("keys", []).append({}), self.mark_dirty(),
                                  self.draw_vaults()), anchor="w", pady=6)
        ui.btn_danger(fr, "REMOVE VAULT", lambda i=vi: self.remove_vault(i)).pack(anchor="e", padx=10, pady=(0, 8))

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
                           font=themes.F("Courier", 9), bg=PAPER, fg=INK, relief="solid", bd=1)
        fr.pack(fill="x", pady=4)
        inner = tk.Frame(fr, bg=PAPER)
        inner.pack(fill="x", padx=10, pady=6)

        def row(lbl, key, opts=None, hint=""):
            tk.Label(inner, text=lbl.upper(), font=themes.F("Courier", 8), bg=PAPER, fg=HINT,
                     anchor="w").pack(anchor="w", pady=(6, 0))
            tk.Label(inner, text=hint or "Describe the role or location only; never enter a seed or key.",
                     font=themes.F("Helvetica", 8), bg=PAPER,
                     fg=(FLAG if hint.startswith("⚠") else HINT), anchor="w",
                     wraplength=700, justify="left").pack(anchor="w")
            if opts:
                var = tk.StringVar(value=k.get(key, ""))
                cb = ttk.Combobox(inner, textvariable=var, values=opts, state="readonly", font=themes.F("Helvetica", 10))
                cb.pack(fill="x")
                cb.bind("<<ComboboxSelected>>", lambda *_: (k.__setitem__(key, var.get()), self.mark_dirty(),
                                                            self._maybe_redraw_vault(key)))
            else:
                var = tk.StringVar(value=k.get(key, ""))
                var.trace_add("write", lambda *_: (k.__setitem__(key, var.get()), self.mark_dirty()))
                tk.Entry(inner, textvariable=var, font=themes.F("Helvetica", 10), relief="solid", bd=1).pack(fill="x")

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
        tk.Button(fr, text="REMOVE", font=themes.F("Courier", 8), bg=PAPER, fg=FLAG, relief="flat", cursor="hand2",
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
        self.text(pad, "Signing procedure notes", "signing.coordinatorNotes",
                  "The exact, tested steps for building and signing a spend, in your own words — "
                  "as you would tell a careful friend. No seeds or keys.")

    # ---- folio 05 ---------------------------------------------------------
    def page_backups(self):
        pad = self.page("Descriptor & configuration backups", STEP_INTROS["backups"])
        tk.Label(pad, text="DESCRIPTOR / WALLET-CONFIGURATION COPIES", font=F_MONO_B, bg=PAPER, fg=INK).pack(anchor="w")
        tk.Label(pad, text="For multisignature and timed policies, this copy may be essential to rebuild the wallet. "
                           "For a simple single-key setup, follow its tested restore instructions and record any "
                           "configuration copies that are actually needed.", font=themes.F("Helvetica", 9), fg=HINT,
                 bg=PAPER, wraplength=620, justify="left").pack(anchor="w", pady=(2, 8))
        self.dloc_box = tk.Frame(pad, bg=PAPER)
        self.dloc_box.pack(fill="x")
        self.draw_dlocs()
        ui.btn_secondary(pad, "+ ADD A COPY LOCATION",
                         lambda: (self.plan["backups"]["descriptorLocations"].append({}),
                                  self.mark_dirty(), self.draw_dlocs()), anchor="w", pady=8)
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
                   "backups.testedSoftware",
                   "e.g. 'Sparrow 1.9.3 + Coldcard Mk4 — signed a full test in March 2026.'")

    def draw_dlocs(self):
        for w in self.dloc_box.winfo_children():
            w.destroy()
        for i, d in enumerate(self.plan["backups"]["descriptorLocations"]):
            fr = tk.Frame(self.dloc_box, bg=WHITE, highlightthickness=1, highlightbackground=LINE)
            fr.pack(fill="x", pady=2)
            tk.Label(fr, text="WHERE", font=themes.F("Courier", 8), bg=WHITE, fg=HINT).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))
            tk.Label(fr, text="Broad place alias or site name.", font=themes.F("Helvetica", 8), bg=WHITE,
                     fg=HINT).grid(row=1, column=0, sticky="w", padx=8)
            v1 = tk.StringVar(value=d.get("where", ""))
            v1.trace_add("write", lambda *_: (d.__setitem__("where", v1.get()), self.mark_dirty()))
            tk.Entry(fr, textvariable=v1, font=themes.F("Helvetica", 10), relief="solid", bd=1).grid(row=2, column=0, sticky="ew", padx=8)
            tk.Label(fr, text="FORMAT", font=themes.F("Courier", 8), bg=WHITE, fg=HINT).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 0))
            tk.Label(fr, text="Choose the stored copy type.", font=themes.F("Helvetica", 8), bg=WHITE,
                     fg=HINT).grid(row=1, column=1, sticky="w", padx=8)
            v2 = tk.StringVar(value=d.get("format", ""))
            cb = ttk.Combobox(fr, textvariable=v2, font=themes.F("Helvetica", 10), state="readonly",
                              values=["Printed paper", "Plaintext digital file", "Encrypted digital file",
                                      "Wallet descriptor export (BSMS / Core / Sparrow)"], width=26)
            cb.grid(row=2, column=1, sticky="ew", padx=8)
            cb.bind("<<ComboboxSelected>>", lambda *_: (d.__setitem__("format", v2.get()), self.mark_dirty()))
            tk.Button(fr, text="✕", font=themes.F("Courier", 9), bg=WHITE, fg=FLAG, relief="flat", cursor="hand2",
                      command=lambda i=i: (self.plan["backups"]["descriptorLocations"].pop(i),
                                           self.mark_dirty(), self.draw_dlocs())).grid(row=2, column=2, padx=8)
            fr.columnconfigure(0, weight=3)
            fr.columnconfigure(1, weight=2)

    # ---- folio 06 ---------------------------------------------------------
    def page_inheritance(self):
        pad = self.page("Inheritance mechanism", STEP_INTROS["inheritance"])
        self.combo(pad, "Primary inheritance mechanism", "inheritance.mechanism", MECHANISMS,
                   "How the family actually gains the ability to recover: people, documents, timers. Pick the closest.")
        self.text(pad, "Release conditions — when and how heirs gain access", "inheritance.releaseConditions",
                  "e.g. Trustee releases sealed key B on presentation of death certificate; timelocked path "
                  "opens after 18 months of inactivity on the family vault…")
        self.entry(pad, "If timelocks are used — the refresh routine", "inheritance.heartbeat",
                   "The timer resets when coins move to yourself under the same policy. Put the reminder further "
                   "out than one missed year.")
        self.entry(pad, "Legal documents referencing this plan", "inheritance.legalDocs",
                   "The will names that instructions exist and who holds them — never the seeds.")
        self.entry(pad, "Where the sealed instruction letter lives", "inheritance.letterLocation",
                   "e.g. 'with the will at Harbor & Finch' or 'desk drawer, red envelope'.")
        self.text(pad, "Canary / liveness signal (optional)", "inheritance.canary",
                  "e.g. one small watched UTXO on the family descriptor; if it moves, someone is spending that "
                  "policy. An alarm, not a dead-man switch.")

    # ---- folio 07 ---------------------------------------------------------
    def page_rehearsal(self):
        pad = self.page("Has it actually been tested?", STEP_INTROS["rehearsal"])
        self.combo(pad, "Restore drill: one key restored from its physical backup onto a blank signer?",
                   "rehearsal.restoreDrill", YESNO3,
                   "An untested backup is a story, not a backup. One key, onto a blank device, all the way to a verified wallet.")
        self.combo(pad, "Family walkthrough: has the spouse/heir opened these instructions and found the "
                        "descriptor without your help?", "rehearsal.familyWalkthrough",
                   ["Yes — they found everything unaided", "They know the plan exists", "Not yet"])
        self.entry(pad, "Date of last full test spend", "rehearsal.testSpendDate", "YYYY-MM-DD is enough.")
        self.text(pad, "Rehearsal notes / what went wrong and was fixed", "rehearsal.notes",
                  "What broke during rehearsal and what you changed. Future-you will thank present-you.")

    # ---- folio 08: review -------------------------------------------------
    def page_review(self):
        pad = self.page("Risk review", STEP_INTROS["review"])
        findings = analyze_plan(self.plan)
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in findings:
            counts[f["sev"]] += 1
        colors = {"critical": FLAG, "warning": WARN_TEXT, "info": HINT}
        chips = tk.Frame(pad, bg=PAPER)
        chips.pack(anchor="w", pady=(0, 12))
        for sev, word in (("critical", "CRITICAL"), ("warning", "WARNINGS"), ("info", "NOTES")):
            chip = tk.Frame(chips, bg=WHITE, highlightthickness=1, highlightbackground=colors[sev])
            chip.pack(side="left", padx=(0, 8))
            tk.Label(chip, text=f"{counts[sev]} {word}", font=ui.F_BADGE, fg=colors[sev],
                     bg=WHITE, padx=10, pady=4).pack()
        if not findings:
            tk.Label(pad, text="No findings — the failure simulator has nothing to flag. Rehearse anyway.",
                     font=F_BODY, bg=PAPER, fg=OK).pack(anchor="w", pady=6)
        for f in findings:
            fr = tk.Frame(pad, bg=WHITE, highlightthickness=1, highlightbackground=LINE)
            fr.pack(fill="x", pady=4)
            tk.Frame(fr, bg=colors[f["sev"]], width=5).pack(side="left", fill="y")
            inner = tk.Frame(fr, bg=WHITE)
            inner.pack(side="left", fill="both", expand=True)
            tk.Label(inner, text=f["sev"].upper(), font=themes.F("Courier", 8, "bold"), bg=WHITE,
                     fg=colors[f["sev"]]).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(inner, text=f["title"], font=themes.F("Helvetica", 11, "bold"), bg=WHITE, fg=INK,
                     anchor="w", wraplength=600, justify="left").pack(anchor="w", padx=12)
            body = f["detail"] + (("\n→ " + f["fix"]) if f["fix"] else "")
            tk.Label(inner, text=body, font=themes.F("Helvetica", 9), bg=WHITE, fg=BODY_TEXT, anchor="w",
                     wraplength=600, justify="left").pack(anchor="w", padx=12, pady=(2, 10))
        self.text(pad, "Owner notes (encrypted with the plan)", "ownerNotes",
                  "Anything the family should hear in your voice. The file is encrypted, but it will be opened — "
                  "still no seeds, keys, or passphrases.")

    # ---- folio 09: export -------------------------------------------------
    def page_export(self):
        pad = self.page("Encrypt & export the inheritance file")
        if self.app.test_mode:
            tk.Label(pad, text="TEST MODE — SYNTHETIC ENCRYPTED SAVE ENABLED", font=F_MONO_B,
                     bg=TEST_BG, fg=FLAG, padx=12, pady=10).pack(anchor="w", fill="x", pady=12)
            tk.Label(pad, text="This run skips environment checks. Use invented answers only. Saving exercises the real "
                     "VAULTFOLIO/2 encryption and encrypted-file writer, but does not prove a safe operating system. "
                     "Test files are marked and rejected by normal mode. No YubiKey actions are available here.",
                     font=F_BODY, bg=PAPER, fg=INK, justify="left", wraplength=620).pack(anchor="w", pady=8)
            tk.Button(pad, text="SAVE SYNTHETIC TEST FILE", font=F_MONO_B, bg=INK, fg=PAPER,
                      relief="flat", padx=14, pady=8,
                      command=lambda: save_synthetic_test_flow(self.app, self.plan)).pack(anchor="w", pady=12)
        else:
            self.note(pad, "Choose any independent unlock methods for this guide. Give a passphrase or enrolled YubiKey "
                           "to your lawyer if desired. Keep the program, encrypted file, and non-secret discovery instructions "
                           "where family can find them. Release conditions are instructions, not a software-enforced time lock.")
            add_export_controls(pad, self.app, self.plan,
                                lambda: self.app.ubuntu_test or environment_is_safe(environment_report()))

        # --- preview: the pictures the family will see ---------------------
        if self.plan["vaults"]:
            tk.Label(pad, text="SETUP DIAGRAM PREVIEW · CHECK THIS AGAINST YOUR WALLET", font=F_MONO_B,
                     bg=PAPER, fg=INK).pack(anchor="w", pady=(20, 6))
            for vi, v in enumerate(self.plan["vaults"]):
                cv = tk.Canvas(pad, bg=PAPER, highlightthickness=0)
                canvas_quorum(cv, v, vi)
                cv.pack(anchor="w", pady=(0, 14))
            tk.Label(pad, text="SIGNING FLOW", font=F_MONO_B, bg=PAPER, fg=INK).pack(anchor="w", pady=(4, 6))
            cv2 = tk.Canvas(pad, bg=PAPER, highlightthickness=0)
            canvas_psbt_flow(cv2, self.plan["signing"].get("medium"))
            cv2.pack(anchor="w", pady=(0, 14))

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
                 font=themes.F("Helvetica", 9), fg=HINT, bg=PAPER, justify="left", wraplength=620).pack(anchor="w", pady=14)


def start_wizard(app, plan):
    app.wizard = Wizard(app, plan)
    return app.wizard


def save_synthetic_test_flow(app, plan):
    if not messagebox.askokcancel(
            "Synthetic test file only",
            "This mode skips all environment checks. Use only invented questionnaire answers and a new test passphrase. "
            "Never enter or save a real inheritance plan here. Continue?", parent=app):
        return
    password = simpledialog.askstring(APP_NAME, "Create a TEST-ONLY passphrase (at least 12 characters). "
                                      "Do not reuse any real passphrase:", show="*", parent=app)
    if password is None:
        return
    if len(password) < 12:
        password = None
        messagebox.showerror(APP_NAME, "The test passphrase must contain at least 12 characters.", parent=app)
        return
    confirm = simpledialog.askstring(APP_NAME, "Confirm the TEST-ONLY passphrase:", show="*", parent=app)
    if confirm is None or confirm != password:
        password = confirm = None
        messagebox.showerror(APP_NAME, "The passphrases did not match.", parent=app)
        return
    confirm = None
    path = filedialog.asksaveasfilename(
        parent=app, title="Save synthetic encrypted test guide", defaultextension=".csp.json",
        initialfile="synthetic-test-guide.csp.json",
        filetypes=[("Vault Folio encrypted guide", "*.csp.json"), ("JSON file", "*.json")])
    if not path:
        password = None
        return
    try:
        save_synthetic_plan(path, plan, password)
    except (OSError, ValueError):
        messagebox.showerror(APP_NAME, "Could not save the encrypted synthetic test file.", parent=app)
    else:
        app.dirty = False
        messagebox.showinfo(APP_NAME, "Encrypted synthetic test file saved. Use OPEN TEST FILE to verify the passphrase "
                            "and beneficiary view. Normal mode will refuse this marked test file.", parent=app)
    finally:
        password = None


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
    test_mode = any(flag in sys.argv for flag in (
        "--test-session", "--test-only-synthetic-questionnaire"))
    ubuntu_test = "--ubuntu-test" in sys.argv
    app = App(test_mode=test_mode, ubuntu_test=ubuntu_test)
    app.mainloop()


if __name__ == "__main__":
    main()
