"""Domain models shared across pipelines."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class CandidateSource(StrEnum):
    HANDLE_VARIANT = "handle_variant"
    DISPLAY_NAME_SEARCH = "display_name_search"
    FOLLOWER_SCAN = "follower_scan"
    IMAGE_LOOKUP = "image_lookup"
    SCRAPE = "scrape"
    FIXTURE = "fixture"


class QueueStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    REPORTED = "reported"
    REPORT_FAILED = "report_failed"
    FAILED = "failed"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccountProfile(BaseModel):
    id: str
    username: str
    name: str
    description: str = ""
    verified: bool = False
    verified_affiliation: str | None = None
    followers_count: int = Field(default=0, ge=0)
    following_count: int = Field(default=0, ge=0)
    tweet_count: int = Field(default=0, ge=0)
    protected_followers_followed: int = Field(default=0, ge=0)
    mutual_followers: int = Field(default=0, ge=0)
    recent_posts_containing_protected_handle: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    profile_image_url: HttpUrl | None = None
    profile_image_phash: str | None = None

    @property
    def handle_url(self) -> str:
        return f"https://x.com/{self.username}"


class SignalBreakdown(BaseModel):
    handle_similarity: float
    name_similarity: float
    bio_similarity: float
    image_similarity: float
    account_age: float
    follower_ratio: float
    follow_back_pattern: float
    posting_behavior: float
    verified_status: float


class ScoreResult(BaseModel):
    candidate: AccountProfile
    score: int
    priority: Priority | None
    signals: SignalBreakdown
    weighted_scores: dict[str, float]
    reasons: list[str]
    mitigations: list[str]
    should_store: bool
    queue: str | None
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DetectionCandidate(BaseModel):
    identity_handle: str
    source: CandidateSource
    profile: AccountProfile
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)


class ReportMetadata(BaseModel):
    candidate_id: int
    identity_handle: str
    candidate_handle: str
    filed_at: datetime
    reporter_name: str
    reporter_email: str
    reasons: list[str]
    score_breakdown: dict[str, Any]
