"""Looks for real open jobs on the websites of employers found on Google Maps."""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlsplit
from uuid import UUID

import httpx

from app.core.errors import ProviderError
from app.core.normalize import contains_term
from app.core.nz_places import fold_place
from app.providers.company.careers import find_board, find_careers_link, site_host
from app.providers.jobs.ats import BoardSource
from app.schemas.job import AlertJob, JobDraft
from app.schemas.resume import BoardEntry

logger = logging.getLogger(__name__)

ExtractJobs = Callable[[str, str, str], list[AlertJob]]


@dataclass(frozen=True)
class SiteEmployer:
    company_id: UUID
    name: str
    website: str
    address: str | None


class PageReader(Protocol):
    def read(self, url: str) -> str: ...


def _job_link(careers_url: str, url: str | None) -> str:
    link = urljoin(careers_url, url or "")
    return link if urlsplit(link).scheme in ("http", "https") else careers_url


def _location(alert: AlertJob, employer: SiteEmployer) -> str:
    place = alert.location.strip()
    if not place:
        address = employer.address or ""
        if address and "new zealand" not in fold_place(address):
            address = f"{address}, New Zealand"  # Google omits the country on NZ addresses
        return address or "New Zealand"
    if "new zealand" in fold_place(place) or contains_term(place, "NZ"):
        return place
    return f"{place}, New Zealand"


class EmployerSitesSource:
    name = "employer_sites"
    label = "Employer websites via Google Maps"

    def __init__(
        self,
        client: httpx.Client,
        reader: PageReader,
        extract: ExtractJobs | None,
        employers: list[SiteEmployer],
    ) -> None:
        self._client = client
        self._reader = reader
        self._extract = extract
        self._employers = employers
        self._done = False
        self.checked: list[UUID] = []

    def _board_jobs(self, employer: SiteEmployer, board: tuple[str, str]) -> list[JobDraft]:
        entry = BoardEntry(platform=board[0], token=board[1], company=employer.name[:120])
        return BoardSource(self._client, entry).search("")

    def _to_job(
        self, employer: SiteEmployer, careers_url: str, page: str, alert: AlertJob
    ) -> JobDraft | None:
        title = alert.title.strip()
        if not title or not contains_term(page, title):  # never store a job the page doesn't show
            return None
        location = _location(alert, employer)
        key = hashlib.sha256(f"{title}|{location}".casefold().encode("utf-8")).hexdigest()[:16]
        return JobDraft(
            source="ats",
            external_id=f"site:{site_host(employer.website)}:{key}",
            title=title,
            company=employer.name,
            location=location,
            url=_job_link(careers_url, alert.url),
            description=alert.summary.strip(),
            company_website=employer.website,
        )

    def _scan(self, employer: SiteEmployer) -> list[JobDraft]:
        home = self._reader.read(employer.website)
        board = find_board(home)
        if board:
            return self._board_jobs(employer, board)
        if self._extract is None:
            return []
        careers_url = find_careers_link(home, employer.website)
        if careers_url is None:
            return []
        page = self._reader.read(careers_url)
        board = find_board(page)
        if board:
            return self._board_jobs(employer, board)
        alerts = self._extract(employer.name, careers_url, page)
        return [job for a in alerts if (job := self._to_job(employer, careers_url, page, a))]

    def search(self, keywords: str) -> list[JobDraft]:
        if self._done:
            return []
        self._done = True

        jobs: list[JobDraft] = []
        failure: ProviderError | None = None
        succeeded = 0
        for employer in self._employers:
            self.checked.append(employer.company_id)
            try:
                jobs.extend(self._scan(employer))
            except ProviderError as error:
                logger.info("Could not read %s: %s", employer.name, error)
                failure = error
            else:
                succeeded += 1
        if self._employers and not succeeded and failure:
            raise failure
        return jobs
