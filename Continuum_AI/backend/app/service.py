"""Application service: the whole Connect -> Reconstruct -> Verify -> Review ->
Handover workflow, independent of HTTP and of the database.

Role rules (enforced here, on the server):
- admin / reviewer: load data, run extraction, review, read restricted
  evidence, read the audit log.
- leaver: may list claims (redacted above their clearance) and view handover.
- successor: may only view the handover (approved claims, redacted).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from .core.conflicts import detect_conflicts
from .core.extraction import extract_claims
from .core.handover import Handover, build_handover
from .core.models import ClaimStatus, ReviewState, Role, Source
from .core.permissions import ClaimView, filter_sources, leaked_restricted_text, view_claim
from .core.verifier import citation_precision, verify_all
from .demo import load_sources

STAFF = {Role.ADMIN, Role.REVIEWER}


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Service:
    def __init__(self, store, llm_factory: Callable[[Optional[str]], tuple]):
        self.store = store
        self.llm_factory = llm_factory

    # -- helpers ---------------------------------------------------------
    def _require_staff(self, role: Role) -> None:
        if role not in STAFF:
            raise Forbidden(f"role '{role.value}' may not do this")

    def _audit(self, action: str, role: Role, detail: Optional[dict] = None) -> None:
        self.store.add_audit({"ts": _now(), "action": action, "role": role.value, "detail": detail or {}})

    # -- Connect ---------------------------------------------------------
    def load_demo(self, role: Role) -> dict:
        self._require_staff(role)
        self.store.reset()
        sources = load_sources()
        self.store.put_sources(sources)
        self.store.set_meta("project", "Atlas Billing (synthetic demo)")
        self._audit("demo_loaded", role, {"sources": len(sources)})
        return self.status()

    # -- Reconstruct + Verify -------------------------------------------
    def extract(self, role: Role, provider: Optional[str] = None) -> dict:
        self._require_staff(role)
        sources = self.store.list_sources()
        if not sources:
            raise BadRequest("no sources loaded; load the demo project first")
        client, label = self.llm_factory(provider)
        claims = extract_claims(client, sources)
        claims = verify_all(claims, sources)
        claims = detect_conflicts(claims)
        used = getattr(client, "used", None)
        if used:
            label = used
        self.store.put_claims(claims)
        self.store.set_meta("extraction_provider", label)
        self.store.set_meta("extracted_at", _now())
        self._audit("extraction_run", role, {"provider": label, "claims": len(claims)})
        return self.status()

    # -- Status ----------------------------------------------------------
    def status(self) -> dict:
        claims = self.store.list_claims()
        counts: dict[str, int] = {}
        for c in claims:
            counts[c.status.value] = counts.get(c.status.value, 0) + 1
        return {
            "project": self.store.get_meta("project"),
            "sources": len(self.store.list_sources()),
            "claims": len(claims),
            "approved": sum(1 for c in claims if c.review_state == ReviewState.APPROVED),
            "rejected": sum(1 for c in claims if c.review_state == ReviewState.REJECTED),
            "by_status": counts,
            "extraction_provider": self.store.get_meta("extraction_provider"),
            "extracted_at": self.store.get_meta("extracted_at"),
        }

    # -- Evidence ledger ------------------------------------------------
    def list_sources(self, role: Role) -> list[Source]:
        if role == Role.SUCCESSOR:
            raise Forbidden("successors see the approved handover only")
        return filter_sources(role, self.store.list_sources())

    def list_claims(self, role: Role) -> list[ClaimView]:
        if role == Role.SUCCESSOR:
            raise Forbidden("successors see the approved handover only")
        idx = {s.id: s for s in self.store.list_sources()}
        return [view_claim(c, role, idx) for c in self.store.list_claims()]

    def get_claim(self, role: Role, claim_id: str) -> dict:
        if role == Role.SUCCESSOR:
            raise Forbidden("successors see the approved handover only")
        claim = self.store.get_claim(claim_id)
        if claim is None:
            raise NotFound(claim_id)
        idx = {s.id: s for s in self.store.list_sources()}
        view = view_claim(claim, role, idx)
        versions = self.store.list_versions(claim_id) if role in STAFF else []
        return {"claim": view, "versions": versions}

    # -- Review ----------------------------------------------------------
    def review(self, role: Role, claim_id: str, action: str, statement: Optional[str] = None) -> ClaimView:
        self._require_staff(role)
        claim = self.store.get_claim(claim_id)
        if claim is None:
            raise NotFound(claim_id)
        if action not in ("approve", "reject", "edit"):
            raise BadRequest("action must be approve, reject or edit")

        self.store.add_version(claim_id, claim.model_dump(mode="json") | {"snapshot_at": _now()})
        detail: dict = {"claim": claim_id, "from_version": claim.version}

        if action == "approve":
            if any(n.startswith("verifier: no quote found") for n in claim.notes):
                raise BadRequest(
                    "this claim has no verified evidence; edit it or reject it, it cannot be approved"
                )
            claim.review_state = ReviewState.APPROVED
        elif action == "reject":
            claim.review_state = ReviewState.REJECTED
        else:
            new_text = (statement or "").strip()
            if not new_text:
                raise BadRequest("edit needs a non-empty statement")
            claim.statement = new_text
            claim.review_state = ReviewState.DRAFT
            if claim.status == ClaimStatus.VERIFIED:
                claim.status = ClaimStatus.INFERRED
            claim.confidence = min(claim.confidence, 0.7)
            claim.notes.append("reviewer: statement edited; no longer machine-verified against the quote")
            detail["new_statement"] = new_text

        claim.version += 1
        self.store.save_claim(claim)
        self._audit(f"claim_{action}", role, detail)
        idx = {s.id: s for s in self.store.list_sources()}
        return view_claim(claim, role, idx)

    # -- Handover --------------------------------------------------------
    def handover(self, role: Role) -> Handover:
        claims = self.store.list_claims()
        sources = self.store.list_sources()
        h = build_handover(claims, sources, role)
        self._audit("handover_viewed", role, {"approved_claims": h.readiness.get("approved", 0)})
        return h

    # -- Audit + metrics -------------------------------------------------
    def audit_log(self, role: Role) -> list[dict]:
        self._require_staff(role)
        return self.store.list_audit()

    def metrics(self, role: Role) -> dict:
        """Numbers we actually measured on the current data."""
        self._require_staff(role)
        claims = self.store.list_claims()
        sources = self.store.list_sources()
        idx = {s.id: s for s in sources}
        leaks = {}
        for r in (Role.SUCCESSOR, Role.LEAVER):
            views = [view_claim(c, r, idx) for c in claims]
            leaks[r.value] = leaked_restricted_text(views, r, sources)
        return {
            "citation_precision": citation_precision(claims),
            "claims": len(claims),
            "restricted_sources": sum(1 for s in sources if s.access_label.value == "restricted"),
            "restricted_leaks_by_role": leaks,
            "note": "Quote checking proves the evidence exists, not that a conclusion is correct. Human review is required.",
        }
