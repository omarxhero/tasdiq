# Tasdiq — Telecom-Verified AI Risk Agent (Prototype)

Fraud decision service for MENA instant payments. Deterministic engine decides
inside a 450ms budget (dual-reported latency: end-to-end incl. sandbox RTT +
internal execution). CAMARA signals via Nokia Network-as-Code (SIM Swap, Device
Status, Number Verification-degraded). Guide-listed AI agent (Gemini 2.5 Flash)
handles async compliance — bilingual reports, clustering, sealed tool belt.

## Run
    pip install -r requirements.txt
    python -m pytest tests/ -q        # 13 tests
    python demo/run_demo.py           # live end-to-end run + evidence
    python ablation/run.py            # ablation study
    uvicorn app.main:app --port 8792  # demo console at http://127.0.0.1:8792/

## Security properties (demoed live)
- Signed maker-checker policies — tampered config rejected; decisions bind policy hash
- Dual hash-chained ledgers, HMAC-pseudonymized MSISDN, RFC 3161 anchoring queue
- Band isolation: SMS prohibited after SIM swap / snatch-&-run (biometrics only)
- Prompt-injection canary: hostile memos never reach model context (PII-sealed tool belt)
- Per-operator circuit breakers with labeled recorded fallback (sandbox resilience)

Keys live in `.env` (gitignored). Full design: `../TASDIQ_ARCHITECTURE_AND_DEMO_MAP.txt`.
Continuation guide: `HANDOFF.md`.
