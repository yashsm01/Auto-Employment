"""Deep search rules: spending limits, quote checks and pack checks."""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.urls import safe_url
from app.providers.company.website_reader import is_allowed_url
from app.providers.llm.base import LLMProvider
from app.repositories import prep_repo
from app.schemas.prep import (
    DeepSearchSettings,
    DeepSearchView,
    Fact,
    PageSource,
    PrepPack,
    PrepView,
    SourcedLine,
    SourceLink,
    WriteDraft,
)

REQUIRED_KINDS = ("about", "news", "pay", "practical", "interview")
MAX_QUOTE_WORDS = 25
PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}
_FALLBACK_PRICE = PRICES_USD_PER_MTOK["claude-sonnet-5-5"]
_PLAIN = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-"})
_NUMBER = re.compile(r"\d[\d,.]*")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARKS = re.compile(r"[*_`#>]+")
_LINK = re.compile(r"https?://\S+")
# Facts about named people are never kept. These roles almost always come with a person's name.
_PERSON_ROLES = re.compile(
    r"\b(ceo|cto|cfo|coo|chief executive|chief technology officer|founder|co-founder|"
    r"managing director|chair|chairman|chairwoman|chairperson|president|recruiter|"
    r"hiring manager|talent partner)\b",
    re.IGNORECASE,
)
# Writing the pack must always be possible, so other calls stop earlier.
WRITE_RESERVE_CALLS = 2
WRITE_RESERVE_USD = 0.05
BLOCKED_LINK_NOTE = (
    "That link is on a site the app may not open. Paste the job text into Extra details instead."
)

BudgetKind = Literal["query", "page", "explore", "model", "write"]


@dataclass
class Budget:
    """Hard limits for one run. Every call checks here first."""

    max_queries: int = 4
    max_pages: int = 6
    max_explore: int = 3
    max_model_calls: int = 14
    max_cost_usd: float = 0.12
    queries: int = 0
    pages: int = 0
    explore: int = 0
    model_calls: int = 0
    cost_usd: float = 0.0
    stopped_by: str | None = None

    def _state(self, kind: BudgetKind) -> tuple[int, int, str]:
        if kind == "query":
            message = f"Stopped searching after {self.max_queries} searches."
            return self.queries, self.max_queries, message
        if kind == "page":
            return self.pages, self.max_pages, f"Stopped reading after {self.max_pages} pages."
        if kind == "explore":
            return (
                self.explore,
                self.max_explore,
                f"Stopped exploring after {self.max_explore} extra steps.",
            )
        limit = self.max_model_calls
        if kind == "model":
            limit -= WRITE_RESERVE_CALLS
        return self.model_calls, limit, "Stopped at the spending limit for one run."

    def can(self, kind: BudgetKind) -> bool:
        used, limit, _ = self._state(kind)
        if kind == "model" and self.cost_usd >= self.max_cost_usd - WRITE_RESERVE_USD - 1e-9:
            return False
        if kind == "write" and self.cost_usd >= self.max_cost_usd - 1e-9:
            return False
        return used < limit

    def allow(self, kind: BudgetKind) -> bool:
        if not self.can(kind):
            self.stopped_by = self.stopped_by or self._state(kind)[2]
            return False
        setattr(self, _COUNTERS[kind], getattr(self, _COUNTERS[kind]) + 1)
        return True

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        price_in, price_out = PRICES_USD_PER_MTOK.get(model, _FALLBACK_PRICE)
        self.cost_usd += (input_tokens * price_in + output_tokens * price_out) / 1_000_000


_COUNTERS = {
    "query": "queries",
    "page": "pages",
    "explore": "explore",
    "model": "model_calls",
    "write": "model_calls",
}


def call_model[T](
    budget: Budget,
    llm: LLMProvider,
    model: str,
    call: Callable[[], T],
    kind: Literal["model", "write"] = "model",
) -> T | None:
    """Run one model call if the budget allows it, and record what it cost."""
    if not budget.allow(kind):
        return None
    before_in, before_out = llm.input_tokens, llm.output_tokens
    try:
        return call()
    finally:
        budget.record(model, llm.input_tokens - before_in, llm.output_tokens - before_out)


def normalise(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text).translate(_PLAIN)
    # Pages come from Jina as markdown: keep link text, drop emphasis and heading marks.
    plain = _MD_MARKS.sub(" ", _MD_LINK.sub(r"\1", plain))
    return " ".join(plain.split()).casefold()


def is_link(text: str) -> bool:
    return bool(_LINK.fullmatch(text.strip()))


def names_a_person(fact: Fact) -> bool:
    return bool(_PERSON_ROLES.search(fact.text) or _PERSON_ROLES.search(fact.quote))


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text)}


def verify_facts(
    facts: list[Fact], pages: dict[str, PageSource]
) -> tuple[list[Fact], list[Fact]]:
    """Keep facts whose short quote really appears in the page they cite, and whose wording
    adds no number the quote lacks. Facts about named people are discarded entirely."""
    kept: list[Fact] = []
    dropped: list[Fact] = []
    for fact in facts:
        if names_a_person(fact):
            continue
        page = pages.get(fact.source_id)
        quote = normalise(fact.quote)
        ok = (
            page is not None
            and quote
            and len(quote.split()) <= MAX_QUOTE_WORDS
            and quote in normalise(page.text)
            and _numbers(fact.text) <= _numbers(fact.quote)
        )
        (kept if ok else dropped).append(fact)
    return kept, dropped


def missing_kinds(facts: list[Fact], needs: list[str]) -> list[str]:
    found = {fact.kind for fact in facts}
    return [kind for kind in needs if kind not in found]


def _lines(facts: list[Fact], kinds: tuple[str, ...]) -> list[SourcedLine]:
    seen: set[str] = set()
    lines = []
    for fact in facts:
        key = normalise(fact.text)
        if fact.kind in kinds and key not in seen:
            seen.add(key)
            lines.append(SourcedLine(text=fact.text, source_ids=[fact.source_id], quote=fact.quote))
    return lines


def assemble_pack(
    draft: WriteDraft,
    facts: list[Fact],
    dropped: list[Fact],
    resume_text: str,
    directions_url: str | None,
) -> PrepPack:
    """Employer, pay and practical lines come only from verified facts, never from the writer.
    Resume lines the writer quotes are checked against the resume."""
    resume = normalise(resume_text)
    evidence = []
    for item in draft.evidence:
        if item.evidence and normalise(item.evidence) not in resume:
            item = item.model_copy(update={"status": "check"})
        evidence.append(item)
    pay = _lines(facts, ("pay",))
    unverified = list(dict.fromkeys(fact.text for fact in dropped))
    return PrepPack(
        evidence=evidence,
        interview_stages=draft.interview_stages,
        pay=pay[0] if pay else None,
        employer=_lines(facts, ("about", "news")),
        questions=draft.questions,
        brush_up=draft.brush_up,
        practical=_lines(facts, ("practical",)),
        tips=draft.tips,
        unknowns=draft.unknowns,
        could_not_verify=unverified,
        directions_url=directions_url,
    )


def directions_link(origin: str | None, address: str | None) -> str | None:
    if not address:
        return None
    params = {"api": "1"}
    if origin:
        params["origin"] = origin
    params["destination"] = address
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


def cost_nzd(cost_usd: float, rate: float) -> float:
    return round(cost_usd * rate, 2)


NO_KEY_MESSAGE = "Deep search needs a Claude key in backend/.env."


def available(settings: Settings) -> bool:
    return bool(settings.anthropic_api_key.get_secret_value())


def get_settings(conn: psycopg.Connection, profile_id: UUID | str) -> DeepSearchSettings:
    row = conn.execute(
        "select ai -> 'deep_search' as value from settings where profile_id = %s", (profile_id,)
    ).fetchone()
    return DeepSearchSettings(**row["value"]) if row and row["value"] else DeepSearchSettings()


def save_settings(
    conn: psycopg.Connection, profile_id: UUID | str, value: DeepSearchSettings
) -> None:
    conn.execute(
        """
        insert into settings (profile_id, ai) values (%s, %s)
        on conflict (profile_id) do update set
            ai = settings.ai || excluded.ai,
            updated_at = now()
        """,
        (profile_id, Jsonb({"deep_search": value.model_dump()})),
    )


def used_this_month(conn: psycopg.Connection, profile_id: UUID | str, now: datetime) -> int:
    return prep_repo.count_since(conn, profile_id, prep_repo.month_start_nz(now))


def settings_view(
    conn: psycopg.Connection, profile_id: UUID | str, settings: Settings, now: datetime
) -> DeepSearchView:
    value = get_settings(conn, profile_id)
    return DeepSearchView(
        **value.model_dump(),
        used_this_month=used_this_month(conn, profile_id, now),
        available=available(settings),
    )


def request_run(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    extra: str | None,
    settings: Settings,
    now: datetime,
) -> None:
    """Queue one deep search for a job. Asking again while one is waiting does nothing."""
    row = prep_repo.application_company(conn, profile_id, application_id)
    if row is None:
        raise NotFound("Application not found")
    if prep_repo.open_for_application(conn, application_id):
        return
    if extra and is_link(extra) and not is_allowed_url(extra.strip()):
        raise BadRequest(BLOCKED_LINK_NOTE)
    if not available(settings):
        raise BadRequest(NO_KEY_MESSAGE)
    # Hold the profile row so two quick requests can't both take the last run of the month.
    conn.execute("select id from profiles where id = %s for update", (profile_id,))
    limit = get_settings(conn, profile_id).monthly_limit
    if used_this_month(conn, profile_id, now) >= limit:
        raise Conflict(
            f"You have used all {limit} deep searches this month. "
            "Change the limit on My resume profile."
        )
    prep_repo.insert_queued(conn, profile_id, application_id, row["company_id"], extra)


def on_approved(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    settings: Settings,
    now: datetime,
) -> bool:
    """With the switch on, approving a job queues a deep search. A full month skips it."""
    if not get_settings(conn, profile_id).enabled or not available(settings):
        return False
    try:
        request_run(conn, profile_id, application_id, None, settings, now)
    except Conflict:
        return False
    return True


def view(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    application_id: UUID | str,
    settings: Settings,
    now: datetime,
) -> PrepView:
    if prep_repo.application_company(conn, profile_id, application_id) is None:
        raise NotFound("Application not found")
    row = prep_repo.latest_for_application(conn, profile_id, application_id)
    common = {
        "application_id": application_id,
        "available": available(settings),
        "used_this_month": used_this_month(conn, profile_id, now),
        "monthly_limit": get_settings(conn, profile_id).monthly_limit,
    }
    if row is None:
        return PrepView(status="none", **common)
    done = row["status"] == "done"
    return PrepView(
        status=row["status"],
        pack=PrepPack(**row["content"]) if done else None,
        sources=[
            SourceLink(id=s["id"], title=s.get("title") or s["id"], url=safe_url(s.get("url")),
                       kind=s.get("kind") or "website")
            for s in row["sources"]
        ],
        notes=row["notes"],
        cost_nzd=cost_nzd(float(row["cost_usd"]), settings.usd_to_nzd) if done else None,
        finished_at=row["finished_at"],
        error=row["error"] if row["status"] == "failed" else None,
        **common,
    )
