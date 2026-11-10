"""Demo data loader and offline pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from ..core.conflicts import detect_conflicts
from ..core.extraction import FakeLLM, extract_claims
from ..core.models import Claim, Source
from ..core.verifier import verify_all

DEMO_DIR = Path(__file__).parent


def load_sources() -> list[Source]:
    data = json.loads((DEMO_DIR / "demo_project.json").read_text(encoding="utf-8"))
    return [Source(**s) for s in data["sources"]]


def load_mock_llm() -> FakeLLM:
    return FakeLLM((DEMO_DIR / "mock_llm_output.json").read_text(encoding="utf-8"))


def run_pipeline(client=None, sources: list[Source] | None = None) -> tuple[list[Claim], list[Source]]:
    """Extract -> verify -> detect conflicts. Defaults to the offline demo."""
    sources = sources if sources is not None else load_sources()
    client = client or load_mock_llm()
    claims = extract_claims(client, sources)
    claims = verify_all(claims, sources)
    claims = detect_conflicts(claims)
    return claims, sources
