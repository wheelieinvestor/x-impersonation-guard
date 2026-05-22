from __future__ import annotations

import pytest

from x_impersonation_guard.clients.cost_guard import (
    ApiCostBudgetExceeded,
    CostGuardedLookup,
)
from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import AccountProfile


class FakeLookup(XProfileLookup):
    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        return AccountProfile(id=username, username=username, name=username)

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        return [
            AccountProfile(
                id=display_name,
                username=display_name.replace(" ", "_"),
                name=display_name,
            )
        ]

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        del limit
        return [AccountProfile(id=user_id, username=user_id, name=user_id)]


@pytest.mark.asyncio
async def test_cost_guard_allows_calls_inside_budget() -> None:
    lookup = CostGuardedLookup(
        FakeLookup(),
        max_cost_usd=0.03,
        estimated_cost_per_request_usd=0.01,
    )

    assert lookup.max_calls == 3
    assert await lookup.get_user_by_username("creator") is not None
    assert await lookup.search_users_by_display_name("Creator") != []
    assert await lookup.sample_followers("creator", 10) != []
    assert lookup.calls_made == 3
    assert lookup.estimated_cost_usd == pytest.approx(0.03)


@pytest.mark.asyncio
async def test_cost_guard_fails_closed_after_budget() -> None:
    lookup = CostGuardedLookup(
        FakeLookup(),
        max_cost_usd=0.02,
        estimated_cost_per_request_usd=0.01,
    )

    await lookup.get_user_by_username("creator")
    await lookup.search_users_by_display_name("Creator")
    with pytest.raises(ApiCostBudgetExceeded) as excinfo:
        await lookup.sample_followers("creator", 10)

    assert excinfo.value.calls_made == 2
    assert excinfo.value.max_calls == 2
    assert "estimated X API scan cost limit reached" in str(excinfo.value)
