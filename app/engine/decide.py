"""L2 progressive decision engine — deadline-driven, early-exit.

Phase 1 (0–200ms budget): SIM Swap only; swap + amount > multiplier×mean -> DECLINE.
Phase 2: parallel Number Verify + Device Status + behavioral signals.
Dual latency reporting: end_to_end_ms (incl. sandbox RTT) and internal_ms
(external network excluded). Sandbox overhead shown, never hidden.
"""
from __future__ import annotations
import time
from app.config import cfg
from app.signals.nac import NacClient
from app.engine.weighting import Behavioral, evaluate
from app.policy import verify_bundle


class DecisionEngine:
    def __init__(self, nac: NacClient):
        self.nac = nac

    def decide(self, req: dict, bundle: dict) -> dict:
        t0 = time.perf_counter()
        deadline = cfg.DECISION_BUDGET_MS / 1000.0

        policy = verify_bundle(bundle)["rules"]   # tampered config -> exception -> REJECT
        mult = policy.get("instant_multiplier", 50)
        amount_vs_mean = (req["amount"] / req["account_mean"]) if req.get("account_mean") else 1.0

        # ---- Phase 1: SIM Swap only (early exit) --------------------------
        sim = self.nac.sim_swap(req["msisdn"], policy.get("swap_window_hours", 24),
                                deadline_remaining=deadline - (time.perf_counter() - t0))
        swapped_recent = bool(sim.value and sim.value.get("swapped"))
        if swapped_recent and amount_vs_mean > mult:
            return self._finish(req, t0, "DECLINE", "SIM_SWAP_INSTANT_PATTERN",
                                [sim.as_dict()], 0.0, policy, bundle,
                                ["WEBAUTHN", "IN_APP_BIOMETRIC"], ["SMS", "VOICE"])

        # ---- Phase 2: parallel + behavioral --------------------------------
        remaining = deadline - (time.perf_counter() - t0)
        nv = self.nac.number_verify(req["msisdn"], req.get("declared_multi_sim", False), remaining)
        roam = self.nac.roaming(req["msisdn"], remaining)
        b = Behavioral(
            beneficiary_first_seen_minutes=req.get("beneficiary_first_seen_minutes", 9999),
            attempts_last_hour=req.get("attempts_last_hour", 0),
            amount_vs_mean=amount_vs_mean,
            declared_multi_sim=req.get("declared_multi_sim", False),
        )
        result = evaluate([sim, nv, roam], b, policy)
        return self._finish(req, t0, result["decision"], result["band"], result["reasons"],
                            result["weighted_risk"], policy, bundle,
                            result["step_up"]["allowed"], result["step_up"]["prohibited"],
                            total_risk=result["total_risk"])

    def _finish(self, req, t0, decision, band, reasons, wr, policy, bundle,
                allowed, prohibited, total_risk=None):
        from app.policy import verify_bundle
        end_to_end = int((time.perf_counter() - t0) * 1000)
        external = sum(r.get("latency_ms", 0) for r in reasons)
        return {
            "txn_id": req.get("txn_id"), "decision": decision, "band": band,
            "weighted_risk": wr, "total_risk": total_risk if total_risk is not None else wr,
            "reasons": reasons,
            "step_up": {"allowed": allowed, "prohibited": prohibited},
            "policy_id": bundle.get("policy_id"),
            "policy_version_hash": verify_bundle(bundle)["policy_version_hash"],
            "latency": {"end_to_end_ms": end_to_end,
                        "internal_ms": max(0, end_to_end - external),
                        "external_network_ms": external,
                        "budget_ms": cfg.DECISION_BUDGET_MS},
        }
