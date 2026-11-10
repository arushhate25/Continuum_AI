"""Permission-aware access and redaction.

Rules:
- Every source has an access label. A claim inherits the STRICTEST label
  among its evidence sources.
- Filtering happens on the server BEFORE retrieval and before any LLM call
  for a viewer-facing flow, so the model never sees material the viewer
  cannot access.
- Restricted evidence is shown as a placeholder, never as content.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .models import (
    LABEL_RANK,
    AccessLabel,
    Claim,
    Role,
    Source,
)

# Highest label each role may read.
ROLE_CLEARANCE: dict[Role, AccessLabel] = {
    Role.ADMIN: AccessLabel.RESTRICTED,
    Role.REVIEWER: AccessLabel.RESTRICTED,
    Role.LEAVER: AccessLabel.INTERNAL,
    Role.SUCCESSOR: AccessLabel.INTERNAL,
}


def can_read(role: Role, label: AccessLabel) -> bool:
    return LABEL_RANK[label] <= LABEL_RANK[ROLE_CLEARANCE[role]]


def filter_sources(role: Role, sources: list[Source]) -> list[Source]:
    """Drop sources the role may not read. Call BEFORE retrieval / LLM."""
    return [s for s in sources if can_read(role, s.access_label)]


def claim_label(claim: Claim, sources: dict[str, Source]) -> AccessLabel:
    """Strictest label among the claim's cited sources."""
    labels = [
        sources[e.source_id].access_label
        for e in claim.evidence
        if e.source_id in sources
    ]
    if not labels:
        return AccessLabel.INTERNAL
    return max(labels, key=lambda l: LABEL_RANK[l])


class EvidenceView(BaseModel):
    source_id: Optional[str] = None
    quote: Optional[str] = None
    timestamp: Optional[str] = None
    match_kind: Optional[str] = None
    redacted: bool = False


class ClaimView(BaseModel):
    id: str
    type: str
    statement: Optional[str] = None
    status: str
    confidence: float
    evidence: list[EvidenceView]
    review_state: str = "draft"
    version: int = 1
    conflicts_with: list[str] = []
    redacted: bool = False
    placeholder: Optional[str] = None
    notes: list[str] = []


def view_claim(claim: Claim, role: Role, sources: dict[str, Source]) -> ClaimView:
    """Return what `role` is allowed to see for this claim.

    If the claim depends on any source above the role's clearance, the
    statement and all evidence are replaced by a placeholder.
    """
    label = claim_label(claim, sources)
    if not can_read(role, label):
        restricted_n = sum(
            1
            for e in claim.evidence
            if e.source_id in sources
            and not can_read(role, sources[e.source_id].access_label)
        )
        return ClaimView(
            id=claim.id,
            type=claim.type.value,
            statement=None,
            status=claim.status.value,
            confidence=claim.confidence,
            evidence=[EvidenceView(redacted=True) for _ in range(restricted_n)],
            review_state=claim.review_state.value,
            version=claim.version,
            redacted=True,
            placeholder=f"Supported by {restricted_n} restricted source(s)",
        )
    return ClaimView(
        id=claim.id,
        type=claim.type.value,
        statement=claim.statement,
        status=claim.status.value,
        confidence=claim.confidence,
        evidence=[
            EvidenceView(
                source_id=e.source_id,
                quote=e.quote,
                timestamp=e.timestamp,
                match_kind=e.match_kind,
            )
            for e in claim.evidence
        ],
        review_state=claim.review_state.value,
        version=claim.version,
        conflicts_with=claim.conflicts_with,
        notes=claim.notes,
    )


def leaked_restricted_text(
    views: list[ClaimView], role: Role, sources: list[Source]
) -> list[str]:
    """Leak check used by tests: return source ids whose text appears in any
    view although the role may not read that source."""
    blob = " ".join(
        (v.statement or "") + " " + " ".join((e.quote or "") for e in v.evidence)
        for v in views
    ).lower()
    leaks = []
    for s in sources:
        if can_read(role, s.access_label):
            continue
        # Check a distinctive chunk of the source text.
        probe = s.text.strip().lower()[:30]
        if probe and probe in blob:
            leaks.append(s.id)
    return leaks
