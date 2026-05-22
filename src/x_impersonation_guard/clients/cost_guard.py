"""Estimated API cost guard for live scans."""

from __future__ import annotations

from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import AccountProfile


class ApiCostBudgetExceeded(RuntimeError):
    def __init__(self, calls_made: int, max_calls: int, estimated_cost_usd: float):
        self.calls_made = calls_made
        self.max_calls = max_calls
        self.estimated_cost_usd = estimated_cost_usd
        super().__init__(
            "estimated X API scan cost limit reached: "
            f"{calls_made}/{max_calls} calls used, "
            f"estimated=${estimated_cost_usd:.2f}"
        )


class CostGuardedLookup(XProfileLookup):
    def __init__(
        self,
        wrapped: XProfileLookup,
        *,
        max_cost_usd: float,
        estimated_cost_per_request_usd: float,
    ) -> None:
        self.wrapped = wrapped
        self.estimated_cost_per_request_usd = estimated_cost_per_request_usd
        self.max_calls = max(1, int(max_cost_usd / estimated_cost_per_request_usd))
        self.calls_made = 0

    @property
    def estimated_cost_usd(self) -> float:
        return self.calls_made * self.estimated_cost_per_request_usd

    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        self._charge()
        return await self.wrapped.get_user_by_username(username)

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        self._charge()
        return await self.wrapped.search_users_by_display_name(display_name)

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        self._charge()
        return await self.wrapped.sample_followers(user_id, limit)

    def _charge(self) -> None:
        if self.calls_made >= self.max_calls:
            raise ApiCostBudgetExceeded(
                self.calls_made,
                self.max_calls,
                self.estimated_cost_usd,
            )
        self.calls_made += 1
