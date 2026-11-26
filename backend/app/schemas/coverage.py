from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Status = Literal["shown", "added", "missing", "declined"]


class SkillCoverage(BaseModel):
    name: str
    status: Status
    evidence: str
    matched_as: str | None = None


class Coverage(BaseModel):
    required: list[SkillCoverage]
    preferred: list[SkillCoverage]
    split: bool
    required_text: str
    preferred_text: str


SkillName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class SkillDecisionRequest(BaseModel):
    skill: SkillName
    decision: Literal["have", "no"] | None


class SkillDecisionResponse(BaseModel):
    ok: bool
