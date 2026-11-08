"""Conflict detection across claims.

Two Ownership claims about the same entity with different values are marked
Conflicting and linked to each other. Both stay visible; neither is dropped.
Only claims with verified evidence take part, so a hallucinated claim cannot
create a conflict.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Claim, ClaimStatus, ClaimType


def _key(s: str | None) -> str:
    return (s or "").strip().lower()


def detect_conflicts(claims: list[Claim]) -> list[Claim]:
    groups: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for c in claims:
        if c.type != ClaimType.OWNERSHIP or not c.entity or not c.value:
            continue
        if c.status == ClaimStatus.MISSING:
            continue
        groups[(c.type.value, _key(c.entity))].append(c)

    for group in groups.values():
        values = {_key(c.value) for c in group}
        if len(values) < 2:
            continue
        ids = [c.id for c in group]
        for c in group:
            c.status = ClaimStatus.CONFLICTING
            c.conflicts_with = [i for i in ids if i != c.id]
            note = f"conflict: owners differ for '{c.entity}'"
            if note not in c.notes:
                c.notes.append(note)
            c.confidence = min(c.confidence, 0.5)
    return claims
