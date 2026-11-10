"""FastAPI app. Thin: all rules live in service.py.

AUTH NOTE: roles come from the `X-Role` header (a demo role switcher so judges
can try every view without signing in). It is NOT real authentication. The
role rules are still enforced server-side in service.py.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import parse_origins
from .core.extraction import ExtractionError
from .core.models import Role
from .llm import LLMError, build_client
from .service import BadRequest, Forbidden, NotFound, Service


def build_store():
    url = os.getenv("DATABASE_URL")
    if url:
        from .db import SqlStore

        return SqlStore(url)
    from .store import MemoryStore

    return MemoryStore()


app = FastAPI(title="Continuum AI", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(os.getenv("CORS_ORIGINS")),
    allow_methods=["*"],
    allow_headers=["*"],
)

store = build_store()
service = Service(store, build_client)


@app.on_event("startup")
def seed_on_first_start() -> None:
    """So a judge never sees an empty app: load the synthetic sources once.
    Claims are produced only when extraction is run (live or labelled sample)."""
    if not store.list_sources():
        service.load_demo(Role.ADMIN)


def current_role(x_role: str = Header(default="reviewer")) -> Role:
    try:
        return Role(x_role.strip().lower())
    except ValueError:
        raise HTTPException(400, f"unknown role '{x_role}'; use admin, reviewer, leaver or successor")


@app.exception_handler(Forbidden)
async def _forbidden(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=403)


@app.exception_handler(NotFound)
async def _not_found(_, exc):
    return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)


@app.exception_handler(BadRequest)
async def _bad_request(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(ExtractionError)
async def _extraction(_, exc):
    return JSONResponse({"detail": f"the model returned unusable output: {exc}"}, status_code=502)


@app.exception_handler(LLMError)
async def _llm(_, exc):
    return JSONResponse({"detail": f"LLM provider error: {exc}"}, status_code=502)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    return service.status()


@app.post("/demo/load")
def demo_load(role: Role = Depends(current_role)):
    return service.load_demo(role)


@app.post("/extract")
def extract(
    provider: Optional[str] = Query(default=None, description="e.g. 'gemini,groq' or 'mock'"),
    role: Role = Depends(current_role),
):
    return service.extract(role, provider)


@app.get("/sources")
def sources(role: Role = Depends(current_role)):
    return service.list_sources(role)


@app.get("/claims")
def claims(role: Role = Depends(current_role)):
    return service.list_claims(role)


@app.get("/claims/{claim_id}")
def claim_detail(claim_id: str, role: Role = Depends(current_role)):
    return service.get_claim(role, claim_id)


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "edit"]
    statement: Optional[str] = None


@app.post("/claims/{claim_id}/review")
def review(claim_id: str, body: ReviewRequest, role: Role = Depends(current_role)):
    return service.review(role, claim_id, body.action, body.statement)


@app.get("/handover")
def handover(role: Role = Depends(current_role)):
    return service.handover(role)


@app.get("/audit")
def audit(role: Role = Depends(current_role)):
    return service.audit_log(role)


@app.get("/metrics")
def metrics(role: Role = Depends(current_role)):
    return service.metrics(role)
