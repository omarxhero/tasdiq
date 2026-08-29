"""L2.5 confidence weighting + behavioral features + HARD RULES.

Weighted risk = Σ(risk_i × confidence_i) / Σ(confidence_i)
Hard rules (regulator-correct, always win over the weighted score):
  1. SIM swap < 1h AND amount > instant_multiplier × mean  -> DECLINE (early exit, L2 Phase 1)
  2. degraded signal + amount/velocity deviation           -> ESCALATE (never approve at 0.30)
  3. primary-signal (SIM Swap) loss + any anomaly           -> ESCALATE (timeout-approve path closed)
  4. coverage below bank minimum                            -> ESCALATE
  5. snatch-&-run pattern (telecom green + behavioral)      -> ESCALATE, biometric-only step-up
"""
from __future__ import annotations
from dataclasses import dataclass
from app.signals.nac import Signal


@dataclass
class Behavioral:
    beneficiary_first_seen_minutes: float
    attempts_last_hour: int
    amount_vs_mean: float          # amount / account_mean
    declared_multi_sim: bool

    @property
    def anomaly(self) -> bool:
        return (self.beneficiary_first_seen_minutes <= 5
                or self.amount_vs_mean >= 20
                or self.attempts_last_hour >= 5)


def weighted_risk(signals: list[Signal]) -> float:
    num = sum(s.risk * s.confidence for s in signals)
    den = sum(s.confidence for s in signals)
    return round(num / den, 2) if den > 0 else 0.0


def coverage(signals: list[Signal]) -> float:
    """Effective coverage: signals still contributing (confidence > 0) count —
    a 0.30-confidence signal informs the decision; a 0.0 signal does not."""
    contributing = [s for s in signals if s.confidence > 0]
    return round(len(contributing) / len(signals), 2) if signals else 0.0


def behavioral_risk(b: Behavioral) -> float:
    risk = 0.0
    if b.beneficiary_first_seen_minutes <= 5:  risk += 30.0   # payee added moments ago
    if b.amount_vs_mean >= 20:                  risk += 25.0
    if b.attempts_last_hour >= 5:               risk += 15.0
    return risk


def evaluate(signals: list[Signal], b: Behavioral, policy: dict) -> dict:
    """Returns {decision, band, weighted_risk, total_risk, reasons, step_up}."""
    wr = weighted_risk(signals)
    total = min(100.0, wr + behavioral_risk(b))
    cov = coverage(signals)
    reasons = [s.as_dict() for s in signals]

    sim = next((s for s in signals if s.name == "SIM_SWAP"), None)

    # Rule 0: live SIM swap is never a clean approve (band SIM_SWAP_RECENT)
    if telecom_swap_live := (sim is not None and isinstance(sim.value, dict)
                             and sim.value.get("swapped") and sim.confidence >= 0.9):
        if total >= policy.get("decline_gte", 80):
            return _out("DECLINE", "SIM_SWAP_HIGH_RISK", wr, total, reasons, [], [])
        return _out("ESCALATE", "SIM_SWAP_RECENT", wr, total, reasons,
                    ["WEBAUTHN", "IN_APP_BIOMETRIC"], ["SMS", "VOICE"])
    # Rule 3 (checked before generic rule 2): primary signal lost + anomaly
    if sim is not None and sim.confidence == 0.0 and b.anomaly:
        return _out("ESCALATE", "PRIMARY_SIGNAL_LOSS", wr, total, reasons,
                    ["IN_APP_BIOMETRIC", "WEBAUTHN"], ["SMS", "VOICE"])
    # Rule 5 (before generic rule 2): snatch-&-run — telecom green + behavioral anomaly
    telecom_green = (sim is not None and isinstance(sim.value, dict)
                     and not sim.value.get("swapped"))
    if telecom_green and b.anomaly and b.amount_vs_mean >= 20:
        return _out("ESCALATE", "BEHAVIORAL_ANOMALY", wr, total, reasons,
                    ["IN_APP_BIOMETRIC"], ["SMS"])   # stolen unlocked device receives SMS too
    # Rule 2: degraded signal + anomaly -> escalate (never approve at 0.30)
    degraded = [s for s in signals if s.degradation and s.confidence < 1.0]
    if degraded and b.anomaly:
        return _out("ESCALATE", "DEGRADED_SIGNAL_ANOMALY", wr, total, reasons,
                    ["IN_APP_BIOMETRIC", "WEBAUTHN"], ["SMS", "VOICE"])
    # Rule 4: coverage
    if cov < policy.get("min_signal_coverage", 0.5):
        return _out("ESCALATE", "COVERAGE_LOW", wr, total, reasons,
                    ["IN_APP_BIOMETRIC", "WEBAUTHN"], [])
    # thresholds (+ jitter applied by policy loader)
    if total >= policy.get("decline_gte", 80):
        return _out("DECLINE", "WEIGHTED_RISK_HIGH", wr, total, reasons, [], [])
    if total >= policy.get("escalate_gte", 55):
        return _out("ESCALATE", "WEIGHTED_RISK_BAND", wr, total, reasons,
                    ["SMS_OTP"], [])
    return _out("APPROVE", "CLEAN", wr, total, reasons, [], [])


def _out(decision, band, wr, total, reasons, allowed, prohibited):
    return {"decision": decision, "band": band, "weighted_risk": wr,
            "total_risk": total, "reasons": reasons,
            "step_up": {"allowed": allowed, "prohibited": prohibited}}
