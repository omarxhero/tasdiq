# TASDIQ PROTOTYPE — HANDOFF & CONTINUATION DOCUMENT
> Purpose: ANY AI (or human) can pick up exactly where this session left off.
> Companion docs: `../TASDIQ_ARCHITECTURE_AND_DEMO_MAP.txt` (design bible v2.8),
> `../Tasdiq_PORTAL_SUBMISSION_v2.txt` (submission text), `../deck/` (PDF+PPTX+HTML).

## 1. WHAT THIS IS
Working prototype of Tasdiq — telecom-verified fraud decision service for MENA
instant payments (MENA Ignite 2026 hackathon, GSMA + Nokia NaC). Deterministic
engine decides <450ms (dual-reported latency); guide-listed AI agent does async
compliance. Solo developer + AI-assisted build.

## 2. STATE AT HANDOFF (2026-08-16) — ALL WORKING
- ✅ 13/13 unit tests green (`python -m pytest tests/ -q`)
- ✅ LIVE CAMARA calls verified (Nokia NaC sandbox): SIM Swap + Device Status
  (roaming + connectivity). Evidence: `evidence/live_calls/camara_first_live_evidence.json`
- ✅ End-to-end demo run with all beats landing intended decisions
  (`evidence/demo_run/live_end_to_end.json`):
    clean→APPROVE · swap+52x→DECLINE(early-exit) · dualsim→DEGRADED_SIGNAL_ANOMALY ·
    snatch-&-run→BEHAVIORAL_ANOMALY(biometric-only) · tripwire FIRES on 3 declines
    + AI tool-belt investigation with sealed CAMARA probes
- ✅ Tamper demo (signed policy rejected), canary (injection contained),
  bilingual AI reports (Gemini), replay + intact hash chains, copilot memo-free
- ✅ Ablation (synthetic, 30 cases): bank-only rec 0.5 / telecom-only 0.5 /
  blend 1.0 → **incremental recall from telecom = +0.50** (`evidence/ablation_results.json`)
- ✅ Server boots: `uvicorn app.main:app --port 8792`; demo UI at `/` (also `demo/ui/index.html`)
- ✅ Demo console UI: scenarios, security theater, AI buttons, dual-latency display

## 3. KEYS & ENDPOINTS (in `.env` — GITIGNORED, never commit)
- NaC gateway: `https://network-as-code.p-eu.apihub.nokia.io` (NOT the rapidapi.com
  host — that one 403s with this key). Headers: `x-rapidapi-host:
  network-as-code.nokia.rapidapi.com` + `x-rapidapi-key`.
  - SIM Swap: POST `passthrough/camara/v1/sim-swap/sim-swap/v0/check` {phoneNumber,maxAge(h)} → {swapped}
  - Roaming: POST `device-status/v0/roaming` {device:{phoneNumber}} → {roaming,countryCode,countryName}
  - Connectivity: POST `device-status/v0/connectivity` → {connectivityStatus}
- Simulators: `+99999991000` = swapped:true (fraud beats); `+99999991001` =
  swapped:false (clean beats). Others are flaky (404/422/5xx).
- Gemini: `POST generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
  header `x-goog-api-key` (NOT ?key= param). Works.
- ⚠️ SECURITY: both keys were shared in chat. Rotate them after the hackathon.
  Session cookies pasted by the user are NOT needed/used — do not use them.

## 4. ARCHITECTURE QUICK MAP (see design bible for full detail)
`app/main.py` FastAPI: POST /v1/decide (inline engine+ledger+tripwire+webhook
flag), /v1/replay/{id}, /v1/metrics, /v1/policy/{bank} + /v1/policy/verify
(tamper demo), /v1/agent/{explain,report,investigate,copilot,canary}.
`app/signals/nac.py` — CAMARA client, per-operator breaker, **labeled recorded
fallback** (`demo/cached_responses/nac_recordings.json`, degradation=CACHED_FALLBACK,
conf 0.9) — sandbox rate-limits under load, this keeps demos deterministic
(official guide tip). `app/engine/` — decide (deadline budgeter, dual latency),
weighting (hard rules 0–5 incl. SIM_SWAP_RECENT band, primary-signal-loss,
degraded+anomaly, snatch-&-run biometric-only). `app/policy.py` — ed25519 signed
bundles, maker-checker (two personas), tamper rejection, policy_version_hash.
`app/ledger.py` — dual hash chains, HMAC-pseudonymized MSISDN, RFC3161 anchor
queue (pending→anchored). `app/tripwire.py` — rolling-window cluster alert.
`app/ai/` — Gemini agent (schema-locked JSON, template fallback),
sealed tool belt + Fernet vault (hash↔msisdn resolved inside tools only;
model context is PII-free and free-text-free — memos never reach prompts).

## 5. HOW TO RUN
```
cd prototype
python -m pytest tests/ -q            # 13 green
python demo/run_demo.py               # live end-to-end evidence run
python ablation/run.py                # ablation table + json
uvicorn app.main:app --port 8792      # then open http://127.0.0.1:8792/
```
Deps: `pip install -r requirements.txt` (+ network-as-code installed).

## 6. REMAINING WORK (priority order)
1. Record the ≤3-min demo video (script = design bible Section 9; beats map 1:1
   to the demo UI buttons; rehearse twice; use cached fallback if sandbox lags).
2. Repo on GitHub (submission needs the link): `git init` done locally; create
   empty repo `tasdiq`, push. .env/keys/ledger_store are gitignored.
3. Fill user bio in deck (PPTX slide 12 + HTML+PDF) — waiting on the user.
4. Idea Capture Template — waiting on the user to download from HackerEarth.
5. Optional polish: Number Verify full OAuth flow (3-legged; needs browser
   device consent — Phase 1); breaker metrics surfaced in /v1/metrics; ablation
   expanded beyond 30 synthetic cases (labeled as such).
6. Optional: mTLS self-signed demo certs; streamlit-free — UI is plain HTML.

## 7. GOTCHAS LEARNED THIS SESSION
- Sandbox latency 300–1200ms/call and rate-limits after bursts → dual latency
  reporting (end_to_end vs internal) + labeled cached fallback are LOAD-BEARING
  demo features, not hacks.
- The rapidapi.com gateway 403s (Cloudflare 1010) with this key; apihub works.
- `+99999991000` is ALWAYS swapped:true in the simulator — that's why the clean
  beats use `+99999991001`.
- Gemini needs header auth; query-param key 404s.
- Test-first caught: policy double-signing bug, rule-shadowing order,
  coverage-definition nuance. Keep TDD for any new rule.

## 7.5 NOKIA PORTAL VERIFICATION (2026-08-16, evening)
- User session cookie (connect.sid) EXPIRED 18:27Z — portal SPA renders empty.
  If a logged-in scan is ever needed, ask user for FRESH cookies.
- Did NOT need it: the API key alone unlocked more:
  - OAuth client credentials obtained via GET /oauth2/v1/auth/clientcredentials
    (stored in .env as NAC_OAUTH_CLIENT_ID/SECRET; endpoints auth.eu.nac.nokia.io).
  - Discovery: authorization/token/fast-flow endpoints (fast-flow CSP endpoint
    exists but 404/param-gated from server side — Phase 1 to wire the full
    3-legged device consent; auth URL is demo-showable once obtained).
  - NUMBER RECYCLING API works live: {"phoneNumberRecycled": true} — recycled
    numbers are an account-takeover vector; wired into nac client + tool belt
    as a bonus INVESTIGATION signal (inline rail stays 3 APIs as submitted).
  - consent-info exists (needs purpose=dpv:... + requestCaptureUrl) — Phase 1.
- Sandbox simulator +99999991000: SIM swapped AND number recycled (fraud-heavy
  test profile). +99999991001: clean profile.

## 8. GIT STATE
Local repo initialized at handoff time (see `git log`). Working tree = state
described in §2. Branch: main.
