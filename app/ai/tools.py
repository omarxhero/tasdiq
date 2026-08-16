"""Sealed tool belt — the LLM context is a PII-free, free-text-free zone.

Tools accept opaque IDs only (txn_id / msisdn hash). The vault resolves
hash -> raw number internally (Fernet-encrypted at rest, prototype key in .env;
production: KMS + bank-held key). Tool results returned to the model are
STRUCTURED FACTS ONLY (swap_age_hours, roaming_country, connectivity) — never
the raw number, never memos. Every call is logged with a purpose tag.
"""
from __future__ import annotations
import base64, hashlib, json, threading, time
from pathlib import Path
from cryptography.fernet import Fernet
from app.config import cfg, operator_for


class Vault:
    """hash -> encrypted raw msisdn map (prototype). Bank-held key in production."""
    def __init__(self, vault_file: Path, key: str):
        self.path = Path(vault_file)
        k = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        self._f = Fernet(k)
        self._map: dict[str, str] = {}
        if self.path.exists():
            blob = self._f.decrypt(self.path.read_bytes())
            self._map = json.loads(blob)
        self._lock = threading.Lock()

    def put(self, msisdn: str) -> str:
        h = "msisdn_" + hashlib.sha256(msisdn.encode()).hexdigest()[:20]
        with self._lock:
            self._map[h] = self._f.encrypt(msisdn.encode()).decode()
            self.path.write_bytes(self._f.encrypt(json.dumps(self._map).encode()))
        return h

    def resolve(self, msisdn_hash: str) -> str | None:
        with self._lock:
            enc = self._map.get(msisdn_hash)
        return self._f.decrypt(enc.encode()).decode() if enc else None


class ToolBelt:
    """4 read-only getters, rate-budgeted, Agent-Ledger-logged, PII-sealed."""
    def __init__(self, vault: Vault, nac, ledger, txn_index: dict, log=print):
        self.vault, self.nac, self.ledger, self.txn_index = vault, nac, ledger, txn_index
        self.log = log
        self.calls = 0
        self.rate_budget = 20          # protects NaC sandbox quota

    def _budget(self):
        self.calls += 1
        if self.calls > self.rate_budget:
            raise RuntimeError("tool-belt rate budget exceeded")

    def _structured_swap(self, msisdn_hash: str):
        self._budget()
        raw = self.vault.resolve(msisdn_hash)
        if not raw:
            return {"error": "unknown hash"}
        sig = self.nac.sim_swap(raw, max_age_hours=24, deadline_remaining=3.0)
        return {"msisdn_hash": msisdn_hash,
                "swapped": bool(sig.value and sig.value.get("swapped")),
                "operator": operator_for(raw), "signal_confidence": sig.confidence}

    def _structured_status(self, msisdn_hash: str):
        self._budget()
        raw = self.vault.resolve(msisdn_hash)
        if not raw:
            return {"error": "unknown hash"}
        roam = self.nac.roaming(raw, deadline_remaining=3.0)
        v = roam.value or {}
        return {"msisdn_hash": msisdn_hash, "roaming": v.get("roaming"),
                "country": (v.get("countryName") or [None])[0],
                "connectivity_hint": v.get("lastStatusTime")}

    def camara_probe_for_txn(self, txn_id: str):
        """Investigation entry: txn -> hash -> sealed CAMARA re-query (structured facts out)."""
        h = self.txn_index.get(txn_id)
        if not h:
            return {"txn_id": txn_id, "error": "not found"}
        out = {"txn_id": txn_id, "sim_swap": self._structured_swap(h),
               "device_status": self._structured_status(h), "ts": time.time()}
        self.log(f"[TOOLBELT][investigation] txn={txn_id} -> structured facts only")
        self.ledger.append_agent(txn_id, "toolbelt_investigation",
                                 hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest())
        return out

    def ledger_projection(self, txn_id: str) -> dict:
        """Memo-free projection: structured decision record only (no free text)."""
        recs = self.ledger.replay(txn_id)
        self.log(f"[TOOLBELT][copilot] txn={txn_id} ledger projection")
        return {"records": recs[:5]}
