# TASDIQ DEMO SCRIPT — ≤3 minutes (prototype phase video)

Format: screen recording (OBS), 1600×900+, mic audio. Lead with the live CAMARA
call — a working sandbox call is worth more than three pages of architecture.
Rehearse twice before recording. If the sandbox is slow, the labeled
CACHED_FALLBACK path IS part of the story (graceful degradation) — narrate it,
never apologize for it.

## Shot list

| # | Time | Shot | Say (beats) |
|---|------|------|-------------|
| 1 | 0:00–0:15 | Title card (deck slide 1) | "Tasdiq — telecom-verified AI risk agent for MENA instant payments. CAMARA signals, confidence-weighted, in a deterministic engine. Let's stop a real attack." |
| 2 | 0:15–0:40 | Fraud-ops tab, LIVE badge | "And it's 5G-ready by physics: URLLC transport adds single-digit milliseconds — the 450ms budget is never network-constrained.
     The dashboard is the bank's fraud-ops view. Three CAMARA APIs — SIM Swap, Number Verification, Device Status — live through Nokia Network-as-Code. Confidence-weighted, never binary." |
| 3 | 0:40–1:10 | Customer tab → chip "SIM-swap attack" → Pay | "Attacker swaps the SIM, transfers 52,000 EGP — 52× this account's normal. Watch the phone: the customer is protected in under a second. No OTP was ever sent — the SMS channel may belong to the attacker." |
| 4 | 1:10–1:35 | Result screen + timeline | "Plain language, bilingual: what happened, why, and what the customer should do. Bank sees the same decision signed to a hash-chained ledger." |
| 5 | 1:35–2:00 | Ops: tamper demo (🔓 Tamper policy) | "Zero-trust: policies are Ed25519-signed under maker-checker. Watch — I modify a threshold in the config… the engine REJECTS the tampered bundle. No silent honoring." |
| 6 | 2:00–2:25 | Ops: burst (6 rapid attempts) → tripwire → Investigate | "Coordinated attack pattern — the deterministic tripwire fires, and the AI agent investigates: it decides which signals are proportionate to re-check per transaction, runs them through its PII-sealed tool belt, and drafts the bilingual report. The AI never decides the payment — it decides the investigation." |
| 7 | 2:25–2:45 | Ops: canary (💉 injection) | "Hostile memo in the transaction — a prompt-injection attempt. Schema-locked output: the report stays clean. Enterprise LLM security, demoed live." |
| 8 | 2:45–3:00 | Snatch-&-run chip → Face ID | "And the fraud telecom can't see: phone snatched unlocked. Telecom green — but behavior isn't. Step-up: in-app biometric only. SMS prohibited — the thief holds the phone. Tasdiq." |

## Beat-by-beat UI map (buttons on http://127.0.0.1:8793)
- Shot 3: tab "📱 Customer" → chip "🚨 SIM-swap attack" → "Pay now"
- Shot 5: tab "🖥 Fraud Ops" → "🔓 Tamper policy"
- Shot 6: "⚡ Burst (coordinated attack)" → tripwire banner → "Investigate"
- Shot 7: "💉 Injection canary"
- Shot 8: Customer tab → chip "🏃 Snatch & run" → Pay → Face ID button

## Recording checklist
- [ ] uvicorn running (`python -m uvicorn app.main:app --port 8793`), keys live
- [ ] Warm run first (one clean txn) so sandbox caches settle
- [ ] Window 1600×900, no notifications, phone-mock visible fully
- [ ] Say "live" only when the LIVE badge shows; if CACHED_FALLBACK, say
      "labeled cached fallback — the breaker opened, decision still in-window"
- [ ] Demo-day reasoning note: the policy line is deterministic (template
      fallback if Gemini misbehaves live) — rehearse once with keys OFF so the
      fallback wording feels native, not like a failure
- [ ] End card: team (Omar Chehade · Mohamad Nour Sayour) + repo link

## Mock-judging checklist (run with Dr. or a peer as judge)
1. "Why 450ms?" → two 200ms phases + 50ms margin; must finish inside the
   authorization window (schemes settle in seconds; a slower check becomes the
   transaction). Latency reported two ways.
2. "Why not SMS on SIM swap?" → the swapped SIM receives the SMS — band
   isolation prohibits SMS/voice, allows WebAuthn/biometric.
3. "What if the sandbox is down?" → per-operator breaker → confidence 0 →
   coverage policy escalates conservatively; signed degraded-mode fallback if
   Tasdiq itself is unreachable. Fail-safe, never fail-open.
4. "Who pays?" → bank pays Tasdiq (hybrid SaaS + per-decision) → Tasdiq pays
   operator per CAMARA call → bank avoids fraud losses well above both.
5. "Does the LLM decide?" → never. Deterministic engine decides inline; the
   agent explains/investigates/drafts async, PII-sealed, ledger-logged.
6. "Ablation?" → 200 varied synthetic cases: bank-only 0.50, telecom-only 0.50,
   blend 1.00 recall — the two signal families are complementary. Labeled
   synthetic; partner-operator data is Phase 1.
7. "Does the LLM decide which probes run?" → "No. A deterministic proportionality policy decides. The LLM only writes the natural-language explanation of why the policy skipped a probe. The policy is code, not the model." (verbatim — practice it)

8. "450ms budget but observed latency is higher?" → "Two numbers: internal execution is single-digit ms; end-to-end includes the shared sandbox RTT (200–1,300ms). Production calls NaC from the bank's own VPC — sub-50ms RTT, well inside budget."
9. "Synthetic cases = real fraud?" → "We don't claim that — they stress the engine's logic across the full feature space, reproducibly (seed 2026). The varied dataset caught a real engine bug. Partner data is Phase 1."
10. "Device Swap false positives (eSIM toggles)?" → "Risk 20, corroboration-only — never escalates alone. A legitimate toggle costs at most a biometric step-up, never a decline."8. "Sovereignty?" → hosted models see synthetic demo data only; production runs

11. "Data residency with a hosted model?" → "Demo runs Gemini on synthetic data only. Production drops into a self-hosted sovereign instance — Llama 3.3 via vLLM on the bank's on-premise hardware. Same schemas, same sealed tool belt, nothing leaves the country."
12. "What if STC or Zain has an API blackout?" → "A missing signal is a tightening, not an opening. Breakers trip, Tasdiq drops to signed degraded-mode fallback, high-value instant clearances lock, step-up collapses to biometric WebAuthn — until service returns."   self-hosted open weights in the bank's cloud. No PII crosses a border.
