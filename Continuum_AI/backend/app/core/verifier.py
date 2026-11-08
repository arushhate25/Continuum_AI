"""Deterministic quote verification.

The LLM must return an exact quote per claim. This module confirms the quote
exists in the stored source text, then assigns the final status:

- A claim can only be Verified if at least one of its quotes is found in the
  source it cites (exact, then normalized match).
- Fuzzy matches never produce Verified; they downgrade to Inferred.
- Claims with no usable evidence are downgraded to Missing.

Quote checking only proves that the evidence EXISTS, not that the conclusion
is correct. That is why human review is mandatory.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .models import Claim, ClaimStatus, Evidence, Source

FUZZY_MIN_SCORE = 0.85  # fuzzy match counts as "partial" evidence at/above this


def normalize(text: str) -> str:
    """Lowercase, unify quotes/dashes, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _best_fuzzy(quote_n: str, text_n: str) -> float:
    """Best similarity of quote against any same-length window of the text."""
    if not quote_n or not text_n:
        return 0.0
    qlen = len(quote_n)
    if qlen >= len(text_n):
        return SequenceMatcher(None, quote_n, text_n).ratio()
    best = 0.0
    step = max(1, qlen // 8)
    for start in range(0, len(text_n) - qlen + 1, step):
        window = text_n[start : start + qlen]
        score = SequenceMatcher(None, quote_n, window).ratio()
        if score > best:
            best = score
            if best >= 0.999:
                break
    return best


def verify_quote(quote: str, source_text: str) -> tuple[str, float]:
    """Return (match_kind, score). match_kind: exact|normalized|fuzzy|none."""
    if not quote or not quote.strip():
        return "none", 0.0
    if quote in source_text:
        return "exact", 1.0
    q_n, t_n = normalize(quote), normalize(source_text)
    if q_n and q_n in t_n:
        return "normalized", 1.0
    score = _best_fuzzy(q_n, t_n)
    if score >= FUZZY_MIN_SCORE:
        return "fuzzy", round(score, 3)
    return "none", round(score, 3)


def verify_evidence(ev: Evidence, sources: dict[str, Source]) -> Evidence:
    src = sources.get(ev.source_id)
    if src is None:
        ev.quote_found, ev.match_kind, ev.match_score = False, "none", 0.0
        return ev
    kind, score = verify_quote(ev.quote, src.text)
    ev.match_kind = kind
    ev.match_score = score
    ev.quote_found = kind in ("exact", "normalized")
    if ev.timestamp is None:
        ev.timestamp = src.timestamp
    return ev


def verify_claim(claim: Claim, sources: dict[str, Source]) -> Claim:
    """Check every quote, then set the final status. Never upgrades beyond
    what the evidence supports."""
    for ev in claim.evidence:
        verify_evidence(ev, sources)

    found = [e for e in claim.evidence if e.quote_found]
    fuzzy = [e for e in claim.evidence if e.match_kind == "fuzzy"]
    claim.notes = [n for n in claim.notes if not n.startswith("verifier:")]

    if found:
        # Evidence exists. Keep Inferred/Conflicting if the model said so;
        # only allow Verified when the model asked for it AND quote was found.
        if claim.proposed_status == ClaimStatus.VERIFIED:
            claim.status = ClaimStatus.VERIFIED
        elif claim.proposed_status in (ClaimStatus.CONFLICTING, ClaimStatus.MISSING):
            # A real, evidenced gap or disagreement stays visible as such.
            claim.status = claim.proposed_status
        else:
            claim.status = ClaimStatus.INFERRED
    elif fuzzy:
        claim.status = ClaimStatus.INFERRED
        claim.notes.append("verifier: quote only fuzzy-matched; downgraded to Inferred")
    else:
        claim.status = ClaimStatus.MISSING
        claim.notes.append("verifier: no quote found in source; downgraded to Missing")

    if claim.proposed_status == ClaimStatus.VERIFIED and claim.status != ClaimStatus.VERIFIED:
        claim.notes.append("verifier: model requested Verified but evidence did not support it")

    # Confidence can never exceed what the evidence supports.
    downgraded_to_missing = (
        claim.status == ClaimStatus.MISSING and not found and not fuzzy
        and claim.proposed_status != ClaimStatus.MISSING
    )
    if downgraded_to_missing:
        claim.confidence = 0.0
    elif claim.status == ClaimStatus.INFERRED:
        claim.confidence = min(claim.confidence, 0.7)
    return claim


def verify_all(claims: list[Claim], sources: list[Source]) -> list[Claim]:
    index = {s.id: s for s in sources}
    return [verify_claim(c, index) for c in claims]


def citation_precision(claims: list[Claim]) -> float:
    """Share of evidence quotes that were found in their cited source."""
    total = sum(len(c.evidence) for c in claims)
    if total == 0:
        return 0.0
    ok = sum(1 for c in claims for e in c.evidence if e.quote_found)
    return round(ok / total, 3)
