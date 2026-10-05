"""Experimental offline YubiKey envelope. Never provisions or overwrites a device.

Every configured method is an independent alternative, never a threshold.
Family questions are knowledge-based passwords, not a stronger security factor.
"""
import base64
import copy
import json
import os
import re
import shutil
import unicodedata
import subprocess

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = "VAULTFOLIO/2"
ITERATIONS = 600_000
MAX_BYTES = 10 * 1024 * 1024
DOMAIN = b"VAULTFOLIO/2/key-wrap"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def b64(value):
    return base64.b64encode(value).decode("ascii")


def unb64(value, size=None):
    if not isinstance(value, str) or len(value) > 2 * MAX_BYTES:
        raise ValueError("Malformed encrypted package.")
    try:
        out = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed encrypted package.") from exc
    if size is not None and len(out) != size:
        raise ValueError("Malformed encrypted package.")
    return out


def yubikey_response(challenge, slot):
    """Only a public challenge enters argv; response stays in captured memory."""
    if not isinstance(challenge, bytes) or len(challenge) != 32 or type(slot) is not int or slot not in (1, 2):
        raise ValueError("Invalid YubiKey challenge or slot.")
    executable = shutil.which("ykman")
    if not executable:
        raise ValueError("YubiKey Manager CLI (ykman) is not installed. See docs/YUBIKEY.md.")
    try:
        result = subprocess.run([executable, "otp", "calculate", str(slot), challenge.hex()],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=40)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("YubiKey unavailable or touch timed out. Retry with one compatible key connected.") from exc
    value = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        # Never show stdout/stderr: third-party diagnostics may contain secrets.
        raise ValueError("YubiKey response failed. Check the configured HMAC-SHA1 slot and touch the key.")
    return bytes.fromhex(value)


MAX_METHODS = 12


def question_material(answers):
    if not isinstance(answers, list) or not 3 <= len(answers) <= 5:
        raise ValueError("Use 3 to 5 answers, all required together.")
    normalized = []
    for answer in answers:
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 4096:
            raise ValueError("Every question needs a nonempty answer (maximum 4096 characters).")
        normalized.append(" ".join(unicodedata.normalize("NFKC", answer).casefold().split()))
    return canonical(normalized)


def wrap_key(metadata, credential=None, response=None):
    salt = unb64(metadata["salt"], 16)
    kind = metadata["kind"]
    if kind == "yubikey":
        if not isinstance(response, bytes) or len(response) != 20:
            raise ValueError("Invalid hardware response.")
        material = response
    else:
        if kind == "questions":
            if not isinstance(credential, list) or len(credential) != len(metadata["questions"]):
                raise ValueError("Answer every displayed question.")
            raw = question_material(credential)
        else:
            if not isinstance(credential, str):
                raise ValueError("Enter your guide passphrase.")
            raw = credential.encode("utf-8")
        material = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                             salt=salt, iterations=ITERATIONS).derive(raw)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt,
                info=DOMAIN + b"/" + kind.encode("ascii")).derive(material)


def validate(env):
    """Reject malformed metadata before KDF work or hardware interaction."""
    try:
        if not isinstance(env, dict) or set(env) != {"magic", "cipher", "iv", "methods", "data"}:
            raise ValueError()
        if env["magic"] != MAGIC or env["cipher"] != "AES-256-GCM":
            raise ValueError()
        unb64(env["iv"], 12)
        if not isinstance(env["methods"], list) or not 1 <= len(env["methods"]) <= MAX_METHODS:
            raise ValueError()
        for item in env["methods"]:
            if not isinstance(item, dict) or set(item) != {"meta", "wrapped"}:
                raise ValueError()
            m = item["meta"]
            expected = {"kind", "label", "salt", "iv", "iterations"}
            if not isinstance(m, dict) or m.get("kind") not in ("passphrase", "yubikey", "questions"):
                raise ValueError()
            if not isinstance(m.get("label"), str) or not 1 <= len(m["label"]) <= 80:
                raise ValueError()
            if m["kind"] == "yubikey":
                expected |= {"slot", "challenge"}
                if type(m["slot"]) is not int or m["slot"] not in (1, 2):
                    raise ValueError()
                unb64(m["challenge"], 32)
            if m["kind"] == "questions":
                expected.add("questions")
                questions = m["questions"]
                if not isinstance(questions, list) or not 3 <= len(questions) <= 5:
                    raise ValueError()
                if any(not isinstance(q, str) or not q.strip() or len(q) > 500 for q in questions):
                    raise ValueError()
                if len(set(questions)) != len(questions):
                    raise ValueError()
            if set(m) != expected or type(m["iterations"]) is not int:
                raise ValueError()
            if m["iterations"] != (0 if m["kind"] == "yubikey" else ITERATIONS):
                raise ValueError()
            unb64(m["salt"], 16)
            unb64(m["iv"], 12)
            unb64(item["wrapped"], 48)
        if not 16 <= len(unb64(env["data"])) <= MAX_BYTES + 16:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Unsupported or malformed encrypted guide.") from exc
    return env


def seal(plan, methods, *, response_provider=yubikey_response):
    """Each method opens the same guide independently (OR access).

    Setup configs contain passphrase, or slot, or questions+answers. Secrets
    are used only to derive wrapping keys and never serialized into the file.
    """
    if not isinstance(plan, dict) or not isinstance(methods, list) or not 1 <= len(methods) <= MAX_METHODS:
        raise ValueError("Configure between 1 and 12 independent unlock methods.")
    plaintext = json.dumps(plan, ensure_ascii=False).encode("utf-8")
    if len(plaintext) > MAX_BYTES:
        raise ValueError("Guide too large.")
    # Construct and validate every public method before contacting any device.
    hardware_challenge = b64(os.urandom(32))
    metadata = []
    credentials = []
    for config in methods:
        kind = config.get("kind")
        m = {"kind": kind, "label": config.get("label") or kind,
             "salt": b64(os.urandom(16)), "iv": b64(os.urandom(12)),
             "iterations": 0 if kind == "yubikey" else ITERATIONS}
        credential = None
        if kind == "yubikey":
            m.update(slot=config.get("slot", 2), challenge=hardware_challenge)
        elif kind == "passphrase":
            credential = config.get("passphrase", "")
            if not isinstance(credential, str) or len(credential) < 12:
                raise ValueError("Use a guide passphrase of at least 12 characters.")
        elif kind == "questions":
            m["questions"] = config.get("questions")
            credential = config.get("answers")
            question_material(credential)
            if not isinstance(m["questions"], list) or len(credential) != len(m["questions"]):
                raise ValueError("Each question needs an answer.")
        else:
            raise ValueError("Unsupported unlock method.")
        metadata.append(m)
        credentials.append(credential)
    env = {"magic": MAGIC, "cipher": "AES-256-GCM", "iv": b64(os.urandom(12)),
           "methods": [{"meta": m, "wrapped": b64(bytes(48))} for m in metadata], "data": b64(bytes(16))}
    validate(env)
    del env["data"]
    dek = os.urandom(32)
    seen_responses = set()
    for item, credential in zip(env["methods"], credentials):
        m = item["meta"]
        response = response_provider(unb64(m["challenge"], 32), m["slot"]) if m["kind"] == "yubikey" else None
        if response is not None:
            if response in seen_responses:
                raise ValueError("This YubiKey configuration is already enrolled. Use a distinct key/configuration or remove the duplicate method.")
            seen_responses.add(response)
        kek = wrap_key(m, credential, response)
        wrapped = AESGCM(kek).encrypt(unb64(m["iv"], 12), dek, DOMAIN + canonical(m))
        item["wrapped"] = b64(wrapped)
    env["data"] = b64(AESGCM(dek).encrypt(unb64(env["iv"], 12), plaintext, canonical(env)))
    return env


def open_package(env, *, method_index=0, credential=None, response_provider=yubikey_response,
               return_key=False):
    validate(env)
    if type(method_index) is not int or not 0 <= method_index < len(env["methods"]):
        raise ValueError("Choose a listed unlock method.")
    item = env["methods"][method_index]
    m = item["meta"]
    response = response_provider(unb64(m["challenge"], 32), m["slot"]) if m["kind"] == "yubikey" else None
    kek = wrap_key(m, credential, response)
    try:
        dek = AESGCM(kek).decrypt(unb64(m["iv"], 12), unb64(item["wrapped"], 48), DOMAIN + canonical(m))
        header = {key: value for key, value in env.items() if key != "data"}
        plaintext = AESGCM(dek).decrypt(unb64(env["iv"], 12), unb64(env["data"]), canonical(header))
        plan = json.loads(plaintext.decode("utf-8"))
        if not isinstance(plan, dict):
            raise ValueError("Invalid guide document.")
        if return_key:
            return plan, dek
        return plan
    except (InvalidTag, UnicodeError, ValueError) as exc:
        raise ValueError("Unable to unlock: incorrect credential, wrong key, or damaged file.") from exc


def reseal_preserving_methods(plan, env, dek):
    """Re-encrypt changed plan data under the SAME data key and method set.

    Every existing unlock method keeps working and no credential is asked
    for, because each method's wrapped key stays byte-identical; only the
    plan ciphertext and its IV are replaced. The DEK comes from the open
    that produced this plan (the plaintext already lives in RAM, so holding
    its key adds no new exposure).
    """
    validate(env)
    if not isinstance(dek, (bytes, bytearray)) or len(dek) != 32:
        raise ValueError("Cannot re-seal without the key from the original open.")
    header_old = {key: value for key, value in env.items() if key != "data"}
    try:
        AESGCM(bytes(dek)).decrypt(unb64(env["iv"], 12), unb64(env["data"]), canonical(header_old))
    except InvalidTag as exc:
        raise ValueError("This key does not match this file; refusing to save.") from exc
    plaintext = json.dumps(plan, ensure_ascii=False).encode("utf-8")
    if len(plaintext) > MAX_BYTES:
        raise ValueError("Guide too large.")
    new = {"magic": env["magic"], "cipher": env["cipher"], "iv": b64(os.urandom(12)),
           "methods": copy.deepcopy(env["methods"])}
    header = {key: value for key, value in new.items() if key != "data"}
    new["data"] = b64(AESGCM(bytes(dek)).encrypt(unb64(new["iv"], 12), plaintext,
                                                 canonical(header)))
    validate(new)
    return new
