from dataclasses import dataclass, field
from datetime import datetime

import psycopg
from langchain_core.runnables import RunnableConfig

from app.chains.manager import PrepChains
from app.services.enrich_service import PageReader, PlaceFinder, WebSearch
from app.services.prep_service import Budget


@dataclass
class PrepDeps:
    conn: psycopg.Connection
    chains: PrepChains
    places: PlaceFinder | None
    reader: PageReader | None
    search: WebSearch | None
    now: datetime
    usd_to_nzd: float
    places_allowed: bool
    budget: Budget = field(default_factory=Budget)
    places_remaining: int | None = None  # this month's free lookups left; None means no cap


def get_deps(config: RunnableConfig) -> PrepDeps:
    return config["configurable"]["deps"]
