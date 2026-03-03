import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, get_payloads: dict[str, _FakeResponse], post_payloads: dict[str, _FakeResponse]):
        self._get_payloads = get_payloads
        self._post_payloads = post_payloads
        self.get_calls: list[str] = []
        self.post_calls: list[str] = []

    def get(self, url: str, headers=None, timeout=None):  # noqa: ANN001
        del headers, timeout
        self.get_calls.append(url)
        return self._get_payloads.get(url, _FakeResponse(404, {"error": "not found"}))

    def post(self, url: str, json=None, headers=None, timeout=None):  # noqa: ANN001
        del json, headers, timeout
        self.post_calls.append(url)
        return self._post_payloads.get(url, _FakeResponse(404, {"error": "not found"}))

    def close(self) -> None:
        return None


def test_generate_uses_v3_chat_when_v1_models_missing() -> None:
    cfg = OpenAICompatConfig(
        base_url="http://localhost:8000",
        model="demo-model",
        api_version="auto",
        healthcheck_ttl_sec=3600,
    )
    backend = OpenAICompatBackend(cfg)
    backend._session = _FakeSession(
        get_payloads={
            "http://localhost:8000/v1/models": _FakeResponse(404, {"error": "v1 unavailable"}),
            "http://localhost:8000/v3/models": _FakeResponse(200, {"data": [{"id": "demo-model"}]}),
        },
        post_payloads={
            "http://localhost:8000/v3/chat/completions": _FakeResponse(
                200,
                {
                    "choices": [{"message": {"content": "hello"}}],
                    "usage": {"completion_tokens": 11},
                },
            ),
        },
    )

    first = backend.generate("prompt-1")
    second = backend.generate("prompt-2")

    assert first.text == "hello"
    assert first.tokens_used == 11
    assert second.text == "hello"
    assert backend._session.get_calls.count("http://localhost:8000/v1/models") == 1
    assert backend._session.get_calls.count("http://localhost:8000/v3/models") == 1
    assert backend._session.post_calls == [
        "http://localhost:8000/v3/chat/completions",
        "http://localhost:8000/v3/chat/completions",
    ]


def test_embedded_v3_base_url_does_not_duplicate_prefix() -> None:
    cfg = OpenAICompatConfig(
        base_url="http://ovms.local:8000/v3",
        model="demo-model",
        api_version="auto",
        healthcheck_ttl_sec=3600,
    )
    backend = OpenAICompatBackend(cfg)
    backend._session = _FakeSession(
        get_payloads={
            "http://ovms.local:8000/v3/models": _FakeResponse(200, {"data": [{"id": "demo-model"}]}),
        },
        post_payloads={
            "http://ovms.local:8000/v3/chat/completions": _FakeResponse(
                200,
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"completion_tokens": 3},
                },
            ),
        },
    )

    res = backend.generate("prompt")

    assert res.text == "ok"
    combined_calls = backend._session.get_calls + backend._session.post_calls
    assert all("/v3/v3/" not in call for call in combined_calls)


if __name__ == "__main__":
    test_generate_uses_v3_chat_when_v1_models_missing()
    test_embedded_v3_base_url_does_not_duplicate_prefix()
    print("test_openai_compat_backend: PASS")
