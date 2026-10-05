"""Synthetic-only package helpers for exercising encrypted save/open flows."""
import json
from pathlib import Path

import folio_security as security
from folio_storage import save_encrypted


TEST_MARKER = "syntheticTest"
MAX_FILE_BYTES = 10 * 1024 * 1024


def seal_synthetic_plan(plan, passphrase):
    """Seal an explicitly marked synthetic plan with a single passphrase method."""
    if not isinstance(plan, dict):
        raise ValueError("Synthetic guide must be a plan object.")
    snapshot = json.loads(json.dumps(plan, ensure_ascii=False))
    meta = snapshot.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("Synthetic guide metadata must be an object.")
    meta[TEST_MARKER] = True
    envelope = security.seal(snapshot, [{
        "kind": "passphrase",
        "label": "Synthetic test passphrase",
        "passphrase": passphrase,
    }])
    if security.open_package(envelope, credential=passphrase) != snapshot:
        raise ValueError("Synthetic guide encryption verification failed.")
    return envelope


def open_synthetic_envelope(envelope, passphrase):
    """Open only a marked, passphrase-only synthetic test package."""
    security.validate(envelope)
    methods = envelope.get("methods", [])
    if len(methods) != 1 or methods[0].get("meta", {}).get("kind") != "passphrase":
        raise ValueError("Test mode opens only passphrase-protected synthetic test files.")
    plan = security.open_package(envelope, credential=passphrase)
    meta = plan.get("meta") if isinstance(plan, dict) else None
    if not isinstance(meta, dict) or meta.get(TEST_MARKER) is not True:
        raise ValueError("This is not a marked synthetic test file.")
    return plan


def save_synthetic_plan(path, plan, passphrase):
    """Encrypt, verify, and atomically save a synthetic test plan."""
    envelope = seal_synthetic_plan(plan, passphrase)
    save_encrypted(path, envelope, max_bytes=MAX_FILE_BYTES)


def load_synthetic_plan(path, passphrase):
    """Load a bounded encrypted file and require its synthetic marker."""
    target = Path(path)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Test file is too large.")
    try:
        with target.open("r", encoding="utf-8") as handle:
            envelope = json.load(handle)
    except RecursionError as exc:
        raise ValueError("This test file could not be opened.") from exc
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        raise ValueError("This test file could not be opened.") from exc
    if not isinstance(envelope, dict):
        raise ValueError("This test file could not be opened.")
    return open_synthetic_envelope(envelope, passphrase)
