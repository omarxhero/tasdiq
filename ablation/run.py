"""Ablation study — SYNTHETIC validation framework (labeled, not production evidence).

Splits: TUNE (150, seed 2026), HELD-OUT (50, seed 777 — never used for rule work),
BOUNDARY (12 exact-threshold cases: amounts at exactly 20x, attempts at exactly 5,
SIM-swap confidence at exactly 0.9). Same distributions per split; seeds differ.
Arms: bank behavioral only / telecom only / full blend. Offline, deterministic.
Run: python ablation/run.py
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.signals.nac import Signal
from app.engine.weighting import Behavioral, evaluate
from app.policy import DEFAULT_BANK_A


def build_cases(rng, n_a, n_b, n_c):
    """Feature-jittered labeled cases — identical distributions for every split."""
    cases = []
    def conf(hi=1.0, lo=0.85):
        return round(rng.uniform(lo, hi), 2)

    # A: SIM-swap takeover — the swap is the crime; behavior looks normal to the bank.
    for _ in range(n_a):
        b = Behavioral(
            beneficiary_first_seen_minutes=rng.randint(1000, 525600),
            attempts_last_hour=rng.randint(1, 2),
            amount_vs_mean=round(rng.uniform(8.0, 85.0), 1),
            declared_multi_sim=False)
        nv = "MISMATCH" if rng.random() < 0.75 else "MATCH"
        swap_conf = 1.0 if rng.random() < 0.85 else 0.9
        ds_conf = 0.30 if rng.random() < 0.15 else conf()
        cases.append(("fraud", "A",
                      [Signal("SIM_SWAP", {"swapped": True}, swap_conf, 40.0),
                       Signal("NUMBER_VERIFY", nv, conf(), 25.0 if nv == "MISMATCH" else 0.0),
                       Signal("DEVICE_STATUS", {"roaming": rng.random() < 0.2}, ds_conf, 0.0)],
                      b))

    # B: snatch-and-run — behavioral decisive, telecom green.
    for _ in range(n_b):
        cases.append(("fraud", "B",
                      [Signal("SIM_SWAP", {"swapped": False}, conf(), 0.0),
                       Signal("NUMBER_VERIFY", "MATCH", conf(), 0.0),
                       Signal("DEVICE_STATUS", {"roaming": False}, conf(), 0.0)],
                      Behavioral(beneficiary_first_seen_minutes=rng.randint(1, 5),
                                 attempts_last_hour=rng.randint(3, 9),
                                 amount_vs_mean=round(rng.uniform(22.0, 90.0), 1),
                                 declared_multi_sim=rng.random() < 0.2)))

    # C: clean — includes tricky-but-legitimate patterns that must NOT flag.
    for _ in range(n_c):
        tricky = rng.random() < 0.35
        cases.append(("clean", "C",
                      [Signal("SIM_SWAP", {"swapped": False}, conf(), 0.0),
                       Signal("NUMBER_VERIFY", "MATCH", conf(), 0.0),
                       Signal("DEVICE_STATUS", {"roaming": rng.random() < 0.25}, conf(), 0.0)],
                      Behavioral(beneficiary_first_seen_minutes=rng.randint(2, 90) if tricky else rng.randint(2000, 525600),
                                 attempts_last_hour=rng.randint(1, 2),
                                 amount_vs_mean=round(rng.uniform(1.5, 9.0), 1) if tricky else round(rng.uniform(0.2, 3.0), 1),
                                 declared_multi_sim=rng.random() < 0.3)))
    return cases


TUNE = build_cases(random.Random(2026), 52, 52, 46)   # 150 — used when validating rules
HELD = build_cases(random.Random(777), 18, 17, 15)    # 50  — held-out, different seed
HARD = []                                             # exact-threshold boundary cases
for amt in (20.0, 19.9, 20.1):
    for att in (5, 4):
        HARD.append(("fraud", "H",
                     [Signal("SIM_SWAP", {"swapped": False}, 1.0, 0.0),
                      Signal("NUMBER_VERIFY", "MATCH", 1.0, 0.0),
                      Signal("DEVICE_STATUS", {"roaming": False}, 1.0, 0.0)],
                     Behavioral(5, att, amt, False)))
for sc in (1.0, 0.9):
    HARD.append(("fraud", "H",
                 [Signal("SIM_SWAP", {"swapped": True}, sc, 40.0),
                  Signal("NUMBER_VERIFY", "MATCH", 1.0, 0.0),
                  Signal("DEVICE_STATUS", {"roaming": False}, 1.0, 0.0)],
                 Behavioral(9999, 1, 5.0, False)))
CASES = TUNE + HELD + HARD


def run_arm(arm, cases):
    tp = fn = fp = tn = 0
    for label, _, signals, b in cases:
        policy = DEFAULT_BANK_A["rules"]
        if arm == "bank_only":
            sigs = []
            policy = {**DEFAULT_BANK_A["rules"], "min_signal_coverage": 0.0}
        elif arm == "telecom_only":
            sigs = signals; b = Behavioral(9999, 1, 1.0, False)
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


def evaluate_split(cases, label):
    results = [run_arm(a, cases) for a in ("bank_only", "telecom_only", "full_blend")]
    full, bank = results[2], results[0]
    print(f"\n--- {label} (n={len(cases)}) ---")
    print(f"{'arm':14} {'TP':>3} {'FN':>3} {'FP':>3} {'TN':>3} {'prec':>5} {'rec':>5} {'f1':>5}")
    for r in results:
        print(f"{r['arm']:14} {r['TP']:>3} {r['FN']:>3} {r['FP']:>3} {r['TN']:>3} "
              f"{r['precision']:>5} {r['recall']:>5} {r['f1']:>5}")
    inc = round(full["recall"] - bank["recall"], 2)
    print(f"incremental recall (telecom): {inc:+.2f}")
    return results, inc


res_tune, inc_tune = evaluate_split(TUNE, "TUNE (150, seed 2026)")
res_held, inc_held = evaluate_split(HELD, "HELD-OUT (50, seed 777)")
res_hard, inc_hard = evaluate_split(HARD, "BOUNDARY HARD SET (exact-threshold cases)")
print("\nNOTE: synthetic validation framework — partner-operator data is Phase 1.")

out_path = Path(__file__).resolve().parent.parent / "evidence" / "ablation_results.json"
out_path.write_text(json.dumps(
    {"splits": {
        "tune": {"n": len(TUNE), "results": res_tune, "incremental_recall_telecom": inc_tune},
        "held_out": {"n": len(HELD), "results": res_held, "incremental_recall_telecom": inc_held},
        "boundary_hard": {"n": len(HARD), "results": res_hard, "incremental_recall_telecom": inc_hard}},
     "note": "Synthetic validation: tune / held-out / boundary splits, feature-varied, seeded. "
             "Partner-operator data = Phase 1. Labeled as validation, not production evidence."},
    indent=2))
print(f"saved -> {out_path}")
