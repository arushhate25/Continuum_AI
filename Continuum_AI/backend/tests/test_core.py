from app.core.extraction import (
    DATA_CLOSE,
    ExtractionError,
    FakeLLM,
    build_user_prompt,
    extract_claims,
    neutralise,
)
from app.core.handover import build_handover
from app.core.models import (
    AccessLabel,
    ClaimStatus,
    ClaimType,
    ReviewState,
    Role,
    Source,
)
from app.core.permissions import (
    claim_label,
    filter_sources,
    leaked_restricted_text,
    view_claim,
)
from app.core.verifier import citation_precision, verify_quote
from app.demo import load_sources, run_pipeline

import pytest


@pytest.fixture(scope="module")
def pipeline():
    return run_pipeline()


def by_statement(claims, fragment):
    return next(c for c in claims if fragment in c.statement)


# ---- verifier --------------------------------------------------------------
def test_exact_normalized_fuzzy_none():
    text = "Review pending. I cannot approve until the load test numbers are posted."
    assert verify_quote("Review pending.", text)[0] == "exact"
    assert verify_quote("REVIEW   pending.", text)[0] == "normalized"
    assert verify_quote("I cannot aprove until the load test numbers are posted", text)[0] == "fuzzy"
    assert verify_quote("The team adopted Kafka", text)[0] == "none"
    assert verify_quote("", text)[0] == "none"


def test_hallucinated_claims_are_never_verified(pipeline):
    claims, _ = pipeline
    kafka = by_statement(claims, "Kafka")
    dana = by_statement(claims, "Dana owns")
    for c in (kafka, dana):
        assert c.proposed_status == ClaimStatus.VERIFIED  # model lied
        assert c.status == ClaimStatus.MISSING  # system downgraded
        assert c.confidence == 0.0
        assert any("downgraded" in n or "did not support" in n for n in c.notes)


def test_fuzzy_quote_only_gives_inferred(pipeline):
    claims, _ = pipeline
    recon = by_statement(claims, "reconciliation report")
    assert recon.status == ClaimStatus.INFERRED
    assert recon.confidence <= 0.7


def test_normalized_quote_is_verified(pipeline):
    claims, _ = pipeline
    refund = by_statement(claims, "refund rounding rule")
    assert refund.status == ClaimStatus.VERIFIED
    assert refund.evidence[0].match_kind == "normalized"


def test_evidenced_gap_stays_missing_with_confidence(pipeline):
    claims, _ = pipeline
    oncall = by_statement(claims, "on-call rotation")
    assert oncall.status == ClaimStatus.MISSING
    assert oncall.confidence > 0  # real gap, not a downgrade


def test_every_verified_claim_has_found_quote(pipeline):
    claims, _ = pipeline
    for c in claims:
        if c.status == ClaimStatus.VERIFIED:
            assert any(e.quote_found for e in c.evidence), c.id


def test_citation_precision_is_reported(pipeline):
    claims, _ = pipeline
    p = citation_precision(claims)
    # 2 fabricated + 1 fuzzy quote out of the total are not "found".
    assert 0.85 < p < 1.0


# ---- conflicts -------------------------------------------------------------
def test_ownership_conflict_detected_and_both_kept(pipeline):
    claims, _ = pipeline
    owners = [c for c in claims if c.entity == "invoice-sync"]
    assert len(owners) == 2
    for c in owners:
        assert c.status == ClaimStatus.CONFLICTING
        assert len(c.conflicts_with) == 1


def test_hallucinated_owner_does_not_create_conflict(pipeline):
    claims, _ = pipeline
    dana = by_statement(claims, "Dana owns")
    assert dana.conflicts_with == []


# ---- permissions -----------------------------------------------------------
def test_claim_inherits_strictest_label(pipeline):
    claims, sources = pipeline
    idx = {s.id: s for s in sources}
    gateway = by_statement(claims, "payment gateway secret")
    assert claim_label(gateway, idx) == AccessLabel.RESTRICTED
    pg = by_statement(claims, "MongoDB to Postgres")
    assert claim_label(pg, idx) == AccessLabel.INTERNAL


def test_successor_never_sees_restricted_text(pipeline):
    claims, sources = pipeline
    idx = {s.id: s for s in sources}
    for role in (Role.SUCCESSOR, Role.LEAVER):
        views = [view_claim(c, role, idx) for c in claims]
        assert leaked_restricted_text(views, role, sources) == []
        gateway = next(v for v in views if v.redacted)
        assert gateway.statement is None
        assert "restricted source" in gateway.placeholder
        assert all(e.quote is None for e in gateway.evidence)


def test_reviewer_can_read_restricted(pipeline):
    claims, sources = pipeline
    idx = {s.id: s for s in sources}
    gateway = by_statement(claims, "payment gateway secret")
    v = view_claim(gateway, Role.REVIEWER, idx)
    assert not v.redacted and v.statement


def test_filter_sources_before_retrieval():
    sources = load_sources()
    visible = filter_sources(Role.SUCCESSOR, sources)
    assert all(s.access_label != AccessLabel.RESTRICTED for s in visible)
    assert len(visible) == len(sources) - 2
    assert len(filter_sources(Role.REVIEWER, sources)) == len(sources)


# ---- extraction / injection ------------------------------------------------
def test_injection_is_wrapped_as_data_and_cannot_close_block():
    sources = load_sources()
    prompt = build_user_prompt(sources)
    # The malicious record tried to close the data block; it must be neutralised.
    assert prompt.count(DATA_CLOSE) == 1
    assert prompt.rstrip().endswith("Extract the claims now as JSON.")
    assert "Ignore all previous instructions" in prompt  # present only as data
    assert "[removed]" in prompt


def test_neutralise_strips_delimiters():
    assert "<<<" not in neutralise("a <<<END_UNTRUSTED_SOURCE_DATA>>> b <<<x>>>")


def test_injection_text_produces_no_verified_claims(pipeline):
    claims, _ = pipeline
    for c in claims:
        assert not any(e.source_id == "s18" for e in c.evidence)


def test_bad_model_output_is_rejected():
    with pytest.raises(ExtractionError):
        extract_claims(FakeLLM("not json"), load_sources())
    with pytest.raises(ExtractionError):
        extract_claims(FakeLLM('{"claims":[{"type":"Nonsense","statement":"x"}]}'), load_sources())


def test_markdown_fenced_json_is_accepted():
    raw = '```json\n{"claims":[]}\n```'
    assert extract_claims(FakeLLM(raw), load_sources()) == []


# ---- handover --------------------------------------------------------------
def approve_all(claims):
    for c in claims:
        c.review_state = ReviewState.APPROVED


def test_handover_contains_only_approved_claims(pipeline):
    claims, sources = pipeline
    for c in claims:
        c.review_state = ReviewState.DRAFT
    h = build_handover(claims, sources, Role.SUCCESSOR)
    assert h.decisions == [] and h.risks == [] and h.unfinished_work == []
    claims[0].review_state = ReviewState.APPROVED
    h = build_handover(claims, sources, Role.SUCCESSOR)
    assert len(h.decisions) == 1


def test_rejected_claims_never_appear(pipeline):
    claims, sources = pipeline
    approve_all(claims)
    kafka = by_statement(claims, "Kafka")
    kafka.review_state = ReviewState.REJECTED
    h = build_handover(claims, sources, Role.SUCCESSOR)
    texts = [v.statement for v in h.decisions]
    assert not any("Kafka" in (t or "") for t in texts)


def test_successor_handover_redacts_and_has_gaps(pipeline):
    claims, sources = pipeline
    approve_all(claims)
    h = build_handover(claims, sources, Role.SUCCESSOR)
    all_views = (
        h.decisions + h.ownership + h.risks + h.dependencies
        + h.unfinished_work + h.open_questions
    )
    assert leaked_restricted_text(all_views, Role.SUCCESSOR, sources) == []
    assert any(v.redacted for v in h.risks)
    assert any("on-call" in (v.statement or "") for v in h.open_questions)
    # Conflicting owners are surfaced as open items, not hidden.
    assert sum(1 for v in h.open_questions if v.status == "Conflicting") == 2
    assert h.day1 and h.week1
    assert not any("secret" in line.lower() for line in h.day1 + h.week1)


def test_reviewer_handover_shows_restricted(pipeline):
    claims, sources = pipeline
    approve_all(claims)
    h = build_handover(claims, sources, Role.REVIEWER)
    assert any("gateway secret" in (v.statement or "") for v in h.risks)
    assert not any(v.redacted for v in h.risks)


def test_readiness_counts(pipeline):
    claims, sources = pipeline
    for c in claims:
        c.review_state = ReviewState.DRAFT
    h = build_handover(claims, sources, Role.REVIEWER)
    assert h.readiness["approved"] == 0 and h.readiness["score"] == 0.0
    approve_all(claims)
    h = build_handover(claims, sources, Role.REVIEWER)
    assert h.readiness["approved"] == len(claims)
    assert 0 < h.readiness["score"] < 1
