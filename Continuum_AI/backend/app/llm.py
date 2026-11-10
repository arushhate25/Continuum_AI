"""LLM provider adapters (Gemini, Groq) using only the standard library.

Each client exposes `complete_json(system, user) -> str`. HTTP goes through an
injectable `transport(url, headers, payload) -> dict`, so tests never touch
the network. API keys are sent in headers, never in URLs, and never logged.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

Transport = Callable[[str, dict, dict], dict]


class LLMError(Exception):
    """Permanent provider failure (bad key, bad request, bad response)."""


class LLMTransientError(LLMError):
    """Retryable failure: rate limit (429), 5xx, network."""


def urllib_transport(url: str, headers: dict, payload: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:200]
        msg = f"HTTP {exc.code} from provider: {body}"
        if exc.code == 429 or exc.code >= 500:
            raise LLMTransientError(msg) from exc
        raise LLMError(msg) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMTransientError(f"network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError("provider returned non-JSON response") from exc


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", transport: Transport = urllib_transport):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.api_key, self.model, self.transport = api_key, model, transport

    def complete_json(self, system: str, user: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        data = self.transport(url, {"x-goog-api-key": self.api_key}, payload)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected Gemini response shape") from exc


class GroqClient:
    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", transport: Transport = urllib_transport):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set")
        self.api_key, self.model, self.transport = api_key, model, transport

    def complete_json(self, system: str, user: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = self.transport(url, {"Authorization": f"Bearer {self.api_key}"}, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected Groq response shape") from exc


class FallbackClient:
    """Try providers in order. Retries transient errors, then moves on.
    `used` records which provider actually answered."""

    def __init__(self, clients: list, attempts: int = 3, sleep: Callable[[float], None] = time.sleep):
        if not clients:
            raise LLMError("no LLM provider configured")
        self.clients, self.attempts, self.sleep = clients, attempts, sleep
        self.used: Optional[str] = None
        self.errors: list[str] = []

    def complete_json(self, system: str, user: str) -> str:
        self.errors = []
        for client in self.clients:
            for attempt in range(self.attempts):
                try:
                    out = client.complete_json(system, user)
                    self.used = client.name
                    return out
                except LLMTransientError as exc:
                    self.errors.append(f"{client.name}: {exc}")
                    if attempt < self.attempts - 1:
                        self.sleep(2 ** attempt)
                except LLMError as exc:
                    self.errors.append(f"{client.name}: {exc}")
                    break  # permanent: try next provider
        raise LLMError("all providers failed: " + " | ".join(self.errors))


def build_client(spec: Optional[str] = None, env: Optional[dict] = None):
    """Return (client, label). `spec` is e.g. "gemini,groq" or "mock".
    Mock is an explicit, labelled offline replay; it is never used as a silent
    fallback for a real provider."""
    env = env if env is not None else os.environ
    spec = (spec or env.get("LLM_PROVIDER") or "gemini,groq").strip().lower()
    if spec == "mock":
        from .demo import load_mock_llm

        return load_mock_llm(), "mock (offline sample replay, no LLM call)"
    clients = []
    for name in [p.strip() for p in spec.split(",") if p.strip()]:
        if name == "gemini" and env.get("GEMINI_API_KEY"):
            clients.append(GeminiClient(env["GEMINI_API_KEY"], env.get("GEMINI_MODEL", "gemini-2.5-flash")))
        elif name == "groq" and env.get("GROQ_API_KEY"):
            clients.append(GroqClient(env["GROQ_API_KEY"], env.get("GROQ_MODEL", "llama-3.3-70b-versatile")))
    if not clients:
        raise LLMError("no usable provider: set GEMINI_API_KEY or GROQ_API_KEY, or use provider=mock")
    return FallbackClient(clients), "+".join(c.name for c in clients)
