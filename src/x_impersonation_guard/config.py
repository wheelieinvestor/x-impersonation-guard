"""Validated YAML configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

DEFAULT_HOME = Path("~/.x-impersonation-guard")


class IdentityType(StrEnum):
    INDIVIDUAL = "individual"
    BRAND = "brand"
    ORGANIZATION = "organization"


class XApiMode(StrEnum):
    API = "api"
    SCRAPE = "scrape"
    AUTO = "auto"


class ProtectedIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    handle: str
    display_name: str
    user_id: str | None = None
    type: IdentityType = IdentityType.INDIVIDUAL
    report_as: str
    reporter_name: str
    reporter_email: EmailStr
    extra_handle_variants: list[str] = Field(default_factory=list)
    extra_display_variants: list[str] = Field(default_factory=list)
    auto_report_threshold: int = Field(default=95, ge=70, le=100)

    @field_validator("handle")
    @classmethod
    def clean_handle(cls, value: str) -> str:
        handle = value.removeprefix("@").strip().lower()
        if not handle:
            raise ValueError("handle cannot be empty")
        if len(handle) > 15:
            raise ValueError("X handles cannot exceed 15 characters")
        return handle


class XApiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: XApiMode = XApiMode.AUTO
    bearer_token_env: str = "X_API_BEARER_TOKEN"
    max_cost_per_scan_usd: float = Field(default=2.0, gt=0, le=50)


class ScoringThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_queue_medium: int = Field(default=70, ge=0, le=100)
    review_queue_high: int = Field(default=90, ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.review_queue_high < self.review_queue_medium:
            raise ValueError("high threshold must be >= medium threshold")
        return self


class ScoringWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle_similarity: int = 20
    name_similarity: int = 15
    bio_similarity: int = 10
    image_similarity: int = 25
    account_age: int = 10
    follower_ratio: int = 5
    follow_back_pattern: int = 5
    posting_behavior: int = 5
    verified_status: int = 5

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        total = sum(self.model_dump().values())
        if total != 100:
            raise ValueError(f"scoring weights must sum to 100, got {total}")
        return self


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


class ReportingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_submit: bool = False
    max_reports_per_24h: int = Field(default=5, ge=1, le=20)
    delay_between_reports_seconds: tuple[int, int] = (90, 300)
    headless: bool = False

    @model_validator(mode="after")
    def validate_delay(self) -> Self:
        low, high = self.delay_between_reports_seconds
        if low < 0 or high < low:
            raise ValueError("delay_between_reports_seconds must be [low, high]")
        if self.auto_submit and self.max_reports_per_24h > 5:
            raise ValueError(
                "auto_submit with more than 5 reports per day is not allowed"
            )
        return self


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: Path = DEFAULT_HOME / "db.sqlite"
    evidence_dir: Path = DEFAULT_HOME / "evidence"
    reports_dir: Path = DEFAULT_HOME / "reports"

    @field_validator("db_path", "evidence_dir", "reports_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"
    format: str = "json"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_identities: list[ProtectedIdentity] = Field(min_length=1)
    x_api: XApiConfig = Field(default_factory=XApiConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def identity_for_handle(self, handle: str | None) -> ProtectedIdentity:
        if handle is None:
            return self.protected_identities[0]
        clean = handle.removeprefix("@").lower()
        for identity in self.protected_identities:
            if identity.handle == clean:
                return identity
        raise ValueError(f"unknown protected identity: {handle}")


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.expanduser().read_text())
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return AppConfig.model_validate(raw)


def write_default_config(path: Path) -> None:
    path = path.expanduser()
    if path.exists():
        raise FileExistsError(f"config already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(default_config_dict(), sort_keys=False))


def default_config_dict() -> dict[str, Any]:
    return {
        "protected_identities": [
            {
                "name": "Dean Ahrens",
                "handle": "wheelieinvestor",
                "display_name": "Wheelie Investor",
                "user_id": None,
                "type": "individual",
                "report_as": "Me or someone I am authorized to represent",
                "reporter_name": "Dean Ahrens",
                "reporter_email": "dean@wheelhousecapital.com",
                "extra_handle_variants": [
                    "wheelie_*",
                    "*_wheelie",
                    "wheelchairinvestor*",
                ],
                "extra_display_variants": ["Dean Ahrens", "Wheelie Capital"],
                "auto_report_threshold": 95,
            }
        ],
        "x_api": {
            "mode": "auto",
            "bearer_token_env": "X_API_BEARER_TOKEN",
            "max_cost_per_scan_usd": 2.0,
        },
        "scoring": {
            "thresholds": {"review_queue_medium": 70, "review_queue_high": 90},
            "weights": ScoringWeights().model_dump(),
        },
        "reporting": {
            "auto_submit": False,
            "max_reports_per_24h": 5,
            "delay_between_reports_seconds": [90, 300],
            "headless": False,
        },
        "storage": {
            "db_path": "~/.x-impersonation-guard/db.sqlite",
            "evidence_dir": "~/.x-impersonation-guard/evidence",
            "reports_dir": "~/.x-impersonation-guard/reports",
        },
        "logging": {"level": "INFO", "format": "json"},
    }
