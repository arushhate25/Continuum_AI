"""Storage interface and an in-memory implementation.

The service layer only talks to this interface. `MemoryStore` is used for
tests and for running without a database; `db.SqlStore` implements the same
methods on Postgres.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol

from .core.models import Claim, Source


class Store(Protocol):
    def reset(self) -> None: ...
    def put_sources(self, sources: list[Source]) -> None: ...
    def list_sources(self) -> list[Source]: ...
    def put_claims(self, claims: list[Claim]) -> None: ...
    def list_claims(self) -> list[Claim]: ...
    def get_claim(self, claim_id: str) -> Optional[Claim]: ...
    def save_claim(self, claim: Claim) -> None: ...
    def add_version(self, claim_id: str, snapshot: dict) -> None: ...
    def list_versions(self, claim_id: str) -> list[dict]: ...
    def add_audit(self, entry: dict) -> None: ...
    def list_audit(self) -> list[dict]: ...
    def set_meta(self, key: str, value: Any) -> None: ...
    def get_meta(self, key: str, default: Any = None) -> Any: ...


class MemoryStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._sources: dict[str, Source] = {}
        self._claims: dict[str, Claim] = {}
        self._versions: dict[str, list[dict]] = {}
        self._audit: list[dict] = []
        self._meta: dict[str, Any] = {}

    def put_sources(self, sources: list[Source]) -> None:
        self._sources = {s.id: s.model_copy(deep=True) for s in sources}

    def list_sources(self) -> list[Source]:
        return [s.model_copy(deep=True) for s in self._sources.values()]

    def put_claims(self, claims: list[Claim]) -> None:
        self._claims = {c.id: c.model_copy(deep=True) for c in claims}
        self._versions = {}

    def list_claims(self) -> list[Claim]:
        return [c.model_copy(deep=True) for c in self._claims.values()]

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        c = self._claims.get(claim_id)
        return c.model_copy(deep=True) if c else None

    def save_claim(self, claim: Claim) -> None:
        self._claims[claim.id] = claim.model_copy(deep=True)

    def add_version(self, claim_id: str, snapshot: dict) -> None:
        self._versions.setdefault(claim_id, []).append(snapshot)

    def list_versions(self, claim_id: str) -> list[dict]:
        return list(self._versions.get(claim_id, []))

    def add_audit(self, entry: dict) -> None:
        self._audit.append(entry)

    def list_audit(self) -> list[dict]:
        return list(self._audit)

    def set_meta(self, key: str, value: Any) -> None:
        self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._meta.get(key, default)
