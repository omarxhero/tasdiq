# Tasdiq تصديق — Telecom-Verified AI Risk Agent for MENA Instant Payments

**MENA Ignite Hackathon 2026 · Theme 4: Secure FinTech, Payments & Anti-Fraud · Team: Omar Chehade & Mohamad Nour Sayour**

Tasdiq (Arabic for *verification*) stops account-takeover fraud on instant payment rails
(InstaPay · Sarie · Aani · FAST) **before the money moves** — using GSMA Open Gateway
**CAMARA APIs** via the **Nokia Network-as-Code** platform as confidence-weighted signals
inside a **deterministic decision engine**, with an async **AI agent layer** (guide-listed
model) for bilingual compliance drafting and investigations.

> **Core principle — deterministic security, generative compliance:**
> the engine decides every transaction inline (450ms budget: two 200ms signal phases +
> 50ms margin); the AI never decides — it explains, investigates, and drafts paperwork.

![Tests](https://img.shields.io/badge/tests-13%2F13-green) ![CAMARA](https://img.shields.io/badge/CAMARA-3%20APIs%20live-blue) ![Ablation](https://img.shields.io/badge/ablation-%2B0.50%20recall-orange)

---

## How it works (60 seconds)

1. Bank calls `POST /v1/decide` with the transaction (amount, payee age, velocity).
2. **Phase 1 (0–200ms):** SIM Swap check alone. Fresh swap + amount > multiplier×mean
   (per-bank, e.g. 40×) → **DECLINE immediately** (early exit).
3. **Phase 2 (200–400ms):** Number Verification + Device Status **in parallel**, plus
   bank-side behavioral signals (payee recency, velocity, amount-vs-mean) — catches
   snatch-&-run theft where telecom signals stay green.
4. Confidence-weighted scoring: `risk = Σ(riskᵢ × confᵢ) ÷ Σ confᵢ + behavioral points`,
   six hard rules, per-bank signed policy → **APPROVE / ESCALATE / DECLINE** with
   **band isolation** (after a SIM swap, SMS/voice step-up is *prohibited* — the OTP
   would reach the attacker's SIM; in-app biometrics/WebAuthn only).
5. Decision returns to the bank (dual latency: end-to-end + internal) and is appended
   to a **hash-chained, pseudonymized, RFC 3161-anchored audit ledger**.
6. **Seconds later (async):** the AI agent writes the decision explanation and the
   bilingual (MSA/English) regulator-report draft; when the deterministic tripwire
   detects a coordinated attack, the agent **orchestrates CAMARA re-queries itself**
   through a PII-sealed, read-only, ledger-logged tool belt.

## Architecture

| Layer | Responsibility |
|---|---|
| **L0** | Conditional silent authentication (Number Verification match + stable SIM → OTP-free) |
| **L1** | CAMARA signal collection via Nokia NaC — per-operator circuit breakers, labeled cached fallback, deadline budgeter |
| **L2/L2.5** | Progressive engine: early exit, parallel phase, confidence weighting, behavioral signals |
| **L3** | Ed25519-signed maker-checker policies; every decision binds its policy hash (tampered config → rejected) |
| **L4** | Async AI agent: explanations, bilingual reports, clustering, copilot, injection canary + inline tripwire |
| **L5** | Dual-ledger audit: Intercept (inline) + Agent (async), HMAC-pseudonymized MSISDNs, RFC 3161 anchor queue |

```
bank ──► /v1/decide ──► [L1 CAMARA: SIM-Swap ▸ Number-Verify ▸ Device-Status]
                         │  (Nokia NaC gateway, per-operator breakers)
                         ▼
              [L2 engine: rules 0–5 + confidence math] ──► decision + band + step-up
                         │                                      │
              [L5 Intercept Ledger]                   [L4 async AI agent]
              hash-chained · pseudonymized            tool belt → CAMARA re-queries
              RFC 3161 anchor queue                   bilingual reports · copilot
```

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env            # add your keys (see below)
python -m pytest tests/ -q      # 13 tests — engine rules, tamper rejection, canary
python demo/run_demo.py         # live end-to-end evidence run → evidence/
python ablation/run.py          # 200-case ablation study
python -m uvicorn app.main:app --port 8793
# → demo UI: http://127.0.0.1:8793/   (customer view + fraud-ops dashboard)
```

**`.env` keys (gitignored — never commit):** `NAC_API_KEY`, `NAC_BASE_URL`,
`GEMINI_API_KEY`, `GEMINI_MODEL`. NaC self-registration is free at
[networkascode.nokia.io](https://networkascode.nokia.io) (simulator numbers included).
The AI layer is model-agnostic: any Resource & Tooling Guide-listed model (default
demo: Gemini 2.5 Flash; alternatives: Groq Llama 3.3, self-hosted Ollama/vLLM for
sovereign deployments — hosted models see **synthetic demo data only**).

## API

| Endpoint | Purpose |
|---|---|
| `POST /v1/decide` | The decision rail (decision, band, step-up allow/prohibit, dual latency, policy hash) |
| `POST /v1/replay` | Audit replay of any transaction from the ledger |
| `GET /v1/metrics` | Engine metrics |
| `POST /v1/policy/verify` | Policy-bundle signature verification (tamper demo) |
| `POST /v1/agent/explain` · `/report` · `/customer_alert` | Async AI outputs (schema-locked JSON) |
| `POST /v1/agent/investigate` | **Agent-orchestrated CAMARA re-queries** for a tripwire cluster (sealed tool belt) |
| `POST /v1/agent/copilot` | Analyst Q&A from ledger projection only (no PII) |
| `POST /v1/agent/canary` | Prompt-injection containment proof |

## Demo UI (two views)

| 📱 Customer | 🖥 Fraud Ops |
|---|---|
| Phone mockup ("Nile Bank — InstaPay"), 5 scenario chips, bilingual AR/EN results, Face-ID step-up ("no SMS was ever sent") | Decision badge + band, confidence bars, step-up chips (SMS ✗ crossed on swap bands), dual latency, tripwire → **AI panel showing each CAMARA call the agent made**, tamper + canary buttons, audit chain |

Scenarios: normal payment · **SIM-swap attack** (early-exit decline) · recent swap
(sensible weighting) · dual-SIM user (downweight, no false alarm) · **snatch-&-run**
(behavioral detection, biometric-only step-up).

## Results (labeled honestly)

- **Ablation — 200 seeded, feature-varied synthetic cases** (70 SIM-swap ATO · 70
  snatch-&-run · 60 tricky-clean): bank-only recall **0.50** · telecom-only **0.50** ·
  **blend 1.00 (0 FP)** — **+0.50 incremental recall from telecom signals**; the two
  families are complementary. Synthetic validation framework — partner-operator data
  is Phase 1. *Scaling this dataset from 30 to 200 varied cases caught a real engine
  bug: rule 0 fired only at confidence exactly 1.0, so cached-fallback swap detections
  (0.9) escaped the band — fixed to ≥ 0.9.*
- **Latency:** dual-reported — end-to-end (incl. Nokia sandbox RTT) vs internal
  execution. The sandbox is shared dev infrastructure; we show its overhead, not hide it.
- **Tests:** 13/13 — rule ordering, early exit, Ed25519 tamper rejection, injection
  canary, breaker behavior, ledger chains, pseudonymization.
- **Evidence:** `evidence/live_calls/` (first live CAMARA call), `evidence/demo_run/`
  (full live run), `evidence/ablation_results.json`, `evidence/portal/` (UI
  screenshots + official-rules verification).

## Security properties (all demoed live)

- **Ed25519 signed maker-checker policies** — tampered config rejected, never silently honored
- **Band isolation** — SMS/voice step-up *prohibited* on SIM-swap and behavioral bands
- **PII-sealed tool belt** — agent tools take opaque IDs; phone numbers never enter model context
- **Schema-locked outputs + structural canary** — hostile memos cannot poison reports
- **Dual-ledger audit** — HMAC-pseudonymized MSISDNs, RFC 3161 anchoring, decision replay
- **Fail-safe resilience** — per-operator breakers; primary-signal loss + anomaly → escalate;
  signed degraded-mode fallback if the platform is unreachable (attackers buy a stricter posture)

## Honest scope

Mocks (labeled in-demo): biometric UI, InstaPay end-to-end flow (simulated), Sarie/Aani/FAST
(config labels), synthetic transaction history. Phase 1 workstreams (named, not assumed):
porting-aware MNP cache (static map in prototype), operator consent/data-sharing agreements,
bank pilot. Reports are drafts for human compliance review. We claim "regulator-aligned",
never "certified".

## Repo map

```
app/main.py            FastAPI service + endpoints          app/policy.py      Ed25519 maker-checker
app/engine/decide.py   pipeline (phases, dual latency)      app/ledger.py      dual ledger + anchors
app/engine/weighting.py rules 0–5 + confidence math        app/tripwire.py    cluster alarm
app/signals/nac.py     NaC client + breakers + fallback     app/ai/agent.py    Gemini agent (schema-locked)
demo/ui/index.html     two-view demo UI                     app/ai/tools.py    sealed tool belt
demo/run_demo.py       live evidence run                    ablation/run.py    200-case study
demo/DEMO_SCRIPT.md    ≤3-min video script + judge Q&A      HANDOFF.md         full continuation doc
```

## Team

Omar Chehade · Mohamad Nour Sayour — Computer & Electrical Engineering, Beirut Arab
University. Built during the hackathon window (Jul 1 – Sep 13, 2026), AI-assisted with
approved tooling. Code is original team IP per hackathon rules.
