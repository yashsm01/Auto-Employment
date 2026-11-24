"""Reads a public company website through Jina Reader, which checks robots.txt."""

import ipaddress
import re
from urllib.parse import urlsplit

import httpx

from app.core.errors import ProviderError

NAME = "website"
READER_URL = "https://r.jina.ai/"
BOT_NAME = "JobAutopilot"
MAX_TEXT_CHARS = 120_000  # long, so footer links such as "Careers" are kept
_SITE_ERROR = re.compile(r"Warning: Target URL returned error (\d{3})")
_BLOCKED_DOMAINS = (
    "seek.co.nz",
    "seek.com",
    "seek.com.au",
    "linkedin.com",
    "indeed.com",
    "indeed.co.nz",
    "trademe.co.nz",
    "facebook.com",
    "instagram.com",
)


def is_allowed_url(url: str) -> bool:
    """Public web pages only. Job boards that ban scraping and private addresses are refused."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").casefold()
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or "." not in host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return not any(host == d or host.endswith(f".{d}") for d in _BLOCKED_DOMAINS)
    return False


class WebsiteReader:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def read(self, url: str) -> str:
        if not is_allowed_url(url):
            raise ProviderError(NAME, "this address is not allowed")
        try:
            response = self._client.get(
                f"{READER_URL}{url}", headers={"X-Robots-Txt": BOT_NAME, "DNT": "1"}
            )
        except httpx.HTTPError as error:
            raise ProviderError(NAME, f"request failed ({type(error).__name__})") from None
        if response.status_code != httpx.codes.OK:
            raise ProviderError(NAME, f"HTTP {response.status_code}")
        blocked = _SITE_ERROR.search(response.text[:3000])
        if blocked:
            raise ProviderError(NAME, f"the site refused access (HTTP {blocked[1]})")
        return response.text[:MAX_TEXT_CHARS]
