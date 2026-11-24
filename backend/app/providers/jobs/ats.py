"""Public careers boards on Greenhouse, Lever and Ashby. None of them needs a key."""

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import ProviderError
from app.core.normalize import contains_term, parse_annual_salary, parse_timestamp, strip_html
from app.schemas.job import JobDraft
from app.schemas.resume import BoardEntry


def _draft(board: BoardEntry, job_id: Any, title: str, **fields: Any) -> JobDraft:
    return JobDraft(
        source="ats",
        external_id=f"{board.platform}:{board.token}:{job_id}",
        title=title.strip(),
        company=board.company,
        **fields,
    )


def parse_greenhouse(payload: dict[str, Any], board: BoardEntry) -> list[JobDraft]:
    jobs = []
    for item in payload["jobs"]:
        if item.get("id") is None or not item.get("title"):
            continue
        jobs.append(
            _draft(
                board,
                item["id"],
                item["title"],
                location=(item.get("location") or {}).get("name") or "",
                url=item.get("absolute_url"),
                description=strip_html(item.get("content")),
                posted_at=parse_timestamp(item.get("first_published") or item.get("updated_at")),
            )
        )
    return jobs


def _lever_salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    salary = item.get("salaryRange") or {}
    if salary.get("currency") != "NZD" or "year" not in (salary.get("interval") or ""):
        return None, None
    return salary.get("min"), salary.get("max")


def _lever_description(item: dict[str, Any]) -> str:
    parts = [item.get("descriptionPlain") or ""]
    for section in item.get("lists") or []:
        parts.append(section.get("text") or "")
        parts.append(strip_html(section.get("content")))
    parts.append(item.get("additionalPlain") or "")
    return "\n".join(part.strip() for part in parts if part and part.strip())


def parse_lever(payload: list[dict[str, Any]], board: BoardEntry) -> list[JobDraft]:
    if not isinstance(payload, list):
        raise TypeError("Lever returned an unexpected format")
    jobs = []
    for item in payload:
        if not item.get("id") or not item.get("text"):
            continue
        low, high = _lever_salary(item)
        jobs.append(
            _draft(
                board,
                item["id"],
                item["text"],
                location=(item.get("categories") or {}).get("location") or "",
                url=item.get("hostedUrl"),
                description=_lever_description(item),
                salary_min=low,
                salary_max=high,
                posted_at=parse_timestamp(item.get("createdAt")),
            )
        )
    return jobs


def _ashby_salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    summary = (item.get("compensation") or {}).get("scrapeableCompensationSalarySummary") or ""
    if "NZ$" not in summary and "NZD" not in summary:
        return None, None
    return parse_annual_salary(summary)


def parse_ashby(payload: dict[str, Any], board: BoardEntry) -> list[JobDraft]:
    jobs = []
    for item in payload["jobs"]:
        if not item.get("id") or not item.get("title") or item.get("isListed") is False:
            continue
        location = item.get("location") or ""
        if item.get("isRemote") and not contains_term(location, "remote"):
            location = f"Remote, {location}" if location else "Remote"
        low, high = _ashby_salary(item)
        jobs.append(
            _draft(
                board,
                item["id"],
                item["title"],
                location=location,
                url=item.get("jobUrl"),
                description=item.get("descriptionPlain") or strip_html(item.get("descriptionHtml")),
                salary_min=low,
                salary_max=high,
                posted_at=parse_timestamp(item.get("publishedAt")),
            )
        )
    return jobs


_PLATFORMS: dict[str, tuple[str, dict[str, str], Callable[..., list[JobDraft]]]] = {
    "greenhouse": (
        "https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        {"content": "true"},
        parse_greenhouse,
    ),
    "lever": ("https://api.lever.co/v0/postings/{token}", {"mode": "json"}, parse_lever),
    "ashby": (
        "https://api.ashbyhq.com/posting-api/job-board/{token}",
        {"includeCompensation": "true"},
        parse_ashby,
    ),
}


class BoardSource:
    """One company's board. It lists all jobs, so it is fetched once per search run."""

    def __init__(self, client: httpx.Client, board: BoardEntry) -> None:
        self._client = client
        self._board = board
        self._fetched = False
        self.name = f"ats:{board.platform}:{board.token}"
        self.label = f"{board.company} careers board"

    def search(self, keywords: str) -> list[JobDraft]:
        if self._fetched:
            return []
        self._fetched = True

        template, params, parser = _PLATFORMS[self._board.platform]
        url = template.format(token=quote(self._board.token, safe=""))
        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as error:
            raise ProviderError(self.name, f"request failed ({type(error).__name__})") from None
        if response.status_code != httpx.codes.OK:
            raise ProviderError(self.name, f"HTTP {response.status_code}")
        try:
            return parser(response.json(), self._board)
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ProviderError(self.name, "unexpected response format") from None
