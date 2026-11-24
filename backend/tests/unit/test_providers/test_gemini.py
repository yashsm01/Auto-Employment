import json
import math

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.llm.gemini import EMBEDDING_SIZE, GeminiEmbedder


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _vector(first: float = 3.0, second: float = 4.0) -> list[float]:
    return [first, second] + [0.0] * (EMBEDDING_SIZE - 2)


def test_embed_sends_the_documented_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embedding": {"values": _vector()}})

    GeminiEmbedder(_client(handler), "KEY", "gemini-embedding-2").embed("Python", "RETRIEVAL_QUERY")

    assert seen["path"] == "/v1beta/models/gemini-embedding-2:embedContent"
    assert seen["key"] == "KEY"
    assert seen["body"] == {
        "content": {"parts": [{"text": "Python"}]},
        "embedContentConfig": {"taskType": "RETRIEVAL_QUERY", "outputDimensionality": 768},
    }


def test_embed_returns_a_unit_vector():
    client = _client(lambda _: httpx.Response(200, json={"embedding": {"values": _vector()}}))

    values = GeminiEmbedder(client, "KEY", "model").embed("text", "RETRIEVAL_DOCUMENT")

    assert values[:2] == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(value * value for value in values)) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "payload",
    [{"embedding": {"values": [1.0, 2.0]}}, {"embedding": {"values": [0.0] * 768}}, {}],
)
def test_embed_rejects_an_unusable_vector(payload):
    client = _client(lambda _: httpx.Response(200, json=payload))

    with pytest.raises(ProviderError):
        GeminiEmbedder(client, "KEY", "model").embed("text", "RETRIEVAL_DOCUMENT")


def test_embed_error_never_includes_the_key():
    client = _client(lambda _: httpx.Response(403, text="bad key SECRETKEY"))

    with pytest.raises(ProviderError) as caught:
        GeminiEmbedder(client, "SECRETKEY", "model").embed("text", "RETRIEVAL_DOCUMENT")

    assert "SECRETKEY" not in str(caught.value)
    assert "403" in str(caught.value)
