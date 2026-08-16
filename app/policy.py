"""L3 signed policy bundles — ed25519 maker-checker promotion, tamper rejection.

A policy bundle is a JSON doc + ed25519 signature over its canonical bytes.
Promotion requires TWO signatures (maker + checker — two demo personas).
The engine refuses to load unsigned/tampered bundles (demoed live).
Every decision record binds policy_version_hash (sha256 of canonical bytes).
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


def canon(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def doc_hash(doc: dict) -> str:
    return "sha256:" + hashlib.sha256(canon(doc)).hexdigest()


def gen_keypair(name: str, keys_dir: Path):
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    (keys_dir / f"{name}.key").write_bytes(
        priv.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption()))
    (keys_dir / f"{name}.pub").write_bytes(
        pub.public_bytes(serialization.Encoding.PEM,
                         serialization.PublicFormat.SubjectPublicKeyInfo))
    return name


def load_key(name: str, keys_dir: Path, private: bool = True):
    pem = (keys_dir / (f"{name}.key" if private else f"{name}.pub")).read_bytes()
    if private:
        return serialization.load_pem_private_key(pem, password=None)
    return serialization.load_pem_public_key(pem)


def sign_policy(doc: dict, signer_name: str, keys_dir: Path) -> dict:
    """Returns bundle = doc + signatures[signer_name]. Signs the canonical doc
    with ALL signatures stripped, so multi-signer order never matters."""
    doc_no_sig = {k: v for k, v in doc.items() if k != "signatures"}
    sig = load_key(signer_name, keys_dir).sign(canon(doc_no_sig))
    bundle = dict(doc)
    bundle.setdefault("signatures", {})[signer_name] = sig.hex()
    return bundle


def verify_bundle(bundle: dict, required: tuple = ("maker", "checker"), keys_dir: Path = None) -> dict:
    """Verify a policy bundle. Raises PolicyTamperError on any integrity failure.
    Returns the validated policy rules + policy_version_hash."""
    keys_dir = keys_dir or Path(__file__).resolve().parent.parent / "keys"
    doc = {k: v for k, v in bundle.items() if k != "signatures"}
    signatures = bundle.get("signatures", {})
    missing = [s for s in required if s not in signatures]
    if missing:
        raise PolicyTamperError(f"missing signatures: {missing}")
    for signer in required:
        pub: Ed25519PublicKey = load_key(signer, keys_dir, private=False)
        try:
            pub.verify(bytes.fromhex(signatures[signer]), canon(doc))
        except Exception:
            raise PolicyTamperError(f"signature invalid for '{signer}' — tampered or wrong key")
    return {"rules": doc.get("rules", doc), "policy_version_hash": doc_hash(doc),
            "policy_id": doc.get("policy_id", "unknown")}


class PolicyTamperError(Exception):
    pass


# --- default demo policies (bank-a strict, bank-b lenient — same txn, two decisions)
DEFAULT_BANK_A = {
    "policy_id": "bank-a-v1",
    "bank": "A",
    "rules": {
        "decline_gte": 75, "escalate_gte": 50, "instant_multiplier": 40,
        "min_signal_coverage": 0.5, "swap_window_hours": 24,
        "breaker_open_posture": {"mode": "ESCALATE_ONLY", "cap": 1000},
    },
}
DEFAULT_BANK_B = {
    "policy_id": "bank-b-v1",
    "bank": "B",
    "rules": {
        "decline_gte": 88, "escalate_gte": 62, "instant_multiplier": 60,
        "min_signal_coverage": 0.34, "swap_window_hours": 12,
        "breaker_open_posture": {"mode": "ESCALATE_ONLY", "cap": 5000},
    },
}
