# Continuum AI

Evidence-backed, permission-aware knowledge handover. Built for CodersInPune Round 2.

## Status (honest)

Tested by automated tests (`cd backend && python -m pytest`, 51 tests, run in the build workspace):

- Claim model, deterministic quote verifier (exact -> normalized -> fuzzy), conflict detection
- Permission filter and redaction (claim inherits the strictest source label)
- Prompt-injection hardening of the extraction prompt
- Service layer: load demo, extract, review (approve / reject / edit with versions), role-based handover, audit log, metrics
- Gemini / Groq adapters (request shape, parsing, retries, provider fallback), tested with a fake transport
- Claims with no verified quote cannot be approved

Written but NOT yet run (needs FastAPI, SQLAlchemy and Postgres, absent from the build workspace):

- `app/main.py` (HTTP API), `app/db.py` (Postgres store), Alembic migration, Dockerfile
- Real calls to Gemini / Groq have never been made

Not built yet: frontend, deployment.

## Run locally

    cd backend
    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python -m pytest
    uvicorn app.main:app --reload       # runs in memory when DATABASE_URL is unset

Open http://localhost:8000/docs. Pick a role with the `X-Role` header (admin, reviewer, leaver, successor).
The role header is a demo role switcher, not real authentication; rules are enforced server-side.

Try the flow: `POST /extract?provider=mock` -> `GET /claims` -> `POST /claims/{id}/review` -> `GET /handover` with `X-Role: successor`.
`provider=mock` replays a saved sample response and is labelled as such in `/status`. Live extraction needs `GEMINI_API_KEY` and/or `GROQ_API_KEY` (see `.env.example`).

## AI assistance disclosure

Claude was used for development assistance. Code and tests were generated with Claude and reviewed by the team.
