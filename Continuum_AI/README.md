# Continuum AI

Evidence-backed, permission-aware knowledge handover. Built for CodersInPune Round 2.

## Status (honest)

Done and tested (`cd backend && python -m pytest`, 23 tests):

- Claim model with types, statuses, confidence, evidence (source id, exact quote, timestamp)
- Deterministic quote verifier (exact -> normalized -> fuzzy); hallucinated quotes are downgraded, never Verified
- Ownership conflict detection (both claims kept, linked)
- Permission filter and redaction (a claim inherits the strictest source label)
- Prompt-injection hardening of the extraction prompt (source text wrapped as untrusted data)
- Role-based handover built from approved claims only, with readiness counts
- Synthetic demo project (25 records, 2 restricted, 1 injection attempt) and an offline mock LLM response

Not built yet: HTTP API, database layer, real LLM adapters (Gemini/Groq), frontend, deployment.

## Run tests

    cd backend
    pip install -r requirements.txt
    python -m pytest

## AI assistance disclosure

Claude was used for development assistance. Core logic and tests were generated with Claude and reviewed by the team.
