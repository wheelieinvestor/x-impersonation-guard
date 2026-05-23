from datetime import UTC, datetime
from pathlib import Path

import pytest

import x_impersonation_guard.detection as detection
from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.detection import run_scan
from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import AccountProfile
from x_impersonation_guard.storage.repository import ReviewStore


def _wheelie_config() -> AppConfig:
    return AppConfig.model_validate(
        default_config_dict(
            handle="wheelieinvestor",
            display_name="Wheelie Investor",
            reporter_name="Dean Ahrens",
            reporter_email="dean@example.com",
        )
    )


class FakeLookup(XProfileLookup):
    def __init__(self) -> None:
        self.protected = AccountProfile(
            id="1",
            username="wheelieinvestor",
            name="Wheelie Investor",
            followers_count=100_000,
            created_at=datetime(2019, 1, 1, tzinfo=UTC),
            profile_image_phash="0000000000000000",
        )
        self.fake = AccountProfile(
            id="2",
            username="whee1ieinvestor",
            name="Wheelie Investor",
            followers_count=5,
            following_count=800,
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
            profile_image_phash="0000000000000001",
        )

    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        if username == "wheelieinvestor":
            return self.protected
        if username == "whee1ieinvestor":
            return self.fake
        return None

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        if display_name == "Wheelie Investor":
            return [self.fake]
        return []

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        del user_id, limit
        return [self.fake]


@pytest.mark.asyncio
async def test_run_scan_dedupes_scores_and_writes_queue(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _wheelie_config()
    store = ReviewStore(tmp_path / "db.sqlite")
    results = await run_scan(cfg, cfg.protected_identities[0], FakeLookup(), store)
    assert len(results) == 1
    assert results[0].score == 100
    rows = store.list_queue("wheelieinvestor")
    assert len(rows) == 1
    assert rows[0].handle == "whee1ieinvestor"


class ImageLookup(FakeLookup):
    def __init__(self) -> None:
        super().__init__()
        self.protected = AccountProfile.model_validate(
            {
                "id": "1",
                "username": "wheelieinvestor",
                "name": "Wheelie Investor",
                "followers_count": 100_000,
                "created_at": datetime(2019, 1, 1, tzinfo=UTC),
                "profile_image_url": "https://example.com/protected.jpg",
            }
        )
        self.fake = AccountProfile.model_validate(
            {
                "id": "2",
                "username": "whee1ieinvestor",
                "name": "Wheelie Investor",
                "followers_count": 5,
                "following_count": 800,
                "created_at": datetime(2026, 5, 1, tzinfo=UTC),
                "profile_image_url": "https://example.com/fake.jpg",
            }
        )


@pytest.mark.asyncio
async def test_run_scan_hashes_profile_images_before_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_phash_url(url: str) -> str:
        if "protected" in url:
            return "0000000000000000"
        return "0000000000000001"

    monkeypatch.setattr(detection, "_phash_url", fake_phash_url)
    cfg = _wheelie_config()
    store = ReviewStore(tmp_path / "db.sqlite")
    results = await run_scan(cfg, cfg.protected_identities[0], ImageLookup(), store)

    assert results[0].signals.image_similarity > 0.9
    assert results[0].score == 100
