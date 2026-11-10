"""Role-based handover built ONLY from approved claims.

Nothing reaches a handover unless a reviewer approved it. Each claim is
passed through the permission layer, so restricted evidence appears as a
placeholder. Gaps (Missing/Conflicting) are shown as open questions, never
hidden.
"""
from __future__ import annotations

from pydantic import BaseModel

from .models import Claim, ClaimStatus, ClaimType, ReviewState, Role, Source
from .permissions import ClaimView, view_claim


class Handover(BaseModel):
    role: str
    decisions: list[ClaimView]
    ownership: list[ClaimView]
    risks: list[ClaimView]
    dependencies: list[ClaimView]
    unfinished_work: list[ClaimView]
    open_questions: list[ClaimView]
    day1: list[str]
    week1: list[str]
    readiness: dict


def _readiness(claims: list[Claim]) -> dict:
    total = len(claims)
    if total == 0:
        return {"total": 0, "approved": 0, "verified": 0, "score": 0.0}
    approved = [c for c in claims if c.review_state == ReviewState.APPROVED]
    verified = [c for c in claims if c.status == ClaimStatus.VERIFIED]
    verified_and_approved = [c for c in approved if c.status == ClaimStatus.VERIFIED]
    return {
        "total": total,
        "approved": len(approved),
        "verified": len(verified),
        "unresolved": sum(
            1
            for c in claims
            if c.status in (ClaimStatus.MISSING, ClaimStatus.CONFLICTING)
        ),
        "score": round(len(verified_and_approved) / total, 2),
    }


def build_handover(
    claims: list[Claim], sources: list[Source], role: Role
) -> Handover:
    index = {s.id: s for s in sources}
    approved = [c for c in claims if c.review_state == ReviewState.APPROVED]

    def views(t: ClaimType) -> list[ClaimView]:
        return [view_claim(c, role, index) for c in approved if c.type == t]

    open_q = views(ClaimType.OPEN_QUESTION)
    # Approved claims that are still Missing/Conflicting are surfaced as gaps.
    for c in approved:
        if c.status in (ClaimStatus.MISSING, ClaimStatus.CONFLICTING) and (
            c.type != ClaimType.OPEN_QUESTION
        ):
            open_q.append(view_claim(c, role, index))

    tasks = views(ClaimType.TASK)
    risks = views(ClaimType.RISK)

    day1, week1 = [], []
    for v in risks:
        if v.redacted:
            continue
        day1.append(f"Read risk: {v.statement}")
    for v in tasks:
        if v.redacted:
            continue
        week1.append(f"Continue: {v.statement}")
    for v in open_q:
        if v.redacted:
            continue
        week1.append(f"Resolve open item ({v.status}): {v.statement}")

    return Handover(
        role=role.value,
        decisions=views(ClaimType.DECISION),
        ownership=views(ClaimType.OWNERSHIP),
        risks=risks,
        dependencies=views(ClaimType.DEPENDENCY),
        unfinished_work=tasks,
        open_questions=open_q,
        day1=day1,
        week1=week1,
        readiness=_readiness(claims),
    )
