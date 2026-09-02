import os
from app.nodes import AIResponseNodeExecutor


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
    def raise_for_status(self):
        pass
    def json(self):
        return self._data


class FakeClient:
    last = None
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def post(self, url, json=None, headers=None):
        FakeClient.last = {"url": url, "json": json, "headers": headers}
        if "anthropic.com" in url:
            return FakeResponse({"content": [{"type": "text", "text": "anthropic ok"}]})
        if "generativelanguage.googleapis.com" in url:
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]})
        return FakeResponse({"choices": [{"message": {"content": "openai-compatible ok"}}]})


def run(monkeypatch, provider, key, model=None):
    monkeypatch.setattr("app.nodes.httpx.Client", FakeClient)
    monkeypatch.setenv("AI_API_KEY", key)
    executor = AIResponseNodeExecutor()
    state = {"variables": {}, "status": "running", "response": ""}
    node = {"id": "ai-1", "type": "ai", "config": {"provider": provider, "model": model or "test-model", "prompt": "Hello"}}
    result = executor.execute(node, state)
    return result, FakeClient.last


def test_openai(monkeypatch):
    result, req = run(monkeypatch, "openai", "key")
    assert "openai-compatible ok" in result["response"]
    assert "api.openai.com" in req["url"]
    assert req["headers"]["Authorization"] == "Bearer key"


def test_groq(monkeypatch):
    result, req = run(monkeypatch, "groq", "key")
    assert "openai-compatible ok" in result["response"]
    assert "api.groq.com" in req["url"]


def test_anthropic(monkeypatch):
    result, req = run(monkeypatch, "anthropic", "key")
    assert "anthropic ok" in result["response"]
    assert "api.anthropic.com" in req["url"]
    assert req["headers"]["x-api-key"] == "Bearer key" or req["headers"]["x-api-key"] == "key"


def test_gemini(monkeypatch):
    result, req = run(monkeypatch, "gemini", "key", "gemini-test")
    assert "gemini ok" in result["response"]
    assert "generativelanguage.googleapis.com" in req["url"]
    assert "key=key" in req["url"]


def test_custom_openai_compatible(monkeypatch):
    monkeypatch.setattr("app.nodes.httpx.Client", FakeClient)
    executor = AIResponseNodeExecutor()
    state = {"variables": {}, "status": "running", "response": ""}
    node = {"id": "ai-custom", "type": "ai", "config": {
        "provider": "custom",
        "api_url": "https://example.test/v1/chat/completions",
        "api_key": "custom-key",
        "model": "custom-model",
        "prompt": "Hello",
    }}
    result = executor.execute(node, state)
    assert "openai-compatible ok" in result["response"]
    req = FakeClient.last
    assert req
    assert req["url"] == "https://example.test/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer custom-key"

class GroqFallbackClient(FakeClient):
    def post(self, url, json=None, headers=None):
        GroqFallbackClient.last = {"url": url, "json": json, "headers": headers}
        if url.endswith("/chat/completions"):
            return type("R", (), {
                "status_code": 404,
                "text": "not found",
                "json": lambda self: {"error": {"message": "not found"}},
                "raise_for_status": lambda self: None,
            })()
        return FakeResponse({"output_text": "groq responses fallback ok"})


def test_groq_responses_fallback(monkeypatch):
    monkeypatch.setattr("app.nodes.httpx.Client", GroqFallbackClient)
    monkeypatch.setenv("GROQ_API_KEY", "key")
    executor = AIResponseNodeExecutor()
    state = {"variables": {}, "status": "running", "response": ""}
    node = {"id": "ai-groq", "type": "ai", "config": {
        "provider": "groq", "model": "llama-3.3-70b-versatile", "prompt": "Hello"
    }}
    result = executor.execute(node, state)
    assert "groq responses fallback ok" in result["response"]
    assert GroqFallbackClient.last["url"].endswith("/responses")


class GroqRetiredModelClient(FakeClient):
    def get(self, url, headers=None):
        return FakeResponse({
            "data": [
                {"id": "openai/gpt-oss-120b"},
                {"id": "openai/gpt-oss-20b"},
            ]
        })

    def post(self, url, json=None, headers=None):
        GroqRetiredModelClient.last = {"url": url, "json": json, "headers": headers}
        if json and json.get("model") == "llama-3.3-70b-versatile":
            return type("R", (), {
                "status_code": 404,
                "text": "model not found",
                "json": lambda self: {"error": {"message": "The model does not exist or you do not have access to it.", "code": "model_not_found"}},
                "raise_for_status": lambda self: None,
            })()
        return FakeResponse({"choices": [{"message": {"content": "recovered with active model"}}]})


def test_groq_recovers_retired_model(monkeypatch):
    monkeypatch.setattr("app.nodes.httpx.Client", GroqRetiredModelClient)
    monkeypatch.setenv("GROQ_API_KEY", "key")
    executor = AIResponseNodeExecutor()
    state = {"variables": {}, "status": "running", "response": ""}
    node = {"id": "ai-groq-retired", "type": "ai", "config": {
        "provider": "groq", "model": "llama-3.3-70b-versatile", "prompt": "Hello"
    }}
    result = executor.execute(node, state)
    assert "recovered with active model" in result["response"]
    assert GroqRetiredModelClient.last["json"]["model"] == "openai/gpt-oss-120b"
