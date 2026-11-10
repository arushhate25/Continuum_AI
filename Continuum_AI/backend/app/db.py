"""Postgres storage (SQLAlchemy 2.0). Implements the same interface as
store.MemoryStore. Domain objects are stored as JSON documents, which keeps
the schema small and the migration simple for the hackathon.

NOTE: not exercised by the automated tests in the build workspace (no
SQLAlchemy there). Verify with a real Postgres before relying on it.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, Integer, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import normalize_database_url
from .core.models import Claim, Source


class Base(DeclarativeBase):
    pass


class SourceRow(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class ClaimRow(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class VersionRow(Base):
    __tablename__ = "claim_versions"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class AuditRow(Base):
    __tablename__ = "audit_log"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[dict] = mapped_column(JSON)


class MetaRow(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class SqlStore:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(normalize_database_url(database_url), pool_pre_ping=True)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def reset(self) -> None:
        with self.Session.begin() as s:
            for model in (ClaimRow, SourceRow, VersionRow, AuditRow, MetaRow):
                s.execute(delete(model))

    def put_sources(self, sources: list[Source]) -> None:
        with self.Session.begin() as s:
            s.execute(delete(SourceRow))
            s.add_all(SourceRow(id=x.id, data=x.model_dump(mode="json")) for x in sources)

    def list_sources(self) -> list[Source]:
        with self.Session() as s:
            return [Source(**r.data) for r in s.scalars(select(SourceRow).order_by(SourceRow.id))]

    def put_claims(self, claims: list[Claim]) -> None:
        with self.Session.begin() as s:
            s.execute(delete(ClaimRow))
            s.execute(delete(VersionRow))
            s.add_all(ClaimRow(id=c.id, data=c.model_dump(mode="json")) for c in claims)

    def list_claims(self) -> list[Claim]:
        with self.Session() as s:
            return [Claim(**r.data) for r in s.scalars(select(ClaimRow).order_by(ClaimRow.id))]

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        with self.Session() as s:
            row = s.get(ClaimRow, claim_id)
            return Claim(**row.data) if row else None

    def save_claim(self, claim: Claim) -> None:
        with self.Session.begin() as s:
            row = s.get(ClaimRow, claim.id)
            data = claim.model_dump(mode="json")
            if row:
                row.data = data
            else:
                s.add(ClaimRow(id=claim.id, data=data))

    def add_version(self, claim_id: str, snapshot: dict) -> None:
        with self.Session.begin() as s:
            s.add(VersionRow(claim_id=claim_id, data=snapshot))

    def list_versions(self, claim_id: str) -> list[dict]:
        with self.Session() as s:
            rows = s.scalars(
                select(VersionRow).where(VersionRow.claim_id == claim_id).order_by(VersionRow.pk)
            )
            return [r.data for r in rows]

    def add_audit(self, entry: dict) -> None:
        with self.Session.begin() as s:
            s.add(AuditRow(data=entry))

    def list_audit(self) -> list[dict]:
        with self.Session() as s:
            return [r.data for r in s.scalars(select(AuditRow).order_by(AuditRow.pk))]

    def set_meta(self, key: str, value: Any) -> None:
        with self.Session.begin() as s:
            row = s.get(MetaRow, key)
            if row:
                row.value = value
            else:
                s.add(MetaRow(key=key, value=value))

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self.Session() as s:
            row = s.get(MetaRow, key)
            return row.value if row else default
