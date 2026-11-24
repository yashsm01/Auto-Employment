from typing import Literal

from pydantic import BaseModel, Field

WorkRights = Literal["citizen", "resident", "open_visa", "needs_sponsorship"]


class SkillEntry(BaseModel):
    name: str
    years: float | None = None
    level: str | None = None


class ResumeProfile(BaseModel):
    """What was read from the base resume. It drives searching and scoring."""

    titles: list[str] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    seniority: str | None = None
    search_queries: list[str] = Field(default_factory=list)

    def all_skill_names(self) -> list[str]:
        return [skill.name for skill in self.skills] + self.tools


class SearchPreferences(BaseModel):
    regions: list[str] = Field(default_factory=list)
    work_rights: WorkRights | None = None
    salary_min: int | None = None
    avoid_keywords: list[str] = Field(default_factory=list)
    shortlist_threshold: int = Field(default=70, ge=0, le=100)


class BoardEntry(BaseModel):
    """A company's public careers board."""

    platform: Literal["greenhouse", "lever", "ashby"]
    token: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    company: str = Field(min_length=1, max_length=120)


class ProfileUpdate(BaseModel):
    titles: list[str]
    skills: list[SkillEntry]
    tools: list[str]
    search_queries: list[str] = Field(max_length=20)
    regions: list[str]
    work_rights: WorkRights | None
    salary_min: int | None = Field(ge=0)
    avoid_keywords: list[str]
    shortlist_threshold: int = Field(ge=0, le=100)
    boards: list[BoardEntry] = Field(max_length=50)


class ProfileView(ProfileUpdate):
    is_example: bool
    filename: str | None
    industries: list[str]
    seniority: str | None
    connections: dict[str, bool]
    warning: str | None = None
