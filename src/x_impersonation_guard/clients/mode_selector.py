"""Select scan backend from config and environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from x_impersonation_guard.config import AppConfig, XApiMode


@dataclass(frozen=True)
class ScanModeDecision:
    mode: XApiMode
    reason: str
    bearer_token: str | None = None


def select_scan_mode(config: AppConfig) -> ScanModeDecision:
    token = os.getenv(config.x_api.bearer_token_env)
    configured = config.x_api.mode
    if configured == XApiMode.API:
        if not token:
            raise ValueError(
                f"{config.x_api.bearer_token_env} is required when x_api.mode is api"
            )
        return ScanModeDecision(XApiMode.API, "forced api mode", token)
    if configured == XApiMode.SCRAPE:
        return ScanModeDecision(XApiMode.SCRAPE, "forced scrape mode")
    if token:
        return ScanModeDecision(XApiMode.API, "bearer token detected", token)
    return ScanModeDecision(XApiMode.SCRAPE, "no bearer token detected")
