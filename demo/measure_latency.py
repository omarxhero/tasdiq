"""Measured latency vs. the 450ms budget — live Nokia NaC sandbox.
Reports p50/p95 end-to-end (incl. sandbox RTT) and internal execution,
plus timeout (BUDGET_MISS/UNAVAILABLE) and cached-fallback rates.
Run: python demo/measure_latency.py  (needs .env keys; ~15 live calls)
"""
import json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.signals.nac import NacClient
from app.engine.decide import DecisionEngine
from app.policy import DEFAULT_BANK_A
from app import policy as P
from pathlib import Path as _P
_keys = _P(__file__).resolve().parent.parent / "keys"
if not list(_keys.glob("*.key")):
    P.gen_keypair(_keys / "maker.key"); P.gen_keypair(_keys / "checker.key")
_b1 = P.sign_policy(dict(DEFAULT_BANK_A), "maker", _keys)
bundle = P.sign_policy(_b1, "checker", _keys)
from app.config import cfg

SCEN = [
    ("clean",      {"msisdn": "+99999991001", "amount": 250,   "account_mean": 400,  "beneficiary_first_seen_minutes": 525600, "attempts_last_hour": 1}),
    ("swap_spike", {"msisdn": "+99999991000", "amount": 52000, "account_mean": 1000, "beneficiary_first_seen_minutes": 3,     "attempts_last_hour": 2}),
    ("dualsim",    {"msisdn": "+99999991001", "amount": 6000,  "account_mean": 400,  "beneficiary_first_seen_minutes": 2,     "attempts_last_hour": 1, "declared_multi_sim": True}),
    ("snatch",     {"msisdn": "+99999991001", "amount": 18000, "account_mean": 400,  "beneficiary_first_seen_minutes": 1,     "attempts_last_hour": 6}),
]
eng = DecisionEngine(NacClient())
rows = []
N_ROUNDS = 4
for rnd in range(N_ROUNDS):
    for name, base in SCEN:
        req = {"txn_id": f"lat-{rnd}-{name}", **base}
        t0 = time.perf_counter()
        out = eng.decide(dict(req), dict(bundle))
        e2e = int((time.perf_counter() - t0) * 1000)
        reasons = out["reasons"]
        rows.append({
            "scenario": name, "decision": out["decision"], "band": out["band"],
            "end_to_end_ms": e2e, "internal_ms": out["latency"]["internal_ms"],
            "budget_ms": out["latency"]["budget_ms"],
            "budget_miss": any("BUDGET_MISS" in (r.get("degradation") or "") for r in reasons),
            "unavailable": any("UNAVAILABLE" in (r.get("degradation") or "") for r in reasons),
            "cached_fallback": any("CACHED_FALLBACK" in (r.get("degradation") or "") for r in reasons),
            "any_live": any(r.get("degradation") in (None, "") for r in reasons),
        })
        time.sleep(1.0)

def pct(vals, p):
    v = sorted(vals)
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)] if v else 0

e2e = [r["end_to_end_ms"] for r in rows]
internal = [r["internal_ms"] for r in rows]
summary = {
    "n": len(rows),
    "p50_end_to_end_ms": pct(e2e, 50), "p95_end_to_end_ms": pct(e2e, 95),
    "max_end_to_end_ms": max(e2e), "min_end_to_end_ms": min(e2e),
    "p50_internal_ms": pct(internal, 50), "p95_internal_ms": pct(internal, 95),
    "budget_450ms_met_rate": round(sum(1 for v in e2e if v <= 450) / len(e2e), 2),
    "timeout_rate": round(sum(1 for r in rows if r["budget_miss"] or r["unavailable"]) / len(rows), 2),
    "fallback_rate": round(sum(1 for r in rows if r["cached_fallback"]) / len(rows), 2),
    "note": ("Shared Nokia dev sandbox: end-to-end is dominated by sandbox RTT. Internal "
             "execution is the engine itself. Production banks call NaC from their own VPC "
             "(sub-50ms RTT). Degradations are labeled, never silent."),
}
print(f"{'scen':10} {'dec':8} {'e2e':>5} {'int':>4}  flags")
for r in rows:
    flags = [k for k in ("budget_miss", "unavailable", "cached_fallback") if r[k]]
    print(f"{r['scenario']:10} {r['decision']:8} {r['end_to_end_ms']:>5} {r['internal_ms']:>4}  {','.join(flags) or 'live'}")
print(json.dumps(summary, indent=2))
out_path = Path(__file__).resolve().parent.parent / "evidence" / "latency_measurements.json"
out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
print(f"saved -> {out_path}")
