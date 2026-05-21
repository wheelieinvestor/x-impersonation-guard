"""Shared data models for impersonation checks."""

from pydantic import BaseModel, Field


class AccountProfile(BaseModel):
    """Minimal X account profile data used by the detector."""

    id: str
    username: str
    name: str
    description: str = ""
    verified: bool = False
    followers_count: int = Field(default=0, ge=0)
    following_count: int = Field(default=0, ge=0)
    created_at: str | None = None
    profile_image_url: str | None = None


class DetectionResult(BaseModel):
    """Score and recommendation for a candidate account."""

    candidate: AccountProfile
    score: int
    action: str
    reasons: list[str]
    mitigations: list[str] = Field(default_factory=list)
