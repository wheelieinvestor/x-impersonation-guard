"""Report rate limiting."""

from __future__ import annotations

from dataclasses import dataclass

from x_impersonation_guard.config import ReportingConfig
from x_impersonation_guard.storage.repository import ReviewStore


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    message: str


def check_report_limit(
    store: ReviewStore,
    identity_handle: str,
    config: ReportingConfig,
) -> RateLimitDecision:
    used = store.reports_in_window(identity_handle, hours=24)
    remaining = max(0, config.max_reports_per_24h - used)
    if remaining <= 0:
        return RateLimitDecision(
            False,
            0,
            "report cap reached for rolling 24-hour window",
        )
    return RateLimitDecision(True, remaining, f"{remaining} reports remaining")
