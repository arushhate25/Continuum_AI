import pytest

from app.llm import (
    FallbackClient,
    GeminiClient,
    GroqClient,
    LLMError,
    LLMTransientError,
    build_client,
)


def test_gemini_request_and_parse():
    seen = {}

    def transport(url, headers, payload):
        seen.update(url=url, headers=headers, payload=payload)
        return {"candidates": [{"content": {"parts": [{"text": '{"claims":[]}'}]}}]}

    out = GeminiClient("KEY123", "gemini-2.5-flash", transport).complete_json("SYS", "USER")
    assert out == '{"claims":[]}'
    assert "KEY123" not in seen["url"]  # key never in URL
    assert seen["headers"] == {"x-goog-api-key": "KEY123"}
    assert seen["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["payload"]["system_instruction"]["parts"][0]["text"] == "SYS"


def test_groq_request_and_parse():
    seen = {}

    def transport(url, headers, payload):
        seen.update(url=url, headers=headers, payload=payload)
        return {"choices": [{"message": {"content": '{"claims":[]}'}}]}

    out = GroqClient("GK", "llama-3.3-70b-versatile", transport).complete_json("SYS", "USER")
    assert out == '{"claims":[]}'
    assert seen["headers"]["Authorization"] == "Bearer GK"
    assert seen["payload"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in seen["payload"]["messages"]] == ["system", "user"]


def test_bad_response_shapes_raise_permanent_errors():
    with pytest.raises(LLMError):
        GeminiClient("k", transport=lambda *a: {"oops": 1}).complete_json("s", "u")
    with pytest.raises(LLMError):
        GroqClient("k", transport=lambda *a: {"choices": []}).complete_json("s", "u")


def test_missing_key_is_rejected():
    with pytest.raises(LLMError):
        GeminiClient("")
    with pytest.raises(LLMError):
        GroqClient("")


class Stub:
    def __init__(self, name, results):
        self.name, self.results, self.calls = name, list(results), 0

    def complete_json(self, system, user):
        self.calls += 1
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_fallback_retries_transient_then_succeeds():
    a = Stub("gemini", [LLMTransientError("429"), "OK"])
    fb = FallbackClient([a], attempts=3, sleep=lambda s: None)
    assert fb.complete_json("s", "u") == "OK"
    assert a.calls == 2 and fb.used == "gemini"


def test_fallback_moves_to_next_provider():
    a = Stub("gemini", [LLMTransientError("429")] * 3)
    b = Stub("groq", ["FROM_GROQ"])
    fb = FallbackClient([a, b], attempts=3, sleep=lambda s: None)
    assert fb.complete_json("s", "u") == "FROM_GROQ"
    assert fb.used == "groq" and a.calls == 3


def test_permanent_error_skips_retries():
    a = Stub("gemini", [LLMError("bad key")])
    b = Stub("groq", ["OK"])
    fb = FallbackClient([a, b], attempts=3, sleep=lambda s: None)
    assert fb.complete_json("s", "u") == "OK"
    assert a.calls == 1


def test_all_failing_raises_without_leaking_keys():
    a = Stub("gemini", [LLMError("HTTP 400")])
    fb = FallbackClient([a], sleep=lambda s: None)
    with pytest.raises(LLMError) as exc:
        fb.complete_json("s", "u")
    assert "all providers failed" in str(exc.value)


def test_build_client_mock_is_explicit_and_labelled():
    client, label = build_client("mock", env={})
    assert "mock" in label and hasattr(client, "complete_json")


def test_build_client_requires_keys_and_never_falls_back_to_mock():
    with pytest.raises(LLMError):
        build_client("gemini,groq", env={})


def test_build_client_uses_available_keys_in_order():
    client, label = build_client(None, env={"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m"})
    assert label == "gemini+groq"
    assert [c.name for c in client.clients] == ["gemini", "groq"]
