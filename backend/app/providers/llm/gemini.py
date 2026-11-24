"""Gemini text embeddings, used to rank jobs against the resume profile."""

import math
from typing import Protocol

import httpx

from app.core.errors import ProviderError

NAME = "gemini"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
EMBEDDING_SIZE = 768  # matches the vector(768) columns in migration 0002
MAX_TEXT_CHARS = 8000


class Embedder(Protocol):
    def embed(self, text: str, task_type: str) -> list[float]: ...


class GeminiEmbedder:
    def __init__(
        self, client: httpx.Client, api_key: str, model: str, base_url: str = BASE_URL
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._url = f"{base_url}/models/{model}:embedContent"

    def embed(self, text: str, task_type: str) -> list[float]:
        body = {
            "content": {"parts": [{"text": text[:MAX_TEXT_CHARS]}]},
            "embedContentConfig": {
                "taskType": task_type,
                "outputDimensionality": EMBEDDING_SIZE,
            },
        }
        try:
            response = self._client.post(
                self._url, json=body, headers={"x-goog-api-key": self._api_key}
            )
        except httpx.HTTPError as error:
            raise ProviderError(NAME, f"request failed ({type(error).__name__})") from None
        if response.status_code != httpx.codes.OK:
            raise ProviderError(NAME, f"HTTP {response.status_code}")

        try:
            values = [float(value) for value in response.json()["embedding"]["values"]]
        except (KeyError, TypeError, ValueError):
            raise ProviderError(NAME, "unexpected response format") from None
        length = math.sqrt(sum(value * value for value in values))
        if len(values) != EMBEDDING_SIZE or length == 0:
            raise ProviderError(NAME, "unexpected embedding size")
        return [value / length for value in values]
