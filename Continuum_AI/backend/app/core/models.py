"""Domain models for Continuum AI.

A handover is a set of CLAIMS, not free text. Every claim carries a type, a
status, a confidence and evidence (source id + exact quote + timestamp).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AccessLabel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


# Higher number = stricter label.
LABEL_RANK = {
    AccessLabel.PUBLIC: 0,
    AccessLabel.INTERNAL: 1,
    AccessLabel.RESTRICTED: 2,
}


class Role(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    LEAVER = "leaver"
    SUCCESSOR = "successor"


class ClaimType(str, Enum):
    DECISION = "Decision"
    TASK = "Task"
    RISK = "Risk"
    DEPENDENCY = "Dependency"
    OPEN_QUESTION = "OpenQuestion"
    OWNERSHIP = "Ownership"


class ClaimStatus(str, Enum):
    VERIFIED = "Verified"
    INFERRED = "Inferred"
    CONFLICTING = "Conflicting"
    MISSING = "Missing"


class ReviewState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Source(BaseModel):
    """One imported GitHub record (issue, PR, comment)."""

    id: str
    kind: str  # issue | pull_request | comment
    title: Optional[str] = None
    author: str
    timestamp: str  # ISO 8601
    text: str
    access_label: AccessLabel = AccessLabel.INTERNAL
    url: Optional[str] = None


class Evidence(BaseModel):
    source_id: str
    quote: str
    timestamp: Optional[str] = None
    # Filled in by the verifier:
    quote_found: Optional[bool] = None
    match_kind: Optional[str] = None  # exact | normalized | fuzzy | none
    match_score: Optional[float] = None


class Claim(BaseModel):
    id: str
    type: ClaimType
    statement: str
    # Optional structured fields, used by conflict detection.
    entity: Optional[str] = None  # e.g. "invoice-sync"
    value: Optional[str] = None  # e.g. owner handle for Ownership claims
    proposed_status: ClaimStatus = ClaimStatus.INFERRED  # what the LLM asked for
    status: ClaimStatus = ClaimStatus.INFERRED  # what the system assigns
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    review_state: ReviewState = ReviewState.DRAFT
    conflicts_with: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # system flags, e.g. downgrade reasons
    version: int = 1


class ExtractedClaim(BaseModel):
    """Schema the LLM must return, one per claim."""

    type: ClaimType
    statement: str
    entity: Optional[str] = None
    value: Optional[str] = None
    status: ClaimStatus = ClaimStatus.INFERRED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim]
