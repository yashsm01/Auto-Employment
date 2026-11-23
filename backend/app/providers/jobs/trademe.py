"""Trade Me Jobs search API.

Reference: https://developer.trademe.co.nz/api-reference/search-methods/jobs-search
Auth: OAuth 1.0a PLAINTEXT. The token is optional in this client because Trade Me
documents application-only calls, but does not confirm Jobs search accepts them.
"""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import ProviderError
from app.core.normalize import parse_annual_salary
from app.schemas.job import JobDraft

BASE_URL = "https://api.trademe.co.nz"
SEARCH_PATH = "/v1/Search/Jobs.json"
DEFAULT_ROWS = 50
_MS_DATE = re.compile(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/")


def _encode(value: str) -> str:
    return quote(value, safe="-._~")


def build_auth_header(
    consumer_key: str,
    consumer_secret: str,
    token: str | None = None,
    token_secret: str | None = None,
) -> str:
    signature = f"{_encode(consumer_secret)}&{_encode(token_secret or '')}"
    parts = [f'oauth_consumer_key="{_encode(consumer_key)}"']
    if token:
        parts.append(f'oauth_token="{_encode(token)}"')
    parts.append('oauth_signature_method="PLAINTEXT"')
    parts.append(f'oauth_signature="{_encode(signature)}"')
    return "OAuth " + ", ".join(parts)


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    match = _MS_DATE.fullmatch(value)
    if match:
        return datetime.fromtimestamp(int(match[1]) / 1000, tz=UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    transparency = item.get("JobsSalaryTransparency") or {}
    for text in (transparency.get("ApproximatePayRangeDisplay"), item.get("PayBenefits")):
        low, high = parse_annual_salary(text)
        if low is not None:
            return low, high
    return None, None


def _to_job(item: dict[str, Any]) -> JobDraft | None:
    listing_id = item.get("ListingId")
    title = (item.get("Title") or "").strip()
    if listing_id is None or not title:
        return None

    agency = item.get("Agency") or {}
    application = item.get("JobApplicationDetails") or {}
    agency_name = agency.get("Name")
    company = item.get("Company") or agency_name or "Unknown employer"
    # A recruiter's contact details must not be recorded as the employer's.
    employer = agency if agency_name and agency_name == company else {}
    place = [item.get("Suburb"), item.get("Region")]
    low, high = _salary(item)

    return JobDraft(
        source="trademe",
        external_id=str(listing_id),
        title=title,
        company=company,
        location=item.get("JobLocation") or ", ".join(part for part in place if part),
        region=item.get("Region") or "",
        salary_min=low,
        salary_max=high,
        url=application.get("ApplyViaTradeMe") or application.get("Website"),
        description=(
            item.get("ExtendedBody") or item.get("Body") or item.get("ShortDescription") or ""
        ),
        posted_at=_parse_date(item.get("StartDate")),
        closes_at=_parse_date(item.get("EndDate")),
        company_website=employer.get("Website"),
        company_phone=application.get("PhoneNumber") or employer.get("PhoneNumber"),
        company_email=employer.get("EMail"),
        company_address=employer.get("Address"),
    )


def parse_jobs(payload: dict[str, Any]) -> list[JobDraft]:
    jobs = (_to_job(item) for item in payload.get("List") or [])
    return [job for job in jobs if job is not None]


class TradeMeSource:
    name = "trademe"

    def __init__(
        self,
        client: httpx.Client,
        consumer_key: str,
        consumer_secret: str,
        token: str | None = None,
        token_secret: str | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._client = client
        self._auth = build_auth_header(consumer_key, consumer_secret, token, token_secret)
        self._url = f"{base_url.rstrip('/')}{SEARCH_PATH}"

    def search(self, keywords: str) -> list[JobDraft]:
        params = {"search_string": keywords, "rows": DEFAULT_ROWS, "sort_order": "BestMatch"}
        try:
            response = self._client.get(
                self._url, params=params, headers={"Authorization": self._auth}
            )
        except httpx.HTTPError as error:
            raise ProviderError(self.name, f"request failed ({type(error).__name__})") from None

        if response.status_code != httpx.codes.OK:
            raise ProviderError(self.name, f"HTTP {response.status_code}")
        try:
            return parse_jobs(response.json())
        except ValueError:
            raise ProviderError(self.name, "response was not valid JSON") from None
