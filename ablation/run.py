"""Ablation study — SYNTHETIC validation framework (labeled, not production evidence).

Arms: (1) bank behavioral signals only, (2) telecom signals only, (3) full blend.
Dataset: 30 synthetic labeled cases (10 SIM-swap takeover, 10 snatch-&-run, 10 clean).
Offline (stub signals) so it runs instantly and deterministically.
Run: python ablation/run.py
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.signals.nac import Signal
from app.engine.weighting import Behavioral, evaluate
from app.policy import DEFAULT_BANK_A

CASES = []
for i in range(10):   # A: sim-swap takeover (telecom decisive)
    CASES.append(("fraud", "A",
                  [Signal("SIM_SWAP", {"swapped": True}, 1.0, 40.0),
                   Signal("NUMBER_VERIFY", "MISMATCH", 1.0, 25.0),
                   Signal("DEVICE_STATUS", {"roaming": False}, 1.0, 0.0)],
                  Behavioral(9999, 1, 1.0, False)))
for i in range(10):   # B: snatch-and-run (behavioral decisive, telecom green)
    CASES.append(("fraud", "B",
                  [Signal("SIM_SWAP", {"swapped": False}, 1.0, 0.0),
                   Signal("NUMBER_VERIFY", "MATCH", 1.0, 0.0),
                   Signal("DEVICE_STATUS", {"roaming": False}, 1.0, 0.0)],
                  Behavioral(1, 6, 45.0, False)))
for i in range(10):   # C: clean
    CASES.append(("clean", "C",
                  [Signal("SIM_SWAP", {"swapped": False}, 1.0, 0.0),
                   Signal("NUMBER_VERIFY", "MATCH", 1.0, 0.0),
                   Signal("DEVICE_STATUS", {"roaming": False}, 1.0, 0.0)],
                  Behavioral(525600, 1, 1.0, False)))

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
print("NOTE: synthetic validation framework (~30 labeled cases) — partner-operator data is Phase 1.")

out_path = Path(__file__).resolve().parent.parent / "evidence" / "ablation_results.json"
out_path.write_text(json.dumps(
    {"results": results,
     "note": "Synthetic validation framework (~30 cases). Partner-operator data = Phase 1. "
             "Labeled as validation, not production evidence."}, indent=2))
print(f"saved -> {out_path}")
