# MENTOR SESSION — ONE SHOT, 30 MINUTES (strict, per official guide)

Mentor: Abdullah A. Alkaoud (abaalkaoud@stc.com.sa) — STC background = operator
insider. Window: NOW – Sep 10 EOD. ONE session only, no follow-ups. Recording OK?
ASK at start ("may we record for our team notes?").

## Rules that matter (from the official guide)
- One session, 30 min hard cap, mentor may terminate overruns.
- We schedule it ourselves. If live impossible → email guidance (allowed).
- Mentors do NOT: debug code, design the system, validate business models,
  review multiple idea versions. Mentors DO: architecture, API usage patterns,
  execution risks/trade-offs, real-world deployment feedback.
- Come prepared or be deprioritized. This file IS the preparation.

## Minute-by-minute agenda
| Time | Segment | Content |
|------|---------|---------|
| 0–1 | Thanks + framing | "Working prototype, live CAMARA calls. We want your deployment-level judgment, not idea validation." |
| 1–4 | The 3-min pitch | One-sentence pitch → the 3 APIs → decision triad + band isolation → what's real in the prototype. OFFER the live demo only if he signals interest ("we can screen-share the live flow in 90 seconds — useful?"). |
| 4–26 | Q1–Q5 (his answers are the gold — LISTEN, don't pitch) | Questions below, in order. Take notes verbatim. |
| 26–29 | His top risks | "What's the biggest thing we're missing that a telecom person sees immediately?" |
| 29–30 | Close | Thank + one-line commitment ("we'll fold this into the Sep 13 demo"). |

## The five questions (priority order — all in-scope topics)
1. **API usage patterns** — real-world SIM Swap / Number Verification latency +
   availability under load; what degrades first?
2. **Operator integration** — consent/data-sharing steps a bank↔telco rollout
   needs; realistic timeline?
3. **Execution risks** — where fraud-detection pilots fail most: false
   positives, MNP routing, integration friction?
4. **Architecture soundness** — per-operator circuit breakers +
   confidence-weighting for multi-operator MENA: right approach from your
   deployment experience?
5. **Sep 13 demo credibility** — what makes this land with telecom+bank judges?

## Do / Don't
- DO: mention the working prototype once, with evidence (one sentence + offer).
- DO: capture exact phrases he uses — operator vocabulary = judge vocabulary.
- DON'T: pitch the business model (out of scope per guide), ask him to review
  slide versions, or run long.
- DON'T: send code, keys, or the .env. Ever.

## After the session (same day)
- Write his answers into this file (section below).
- Convert each answer into a demo/pitch adjustment; commit.
- If email-mode instead: send the same 5 questions in one email; one polite
  follow-up after 4 days MAX if silent (guide forbids follow-up SESSIONS, not
  delivery of the single email thread's reply).

## SESSION NOTES (fill after)
-
