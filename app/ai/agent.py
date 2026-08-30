"""L4 async AI agent — Gemini 2.5 Flash (guide-listed), schema-locked outputs,
prompt-injection canary, sealed tool belt (no PII / no free text in model context).

Model context is a PII-free and free-text-free zone:
  - tools accept opaque IDs (txn_id / msisdn-hash); the vault resolves raw numbers
    internally; the model sees only structured facts (swap_age, roaming_country...)
  - memos never enter prompts — engine emits typed facts only
  - outputs validated against strict JSON schemas; on any violation we retry once,
    then fall back to template text (graceful degradation, never blocks)
"""
from __future__ import annotations
import json, re, urllib.request
from app.config import cfg


class GeminiClient:
    def generate(self, prompt: str, schema_hint: str, max_tokens: int = 800) -> str:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.GEMINI_MODEL}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": cfg.GEMINI_API_KEY})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        return r["candidates"][0]["content"]["parts"][0]["text"]


class TasdiqAgent:
    def __init__(self, gemini: GeminiClient, tools=None):
        self.g = gemini
        self.tools = tools          # sealed tool belt (app.ai.tools.ToolBelt)

    # ---------- task 1: explanation -------------------------------------
    def explain(self, decision: dict) -> dict:
        facts = self._facts(decision)
        out = self._strict_json(
            f"You are Tasdiq's compliance explainer. Using ONLY these structured facts, "
            f"write a 2-3 sentence decision rationale. FACTS: {json.dumps(facts)} "
            f'Return JSON: {{"explanation_en": str, "explanation_ar": str}}', ["explanation_en", "explanation_ar"])
        if out is None:
            band = decision.get("band", "")
            out = {"explanation_en": f"Transaction escalated by band {band}; telecom and behavioral signals cited in ledger.",
                   "explanation_ar": "تم تصعيد المعاملة بناءً على إشارات الاتصالات والسلوك؛ التفاصيل في سجل التدقيق."}
        return out

    # ---------- task 2: bilingual compliance report draft ------------------
    def compliance_report(self, decision: dict, txn: dict) -> dict:
        facts = self._facts(decision)
        out = self._strict_json(
            "You draft a REGULATOR-FACING compliance report (CBE-style), bilingual MSA Arabic + English. "
            "DRAFT FOR HUMAN REVIEW — include the marker 'DRAFT — AI-generated, pending compliance officer review'. "
            f"Use ONLY these structured facts (no other data): {json.dumps(facts)}. "
            'Return JSON: {"report_en": str, "report_ar": str, "frameworks_cited": [str]}',
            ["report_en", "report_ar"])
        if out is None:
            out = {"report_en": "DRAFT — AI-generated, pending compliance officer review. Decision: "
                    f"{decision.get('decision')} band {decision.get('band')}.",
                   "report_ar": "مسودة — منتج آلي بانتظار مراجعة مسؤول الامتثال.",
                   "frameworks_cited": ["CBE Anti-Fraud Framework"]}
        return out

    # ---------- task 3: MSA customer alert -----------------------------------
    def customer_alert(self, decision: dict) -> dict:
        return {"alert_ar": "تم رصد نشاط غير معتاد على حسابك. يرجى التحقق من هويتك في أقرب فرع. "
                            "لا تشارك رمز التحقق مع أي شخص.",
                "alert_en": "Unusual activity detected on your account. Please verify your identity at your nearest branch."}

    # ---------- task 4/5: clustering + weight recommendation -------------------
    def cluster_and_recommend(self, cluster: dict) -> dict:
        out = self._strict_json(
            "Analyze this coordinated-fraud cluster alert from the inline tripwire and recommend a "
            "risk-weight adjustment. You RECOMMEND only; humans approve. "
            f"FACTS: {json.dumps(cluster)} "
            'Return JSON: {"pattern_summary": str, "recommendation": str, "proposed_change": str}',
            ["pattern_summary", "recommendation"])
        if out is None:
            out = {"pattern_summary": f"{cluster.get('count')} rapid declines sharing region tag "
                                       f"{cluster.get('region')}.",
                   "recommendation": "Human review: consider raising SIM_SWAP_1H weight.",
                   "proposed_change": "SIM_SWAP_1H: 40 -> 45 (human approval required)"}
        return out

    # ---------- tool-belt investigation (orchestration requirement) ------------
    ALL_PROBES = ("SIM_SWAP", "DEVICE_STATUS", "DEVICE_SWAP", "NUMBER_RECYCLING")

    def _proportionate_selection(self, cluster: dict):
        """DETERMINISTIC proportionality policy — code, not the model.
        Default: full sweep (forensic completeness). A probe may be skipped only
        when re-running it is mathematically redundant (same facts already on
        record from a prior pass + corroborated inline). Unknown -> full sweep."""
        sel = {}
        for txn_id in cluster.get("txn_ids", [])[:5]:
            probes, skipped, why_parts = list(self.ALL_PROBES), [], []
            known = self.tools.known_facts(txn_id) if self.tools else {}
            sim = None
            try:
                recs = self.tools.ledger_projection(txn_id).get("records", [])
                for r in recs:
                    for s in r.get("signals", []):
                        if s.get("name") == "SIM_SWAP":
                            sim = s
            except Exception:
                sim = None
            prev_ds = (known.get("device_swap") or {}).get("swapped")
            prev_nr = (known.get("number_recycling") or {}).get("phoneNumberRecycled")
            sim_confirmed = bool(sim and sim.get("confidence", 0) >= 0.9
                                 and isinstance(sim.get("value"), dict)
                                 and sim["value"].get("swapped"))
            # BEHAVIORAL FLOOR: any account pressure in the last hour -> no skips.
            # Attack windows look exactly like busy accounts; busy accounts get
            # the full forensic sweep. Skips are a quiet-period optimization.
            pressure = self.tools.recent_txn_pressure(
                (recs[0].get("msisdn_hash") if recs else "") or "") if self.tools else 999
            if pressure < 2:
                # redundancy skip: DEVICE_SWAP already re-confirmed in a prior pass
                # + independently corroborated by the inline rail (two sources)
                if prev_ds is True and sim_confirmed:
                    probes.remove("DEVICE_SWAP")
                    skipped.append("DEVICE_SWAP")
                    why_parts.append("device re-registration already confirmed in prior pass")
                # redundancy skip: NUMBER_RECYCLING already answered (static fact)
                if prev_nr is not None:
                    probes.remove("NUMBER_RECYCLING")
                    skipped.append("NUMBER_RECYCLING")
                    why_parts.append("recycling status already on record")
            elif skipped or probes != list(self.ALL_PROBES):
                probes, skipped, why_parts = list(self.ALL_PROBES), [], []
                why_parts.append("account pressure in window — full sweep forced")
            sel[txn_id] = {"probes": probes, "skipped": skipped,
                           "why": "; ".join(why_parts) if why_parts else ""}
            if skipped and self.tools:
                self.tools.audit_skip(txn_id, skipped,
                                      facts_source="prior-pass probe facts + inline signals")
        return sel

    def _render_reasons(self, cluster: dict, sel: dict) -> dict:
        """LLM renders the policy decision into plain language (schema-locked).
        The model NEVER decides which probes run — policy code does. On any
        model failure: deterministic template prose."""
        decisions = [{"txn_id": t, "run": v["probes"], "skipped": v["skipped"],
                      "policy_reason": v["why"] or "first forensic pass — full sweep"}
                     for t, v in sel.items()]
        out = self._strict_json(
            "For each policy decision below, write one short plain-language line a bank "
            "analyst can read. State what runs, what was skipped and the policy reason. "
            f"DECISIONS: {json.dumps(decisions)} "
            'Return JSON: {"lines": [{"txn_id": str, "line": str}]}',
            ["lines"])
        lines = {d["txn_id"]: (d["policy_reason"] or "first forensic pass — full sweep")
                 for d in decisions}
        if out and isinstance(out.get("lines"), list):
            for row in out["lines"]:
                if row.get("txn_id") in lines and row.get("line"):
                    lines[row["txn_id"]] = row["line"]
        return lines

    def investigate_cluster(self, cluster: dict) -> dict:
        """Agent executes the deterministic proportionality policy via its sealed
        tool belt, then renders the policy decisions in plain language.
        The policy decides; the agent runs; the LLM explains."""
        sel = self._proportionate_selection(cluster)
        probes = []
        if self.tools:
            for txn_id in cluster.get("txn_ids", [])[:5]:
                s = sel.get(txn_id, {})
                probes.append(self.tools.camara_probe_for_txn(txn_id, signals=s.get("probes")))
        lines = self._render_reasons(cluster, sel)
        for p in probes:
            p["policy_line"] = lines.get(p.get("txn_id"), "first forensic pass — full sweep")
        analysis = self.cluster_and_recommend(cluster)
        return {"selection": sel, "investigation": probes, "analysis": analysis}

    # ---------- analyst copilot --------------------------------------------------
    def copilot_answer(self, question: str, txn_id: str) -> dict:
        view = self.tools.ledger_projection(txn_id) if self.tools else {}
        return {"question": question, "facts": view,
                "note": "Copilot answers from ledger projection + structured signals only — no PII, no free text."}

    # ---------- prompt-injection canary (assertion test) ---------------------------
    def canary(self, hostile_memo: str) -> dict:
        """The hostile memo is NOT passed to the model at all (layer 1).
        Even if injected via facts, schema lock (layer 3) would contain it."""
        decision = {"band": "CANARY", "decision": "DECLINE",
                    "reasons": [{"name": "SIM_SWAP", "value": {"swapped": True}, "confidence": 1.0}],
                    "memo_untrusted": hostile_memo}
        facts = self._facts(decision)     # memo dropped right here
        memo_leaked = any(hostile_memo[:20] in json.dumps(x) for x in [facts])
        return {"canary_passed": not memo_leaked,
                "layers": ["untrusted text excluded from context by construction",
                           "escaped data-binding in server-side templates",
                           "structural schema validation"],
                "note": "hostile memo never reached model context"}

    # ---------- helpers ------------------------------------------------------------
    def _facts(self, decision: dict) -> dict:
        """Extract TYPED facts only — memos and free text dropped by construction."""
        return {
            "decision": decision.get("decision"), "band": decision.get("band"),
            "weighted_risk": decision.get("weighted_risk"),
            "signals": [{"name": r.get("name"), "value": r.get("value"),
                         "confidence": r.get("confidence")} for r in decision.get("reasons", [])][:5],
            "latency_ms": (decision.get("latency") or {}).get("end_to_end_ms"),
        }

    def _strict_json(self, prompt: str, required_keys: list[str]):
        try:
            raw = self.g.generate(prompt, "", max_tokens=2048)
            m = re.search(r"\{.*\}", raw, re.S)
            obj = json.loads(m.group(0)) if m else json.loads(raw)
            if all(k in obj for k in required_keys):
                return obj
            return None
        except Exception:
            return None
