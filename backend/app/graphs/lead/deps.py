from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import psycopg
from langchain_core.runnables import RunnableConfig

from app.chains.score_chain import ScoreChain
from app.providers.jobs.base import JobSource


@dataclass
class LeadDeps:
    conn: psycopg.Connection
    sources: Sequence[JobSource]
    score_chain: ScoreChain
    now: datetime


def get_deps(config: RunnableConfig) -> LeadDeps:
    return config["configurable"]["deps"]
