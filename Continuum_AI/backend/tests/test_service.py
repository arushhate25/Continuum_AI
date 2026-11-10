import pytest

from app.config import normalize_database_url, parse_origins
from app.core.extraction import ExtractionError, FakeLLM
from app.core.models import ReviewState, Role
from app.demo import load_mock_llm
from app.service import BadRequest, Forbidden, NotFound, Service
from app.store import MemoryStore


def make_service(llm=None):
    def factory(provider=None):
        client = llm or load_mock_llm()
        return client, "mock (test)"

    return Service(MemoryStore(), factory)


@pytest.fixture()
def svc():
    s = make_service()
    s.load_demo(Role.REVIEWER)
    s.extract(Role.REVIEWER)
    return s


def claim_id(svc, fragment):
    return next(v.id for v in svc.list_claims(Role.REVIEWER) if fragment in (v.statement or ""))


# ---- role gating -----------------------------------------------------------
def test_only_staff_can_load_and_extract():
    s = make_service()
    for role in (Role.SUCCESSOR, Role.LEAVER):
        with pytest.raises(Forbidden):
            s.load_demo(role)
    s.load_demo(Role.ADMIN)
    for role in (Role.SUCCESSOR, Role.LEAVER):
        with pytest.raises(Forbidden):
            s.extract(role)


def test_extract_without_sources_is_a_clear_error():
    with pytest.raises(BadRequest):
        make_service().extract(Role.REVIEWER)


def test_successor_cannot_list_claims_or_sources(svc):
    with pytest.raises(Forbidden):
        svc.list_claims(Role.SUCCESSOR)
    with pytest.raises(Forbidden):
        svc.list_sources(Role.SUCCESSOR)
    with pytest.raises(Forbidden):
        svc.get_claim(Role.SUCCESSOR, "c001")


def test_leaver_claim_list_is_redacted(svc):
    views = svc.list_claims(Role.LEAVER)
    assert any(v.redacted and v.statement is None for v in views)
    assert all("gateway secret" not in (v.statement or "") for v in views)


def test_sources_filtered_for_leaver(svc):
    assert len(svc.list_sources(Role.LEAVER)) == 23
    assert len(svc.list_sources(Role.REVIEWER)) == 25


def test_only_staff_can_review_and_read_audit(svc):
    with pytest.raises(Forbidden):
        svc.review(Role.LEAVER, "c001", "approve")
    with pytest.raises(Forbidden):
        svc.audit_log(Role.SUCCESSOR)
    with pytest.raises(Forbidden):
        svc.metrics(Role.LEAVER)


# ---- workflow --------------------------------------------------------------
def test_status_reports_provider_and_counts(svc):
    st = svc.status()
    assert st["sources"] == 25 and st["claims"] == 19
    assert st["extraction_provider"] == "mock (test)"
    assert st["by_status"]["Conflicting"] == 2


def test_approve_creates_version_and_audit(svc):
    cid = claim_id(svc, "MongoDB to Postgres")
    v = svc.review(Role.REVIEWER, cid, "approve")
    assert v.review_state == "approved" and v.version == 2
    detail = svc.get_claim(Role.REVIEWER, cid)
    assert len(detail["versions"]) == 1 and detail["versions"][0]["version"] == 1
    assert any(e["action"] == "claim_approve" and e["detail"]["claim"] == cid for e in svc.audit_log(Role.ADMIN))


def test_cannot_approve_claim_without_verified_evidence(svc):
    kafka = claim_id(svc, "Kafka")
    with pytest.raises(BadRequest):
        svc.review(Role.REVIEWER, kafka, "approve")
    # but it can be rejected
    assert svc.review(Role.REVIEWER, kafka, "reject").review_state == "rejected"


def test_edit_downgrades_verified_and_requires_text(svc):
    cid = claim_id(svc, "MongoDB to Postgres")
    with pytest.raises(BadRequest):
        svc.review(Role.REVIEWER, cid, "edit", statement="   ")
    v = svc.review(Role.REVIEWER, cid, "edit", statement="Invoices move to Postgres (edited).")
    assert v.status == "Inferred" and v.review_state == "draft"
    assert any("edited" in n for n in v.notes)


def test_unknown_claim_and_action(svc):
    with pytest.raises(NotFound):
        svc.review(Role.REVIEWER, "nope", "approve")
    with pytest.raises(BadRequest):
        svc.review(Role.REVIEWER, "c001", "publish")


def test_draft_claims_are_not_in_handover(svc):
    h = svc.handover(Role.SUCCESSOR)
    assert h.decisions == [] and h.readiness["approved"] == 0
    cid = claim_id(svc, "MongoDB to Postgres")
    svc.review(Role.REVIEWER, cid, "approve")
    h = svc.handover(Role.SUCCESSOR)
    assert len(h.decisions) == 1


def test_end_to_end_successor_handover_has_no_restricted_text(svc):
    for v in svc.list_claims(Role.REVIEWER):
        try:
            svc.review(Role.REVIEWER, v.id, "approve")
        except BadRequest:
            svc.review(Role.REVIEWER, v.id, "reject")
    h = svc.handover(Role.SUCCESSOR)
    blob = h.model_dump_json().lower()
    assert "gateway secret" not in blob and "legal reviews" not in blob
    assert any(v.redacted for v in h.risks)
    assert "kafka" not in blob
    m = svc.metrics(Role.REVIEWER)
    assert m["restricted_leaks_by_role"] == {"successor": [], "leaver": []}
    assert m["restricted_sources"] == 2
    assert any(e["action"] == "handover_viewed" for e in svc.audit_log(Role.REVIEWER))


def test_reload_demo_resets_everything(svc):
    svc.review(Role.REVIEWER, claim_id(svc, "MongoDB to Postgres"), "approve")
    svc.load_demo(Role.REVIEWER)
    st = svc.status()
    assert st["claims"] == 0 and st["approved"] == 0


def test_bad_llm_output_surfaces_as_extraction_error():
    s = make_service(FakeLLM("garbage"))
    s.load_demo(Role.REVIEWER)
    with pytest.raises(ExtractionError):
        s.extract(Role.REVIEWER)
    assert s.status()["claims"] == 0


# ---- config helpers --------------------------------------------------------
def test_database_url_normalised():
    assert normalize_database_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalize_database_url("postgres://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"


def test_origins_parsed():
    assert parse_origins(None) == ["http://localhost:3000"]
    assert parse_origins("https://a.vercel.app/, http://localhost:3000") == ["https://a.vercel.app", "http://localhost:3000"]
