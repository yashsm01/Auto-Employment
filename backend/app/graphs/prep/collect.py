"""Shared steps for gather and explore: add pages within the budget, and take notes from them."""

from app.core.errors import ProviderError
from app.graphs.prep.deps import PrepDeps
from app.providers.company.places import PlaceMatch
from app.providers.company.website_reader import is_allowed_url
from app.schemas.prep import Fact, PageKind, PageSource
from app.services.prep_service import BLOCKED_LINK_NOTE, call_model, verify_facts


def new_page(pages: list[PageSource], *, url: str | None, title: str, kind: PageKind,
             text: str) -> PageSource:
    page = PageSource(id=f"s{len(pages) + 1}", url=url, title=title, kind=kind, text=text)
    pages.append(page)
    return page


def seen_url(pages: list[PageSource], url: str) -> bool:
    return any(page.url == url and page.kind != "job_post" for page in pages)


def read_page(deps: PrepDeps, pages: list[PageSource], notes: list[str], url: str,
              title: str, kind: PageKind) -> PageSource | None:
    """Read one allowed URL through the reader, counting it against the page limit."""
    if not is_allowed_url(url):
        notes.append(BLOCKED_LINK_NOTE if kind == "user" else f"Skipped a blocked site: {url}")
        return None
    if deps.reader is None or seen_url(pages, url) or not deps.budget.allow("page"):
        return None
    try:
        text = deps.reader.read(url)
    except ProviderError as error:
        notes.append(f"Could not read {url}: {error}")
        return None
    return new_page(pages, url=url, title=title, kind=kind, text=text)


def search_pages(deps: PrepDeps, pages: list[PageSource], notes: list[str], query: str,
                 limit: int | None = None) -> list[PageSource]:
    """Search once and keep allowed, new results as pages from their own content."""
    if deps.search is None or not deps.budget.allow("query"):
        return []
    try:
        hits = deps.search.search(query)
    except ProviderError as error:
        notes.append(f"Search failed: {error}")
        return []
    added: list[PageSource] = []
    for hit in hits:
        if limit is not None and len(added) >= limit:
            break
        if not is_allowed_url(hit.url) or seen_url(pages, hit.url):
            continue
        if not deps.budget.allow("page"):
            break
        added.append(new_page(pages, url=hit.url, title=hit.title or hit.url, kind="search",
                              text=hit.content))
    return added


def place_text(match: PlaceMatch) -> str:
    lines = [match.name or "Business on Google Maps"]
    for label, value in (("Address", match.address), ("Phone", match.phone),
                         ("Website", match.website)):
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def place_page(deps: PrepDeps, pages: list[PageSource], name: str, town: str,
               counter: dict[str, int]) -> PageSource | None:
    if deps.places is None or not deps.places_allowed:
        return None
    counter["places_calls"] += 1
    try:
        match = deps.places.find(name, town)
    except ProviderError:
        return None
    if match is None:
        return None
    url = f"https://www.google.com/maps/place/?q=place_id:{match.place_id}"
    return new_page(pages, url=url, title=f"{name} on Google Maps", kind="places",
                    text=place_text(match))


def extract_new(deps: PrepDeps, pages: list[PageSource], extracted: list[str], facts: list[Fact],
                dropped: list[Fact], notes: list[str], employer: str) -> None:
    """Take notes from pages not seen yet, keeping only facts whose quote is on the page."""
    chain = deps.chains.extract
    by_id = {page.id: page for page in pages}
    for page in pages:
        if page.id in extracted:
            continue
        if not page.text.strip():
            extracted.append(page.id)  # nothing to read, so no model call
            continue
        try:
            result = call_model(deps.budget, chain.llm, chain.model,
                                lambda page=page: chain.run(page, employer))
        except ProviderError as error:
            notes.append(f"Could not take notes from {page.title}: {error}")
            extracted.append(page.id)
            continue
        if result is None:
            return
        extracted.append(page.id)
        kept, failed = verify_facts(result.facts, by_id)
        facts.extend(kept)
        dropped.extend(failed)
