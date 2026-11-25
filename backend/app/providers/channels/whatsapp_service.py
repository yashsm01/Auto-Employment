"""Talks to the WhatsApp Web service (whatsapp-service/): send updates, show the QR, log out."""

from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.errors import ProviderError

NAME = "whatsapp"


class WhatsAppService:
    def __init__(self, client: httpx.Client, url: str, token: str = "",
                 to_field: str = "to", text_field: str = "message") -> None:
        self._client = client
        self._url = url
        parts = urlsplit(url)
        self._base = f"{parts.scheme}://{parts.netloc}"
        self._token = token
        self._to_field = to_field
        self._text_field = text_field

    def _request(self, method: str, url: str, body: dict | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            response = self._client.request(method, url, json=body, headers=headers)
        except httpx.HTTPError as error:
            reason = type(error).__name__
            raise ProviderError(NAME, f"the WhatsApp service did not answer ({reason})") from None
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400:
            detail = str(data.get("error") or "")[:200] if isinstance(data, dict) else ""
            suffix = f": {detail}" if detail else ""
            raise ProviderError(
                NAME, f"the WhatsApp service returned HTTP {response.status_code}{suffix}"
            )
        return data if isinstance(data, dict) else {}

    def send(self, to: str, text: str) -> None:
        self._request("POST", self._url, {self._to_field: to, self._text_field: text})

    def status(self) -> dict[str, Any]:
        return self._request("GET", f"{self._base}/status")

    def logout(self) -> None:
        self._request("POST", f"{self._base}/logout")
