"""Ablation study — SYNTHETIC validation framework (labeled, not production evidence).

Arms: (1) bank behavioral signals only, (2) telecom signals only, (3) full blend.
Dataset: 200 synthetic labeled cases (70 SIM-swap takeover, 70 snatch-&-run, 60 clean),
feature-jittered per case (amount ratios, payee ages, velocities, confidences,
degraded-signal variants) so no two cases are identical. Seeded => reproducible.
Offline (stub signals) so it runs instantly and deterministically.
Run: python ablation/run.py
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.signals.nac import Signal
from app.engine.weighting import Behavioral, evaluate
from app.policy import DEFAULT_BANK_A

rng = random.Random(2026)

def conf(hi=1.0, lo=0.85):
    return round(rng.uniform(lo, hi), 2)

CASES = []

# A (70): SIM-swap takeover — telecom decisive. Behavioral varies: some swaps ride on
# otherwise-normal activity (bank alone is blind to them), some combine with anomalies.
for _ in range(70):
    # ATO pattern: the swap is the crime — behavior looks normal to the bank alone
    b = Behavioral(
        beneficiary_first_seen_minutes=rng.randint(1000, 525600),
        attempts_last_hour=rng.randint(1, 2),
        amount_vs_mean=round(rng.uniform(8.0, 85.0), 1),
        declared_multi_sim=False)
    nv = "MISMATCH" if rng.random() < 0.75 else "MATCH"
    # realistic swap-check confidences: live 1.0, cached fallback 0.9
    swap_conf = 1.0 if rng.random() < 0.85 else 0.9
    # occasionally Device Status is degraded (conf 0.30) — engine must still catch the swap
    ds_conf = 0.30 if rng.random() < 0.15 else conf()
    CASES.append(("fraud", "A",
                  [Signal("SIM_SWAP", {"swapped": True}, swap_conf, 40.0),
                   Signal("NUMBER_VERIFY", nv, conf(), 25.0 if nv == "MISMATCH" else 0.0),
                   Signal("DEVICE_STATUS", {"roaming": rng.random() < 0.2}, ds_conf, 0.0)],
                  b))

# B (70): snatch-and-run — behavioral decisive, telecom green.
for _ in range(70):
    CASES.append(("fraud", "B",
                  [Signal("SIM_SWAP", {"swapped": False}, conf(), 0.0),
                   Signal("NUMBER_VERIFY", "MATCH", conf(), 0.0),
                   Signal("DEVICE_STATUS", {"roaming": False}, conf(), 0.0)],
                  Behavioral(beneficiary_first_seen_minutes=rng.randint(1, 5),
                             attempts_last_hour=rng.randint(3, 9),
                             amount_vs_mean=round(rng.uniform(22.0, 90.0), 1),
                             declared_multi_sim=rng.random() < 0.2)))

# C (60): clean — includes genuinely tricky-but-legitimate patterns that must NOT flag:
# moderately unusual amounts to recent payees, declared dual-SIM, roaming travelers.
for _ in range(60):
    tricky = rng.random() < 0.35
    CASES.append(("clean", "C",
                  [Signal("SIM_SWAP", {"swapped": False}, conf(), 0.0),
                   Signal("NUMBER_VERIFY", "MATCH", conf(), 0.0),
                   Signal("DEVICE_STATUS", {"roaming": rng.random() < 0.25}, conf(), 0.0)],
                  Behavioral(beneficiary_first_seen_minutes=rng.randint(2, 90) if tricky else rng.randint(2000, 525600),
                             attempts_last_hour=rng.randint(1, 2),
                             amount_vs_mean=round(rng.uniform(1.5, 9.0), 1) if tricky else round(rng.uniform(0.2, 3.0), 1),
                             declared_multi_sim=rng.random() < 0.3)))

unique = len({str(c[2]) + str(c[3]) for c in CASES})
print(f"cases: {len(CASES)}, unique feature-vectors: {unique}")
assert len(CASES) == 200 and unique >= 190, "cases must be varied"

def run_arm(arm):
    tp = fn = fp = tn = 0
    for label, _, signals, b in CASES:
        policy = DEFAULT_BANK_A["rules"]
        if arm == "bank_only":
            # the bank alone: no telecom signals exist for it, so coverage rule
            # (a Tasdiq-integration concept) must not apply to this arm
            sigs = []
            policy = {**DEFAULT_BANK_A["rules"], "min_signal_coverage": 0.0}
        elif arm == "telecom_only":
            sigs = signals; b = Behavioral(9999, 1, 1.0, False)   # behavioral zeroed
        else:
            sigs = signals
        out = evaluate(sigs, b, policy)
        flagged = out["decision"] in ("DECLINE", "ESCALATE")
        if label == "fraud" and flagged: tp += 1
        elif label == "fraud" and not flagged: fn += 1
        elif label == "clean" and flagged: fp += 1
        else: tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"arm": arm, "TP": tp, "FN": fn, "FP": fp, "TN": tn,
            "precision": round(prec, 2), "recall": round(rec, 2), "f1": round(f1, 2)}

results = [run_arm(a) for a in ("bank_only", "telecom_only", "full_blend")]
print(f"{'arm':14} {'TP':>3} {'FN':>3} {'FP':>3} {'TN':>3} {'prec':>5} {'rec':>5} {'f1':>5}")
for r in results:
    print(f"{r['arm']:14} {r['TP']:>3} {r['FN']:>3} {r['FP']:>3} {r['TN']:>3} "
          f"{r['precision']:>5} {r['recall']:>5} {r['f1']:>5}")
full, bank = results[2], results[0]
print(f"\nIncremental recall from telecom signals: {full['recall'] - bank['recall']:+.2f}")
print("NOTE: synthetic validation framework (200 seeded, feature-varied cases) — partner-operator data is Phase 1.")

out_path = Path(__file__).resolve().parent.parent / "evidence" / "ablation_results.json"
out_path.write_text(json.dumps(
    {"n_cases": len(CASES), "composition": {"sim_swap_takeover": 70, "snatch_and_run": 70, "clean": 60},
     "seed": 2026, "results": results,
     "incremental_recall_telecom": round(full["recall"] - bank["recall"], 2),
     "note": "Synthetic validation framework (200 seeded, feature-varied cases: jittered amounts, "
             "payee ages, velocities, degraded-signal variants, tricky-but-legitimate cleans). "
             "Partner-operator data = Phase 1. Labeled as validation, not production evidence."},
    indent=2))
print(f"saved -> {out_path}")
