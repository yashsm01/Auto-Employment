from dataclasses import dataclass

import httpx

from app.core.errors import ProviderError
from app.providers.company.website_reader import is_allowed_url

NAME = "tavily"
URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str


class TavilySearch:
    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def search(self, query: str) -> list[SearchHit]:
        body = {"query": query, "search_depth": "basic", "max_results": 3, "topic": "general"}
        try:
            response = self._client.post(
                URL, json=body, headers={"Authorization": f"Bearer {self._api_key}"}
            )
        except httpx.HTTPError as error:
            raise ProviderError(NAME, f"request failed ({type(error).__name__})") from None
        if response.status_code != httpx.codes.OK:
            raise ProviderError(NAME, f"HTTP {response.status_code}")

        try:
            results = response.json().get("results") or []
            return [
                SearchHit(title=item.get("title") or "", url=item["url"], content=item["content"])
                for item in results
                if is_allowed_url(item.get("url") or "") and item.get("content")
            ]
        except (ValueError, KeyError, AttributeError):
            raise ProviderError(NAME, "unexpected response format") from None
