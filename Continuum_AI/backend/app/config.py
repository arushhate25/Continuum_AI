"""Small pure helpers for configuration."""
from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """Neon/Render give `postgresql://...`; SQLAlchemy + psycopg3 needs
    `postgresql+psycopg://...`."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["http://localhost:3000"]
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
