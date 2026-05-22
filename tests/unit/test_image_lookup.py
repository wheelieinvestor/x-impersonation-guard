import pytest

from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.detectors.image_lookup import ImageLookupDetector
from x_impersonation_guard.models import AccountProfile


@pytest.mark.asyncio
async def test_image_lookup_returns_cached_near_matches() -> None:
    cfg = AppConfig.model_validate(default_config_dict())
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie",
        profile_image_phash="0000000000000000",
    )
    near = AccountProfile(
        id="2",
        username="fake",
        name="Fake",
        profile_image_phash="000000000000000f",
    )
    far = AccountProfile(
        id="3",
        username="far",
        name="Far",
        profile_image_phash="ffffffffffffffff",
    )
    detector = ImageLookupDetector([near, far], max_distance=8)
    results = await detector.detect(cfg.protected_identities[0], protected)
    assert [item.profile.username for item in results] == ["fake"]
    assert results[0].raw["hamming_distance"] == 4


@pytest.mark.asyncio
async def test_image_lookup_skips_without_protected_hash() -> None:
    cfg = AppConfig.model_validate(default_config_dict())
    detector = ImageLookupDetector([])
    results = await detector.detect(
        cfg.protected_identities[0],
        AccountProfile(id="1", username="wheelieinvestor", name="Wheelie"),
    )
    assert results == []
