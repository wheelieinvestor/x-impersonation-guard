from __future__ import annotations

import pytest

from x_impersonation_guard.clients.mode_selector import select_scan_mode
from x_impersonation_guard.config import AppConfig, XApiMode, default_config_dict


def _cfg(mode: str = "auto") -> AppConfig:
    raw = default_config_dict()
    raw["x_api"]["mode"] = mode
    return AppConfig.model_validate(raw)


def test_mode_selector_auto_uses_api_when_token_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X_API_BEARER_TOKEN", "token")
    decision = select_scan_mode(_cfg())
    assert decision.mode == XApiMode.API
    assert decision.bearer_token == "token"


def test_mode_selector_auto_falls_back_to_scrape_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)
    decision = select_scan_mode(_cfg())
    assert decision.mode == XApiMode.SCRAPE
    assert "no bearer token" in decision.reason


def test_mode_selector_forced_api_requires_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)
    with pytest.raises(ValueError):
        select_scan_mode(_cfg("api"))


def test_mode_selector_forced_scrape_ignores_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X_API_BEARER_TOKEN", "token")
    decision = select_scan_mode(_cfg("scrape"))
    assert decision.mode == XApiMode.SCRAPE
    assert decision.bearer_token is None
