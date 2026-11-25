"""OmniDimension AI phone calls over its REST API (https://omnidim.io/api/v1)."""

from typing import Any

import httpx

from app.core.errors import ProviderError

NAME = "omnidim"
BASE_URL = "https://omnidim.io/api/v1"
LOG_PAGE_SIZE = 50


class OmniDimClient:
    def __init__(self, client: httpx.Client, api_key: str, base_url: str = BASE_URL) -> None:
        self._client = client
        self._key = api_key
        self._base = base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(
                method, f"{self._base}{path}",
                headers={"Authorization": f"Bearer {self._key}"}, **kwargs,
            )
        except httpx.HTTPError as error:
            raise ProviderError(NAME, f"request failed ({type(error).__name__})") from None
        if response.status_code in (401, 403):
            raise ProviderError(NAME, "the API key was refused")
        if response.status_code >= 400:
            raise ProviderError(NAME, f"HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise ProviderError(NAME, "the answer was not JSON") from None

    def dispatch(
        self,
        *,
        agent_id: int,
        to_number: str,
        from_number_id: int | None = None,
        call_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        post_call_actions: dict[str, Any] | None = None,
    ) -> str:
        """Queue one call. Returns OmniDimension's request id."""
        body: dict[str, Any] = {"agent_id": agent_id, "to_number": to_number}
        if from_number_id is not None:
            body["from_number_id"] = from_number_id
        if call_context:
            body["call_context"] = call_context
        if metadata:
            body["metadata"] = metadata
        if post_call_actions:
            body["__post_call_actions"] = post_call_actions
        data = self._request("POST", "/calls/dispatch", json=body)
        if not data.get("success", True) or data.get("requestId") is None:
            raise ProviderError(NAME, f"the call was not dispatched ({data.get('status')})")
        return str(data["requestId"])

    def find_log(self, *, agent_id: int, app_call_id: str, pages: int = 3) -> dict | None:
        """The call log carrying our id in its metadata, newest pages first."""
        for page in range(1, pages + 1):
            data = self._request(
                "GET", "/calls/logs",
                params={"agentid": agent_id, "pageno": page, "pagesize": LOG_PAGE_SIZE},
            )
            rows = data.get("call_log_data") or []
            for row in rows:
                if (row.get("metadata") or {}).get("app_call_id") == app_call_id:
                    return row
            if len(rows) < LOG_PAGE_SIZE and page > 1:
                break
        return None
