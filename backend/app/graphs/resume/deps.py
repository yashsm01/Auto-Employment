from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg
from langchain_core.runnables import RunnableConfig

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.chains.tailor_chain import FactCheckChain, TailorChain


@dataclass
class ResumeDeps:
    conn: psycopg.Connection
    sections_chain: ResumeSectionsChain | None
    tailor_chain: TailorChain | None
    check_chain: FactCheckChain | None
    upload_dir: Path
    now: datetime


def get_deps(config: RunnableConfig) -> ResumeDeps:
    return config["configurable"]["deps"]
