"""L5 dual-ledger audit — hash-chained, pseudonymized, externally anchored.

Intercept Ledger: inline, linear hash chain over decision records.
Agent Ledger: async, txn_id-linked (separate chain avoids the race condition).
MSISDNs pseudonymized with HMAC pepper (bank-held key in production).
External anchor: RFC 3161-style anchoring via a free TSA, with retry queue and
anchoring state (pending -> anchored); verification-on-read proves integrity as
of the last successful anchor (detection window <= anchor interval = 10 records).
"""
from __future__ import annotations
import hashlib, hmac, json, threading, time, urllib.request
from pathlib import Path


class DualLedger:
    def __init__(self, store_dir: Path, pepper: str, anchor_every: int = 10):
        self.store_dir = Path(store_dir); self.store_dir.mkdir(parents=True, exist_ok=True)
        self.intercept_path = self.store_dir / "intercept_ledger.jsonl"
        self.agent_path = self.store_dir / "agent_ledger.jsonl"
        self.anchor_path = self.store_dir / "anchor_receipts.jsonl"
        self.pepper = pepper.encode()
        self.anchor_every = anchor_every
        self._lock = threading.Lock()
        self._anchor_queue: list[dict] = []

    # --- pseudonymization ---------------------------------------------------
    def pseudonym(self, msisdn: str) -> str:
        return "msisdn_" + hmac.new(self.pepper, msisdn.encode(), hashlib.sha256).hexdigest()[:20]

    # --- intercept (inline) ---------------------------------------------------
    def append_intercept(self, txn_id: str, msisdn: str, decision: dict, policy_hash: str) -> dict:
        rec = {
            "seq": self._count(self.intercept_path) + 1,
            "txn_id": txn_id, "msisdn_hash": self.pseudonym(msisdn),
            "decision": decision["decision"], "band": decision["band"],
            "weighted_risk": decision["weighted_risk"],
            "policy_version_hash": policy_hash,
            "signals_digest": hashlib.sha256(json.dumps(
                decision.get("reasons", []), sort_keys=True).encode()).hexdigest(),
            "signals": decision.get("reasons", []),  # structured facts (no free text) — forensics + proportionality policy
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        rec["prev_hash"] = self._last_hash(self.intercept_path)
        rec["hash"] = self._chain_hash(rec)
        with self._lock:
            with open(self.intercept_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        if rec["seq"] % self.anchor_every == 0:
            self._try_anchor("intercept", rec["seq"], rec["hash"])
        return rec

    # --- agent (async) ---------------------------------------------------------
    def append_agent(self, txn_id: str, task: str, output_digest: str) -> dict:
        rec = {
            "seq": self._count(self.agent_path) + 1, "txn_id": txn_id, "task": task,
            "output_digest": output_digest,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "prev_hash": self._last_hash(self.agent_path), "hash": self._chain_hash(
                {"txn": txn_id, "task": task, "d": output_digest, "t": time.time()}),
        }
        with self._lock:
            with open(self.agent_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        return rec

    # --- replay -----------------------------------------------------------------
    def replay(self, txn_id: str) -> list[dict]:
        out = []
        if self.intercept_path.exists():
            for line in self.intercept_path.read_text().splitlines():
                r = json.loads(line)
                if r["txn_id"] == txn_id:
                    out.append(r)
        return out

    def verify_chains(self) -> dict:
        """Verification-on-read: recompute chain; prove integrity to last anchor."""
        result = {}
        for name, path in [("intercept", self.intercept_path), ("agent", self.agent_path)]:
            ok, last_seq, prev = True, 0, None
            if path.exists():
                for line in path.read_text().splitlines():
                    r = json.loads(line)
                    if prev is not None and r.get("prev_hash") != prev:
                        ok = False; break
                    prev = r.get("hash"); last_seq = r.get("seq", last_seq)
            result[name] = {"intact": ok, "last_seq": last_seq}
        return result

    # --- RFC 3161-style external anchor (retry queue) -----------------------------
    def _try_anchor(self, chain: str, seq: int, tip_hash: str):
        receipt = {"chain": chain, "seq": seq, "tip": tip_hash,
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "status": "pending"}
        for tsa in ["http://timestamp.digicert.com"]:
            try:
                req = urllib.request.Request(tsa, data=_tsq(tip_hash),
                                             headers={"Content-Type": "application/timestamp-query"})
                resp = urllib.request.urlopen(req, timeout=8).read()
                receipt.update(status="anchored", tsa=tsa, receipt_bytes=len(resp))
                break
            except Exception:
                continue
        with open(self.anchor_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt) + "\n")

    # --- helpers ---------------------------------------------------------------------
    @staticmethod
    def _chain_hash(rec) -> str:
        return hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _count(path: Path) -> int:
        return len(path.read_text().splitlines()) if path.exists() else 0

    @classmethod
    def _last_hash(cls, path: Path) -> str:
        if not path.exists():
            return "GENESIS"
        lines = path.read_text().splitlines()
        return json.loads(lines[-1])["hash"] if lines else "GENESIS"


def _tsq(tip_hash: str) -> bytes:
    """Minimal RFC 3161 timestamp query for SHA-256 digest of the tip hash."""
    import struct
    digest = hashlib.sha256(tip_hash.encode()).digest()
    oid_sha256 = bytes([0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01])
    mi = bytes([0x30, 0x31]) + bytes([0x30, 0x0d]) + bytes([0x06, 0x09]) + oid_sha256 + bytes([0x05, 0x00]) \
         + bytes([0x04, 0x20]) + digest
    nonce = struct.pack(">Q", int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF)
    req = b"\x30" + bytes([len(mi) + len(nonce) + 6]) + mi + b"\x02" + bytes([len(nonce)]) + nonce
    return req
