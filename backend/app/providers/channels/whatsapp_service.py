"""Sends WhatsApp updates to the user through their own WhatsApp service (a separate backend)."""

import httpx

from app.core.errors import ProviderError

NAME = "whatsapp"


class WhatsAppService:
    def __init__(self, client: httpx.Client, url: str, token: str = "",
                 to_field: str = "to", text_field: str = "message") -> None:
        self._client = client
        self._url = url
        self._token = token
        self._to_field = to_field
        self._text_field = text_field

    def send(self, to: str, text: str) -> None:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            response = self._client.post(
                self._url, json={self._to_field: to, self._text_field: text}, headers=headers
            )
        except httpx.HTTPError as error:
            reason = type(error).__name__
            raise ProviderError(NAME, f"the WhatsApp service did not answer ({reason})") from None
        if response.status_code >= 400:
            raise ProviderError(NAME, f"the WhatsApp service returned HTTP {response.status_code}")
