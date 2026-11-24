from typing import Literal

from pydantic import BaseModel


class Decision(BaseModel):
    """One past approve or skip, used to tune later scores."""

    action: Literal["approve", "skip"]
    title: str
    company: str
