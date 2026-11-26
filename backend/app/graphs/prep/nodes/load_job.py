from datetime import timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.repositories import prep_repo
from app.schemas.prep import Fact, PageSource
from app.services import resume_build_service

REUSE_DAYS = 30
EMPLOYER_KINDS = ("about", "news")


def _reuse(
    stored_facts: list[dict[str, Any]], stored_sources: list[dict[str, Any]]
) -> tuple[list[Fact], list[PageSource]]:
    """Employer facts from an earlier pack, with sources renumbered r1, r2, ..."""
    ids: dict[str, str] = {}
    sources: list[PageSource] = []
    for source in stored_sources:
        new_id = f"r{len(sources) + 1}"
        ids[source["id"]] = new_id
        sources.append(
            PageSource(
                id=new_id,
                url=source.get("url"),
                title=source.get("title") or "Earlier source",
                kind=source.get("kind") or "website",
                text="",
            )
        )
    facts = [
        Fact(**{**fact, "source_id": ids[fact["source_id"]]})
        for fact in stored_facts
        if fact.get("kind") in EMPLOYER_KINDS and fact.get("source_id") in ids
    ]
    used = {fact.source_id for fact in facts}
    return facts, [source for source in sources if source.id in used]


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    conn = deps.conn
    context = resume_build_service.load_context(conn, state["application_id"])
    pack = prep_repo.get(conn, state["pack_id"])
    extras = prep_repo.job_extras(conn, state["application_id"])
    cached = context["cached_sections"]

    facts: list[Fact] = []
    reused_sources: list[PageSource] = []
    if context["company_id"]:
        since = deps.now - timedelta(days=REUSE_DAYS)
        found = prep_repo.recent_employer_facts(conn, context["company_id"], since)
        if found:
            facts, reused_sources = _reuse(*found)

    regions = extras["regions"] or []
    return {
        "profile_id": context["profile_id"],
        "company_id": context["company_id"],
        "job": context["job"],
        "job_url": extras["url"],
        "employer": context["job"].company,
        "website": extras["website"],
        "address": extras["address"],
        "origin": regions[0] if regions else None,
        "extra": pack["extra"] if pack else None,
        "raw_text": context["raw_text"],
        "contact": context["ai_contact"],
        "sections": resume_build_service.usable_sections(cached),
        "reused": bool(facts),
        "facts": facts,
        "dropped": [],
        "reused_sources": reused_sources,
        "pages": [],
        "extracted": [],
        "notes": [],
        "places_calls": 0,
        "explore_history": [],
    }
