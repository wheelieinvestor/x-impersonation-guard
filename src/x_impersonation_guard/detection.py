"""Detection plus scoring orchestration."""

from __future__ import annotations

from io import BytesIO

import httpx
import imagehash
import structlog
from PIL import Image

from x_impersonation_guard.config import AppConfig, ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector, XProfileLookup
from x_impersonation_guard.detectors.display_name_search import (
    DisplayNameSearchDetector,
)
from x_impersonation_guard.detectors.follower_scan import FollowerScanDetector
from x_impersonation_guard.detectors.handle_variants import HandleVariantDetector
from x_impersonation_guard.detectors.image_lookup import ImageLookupDetector
from x_impersonation_guard.models import AccountProfile, DetectionCandidate, ScoreResult
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.storage.repository import ReviewStore

logger = structlog.get_logger(__name__)


async def run_scan(
    config: AppConfig,
    identity: ProtectedIdentity,
    lookup: XProfileLookup,
    store: ReviewStore,
    detectors: list[Detector] | None = None,
) -> list[ScoreResult]:
    protected = await lookup.get_user_by_username(identity.handle)
    if protected is None:
        protected = AccountProfile(
            id=identity.user_id or identity.handle,
            username=identity.handle,
            name=identity.display_name,
        )
    await enrich_profile_image_hash(protected)
    detectors = detectors or [
        HandleVariantDetector(lookup),
        DisplayNameSearchDetector(lookup),
        FollowerScanDetector(lookup),
        ImageLookupDetector(store.cached_profiles(identity.handle)),
    ]
    raw_candidates: list[DetectionCandidate] = []
    for detector in detectors:
        raw_candidates.extend(await detector.detect(identity, protected))

    deduped: dict[str, DetectionCandidate] = {}
    for candidate in raw_candidates:
        if candidate.profile.id == protected.id:
            continue
        deduped.setdefault(candidate.profile.id, candidate)

    results: list[ScoreResult] = []
    for candidate in deduped.values():
        await enrich_profile_image_hash(candidate.profile)
        result = score_candidate(protected, candidate.profile, identity, config.scoring)
        store.upsert_scored_candidate(identity.handle, candidate.source, result)
        results.append(result)
    return sorted(results, key=lambda item: item.score, reverse=True)


async def enrich_profile_image_hash(profile: AccountProfile) -> None:
    if profile.profile_image_phash or profile.profile_image_url is None:
        return
    try:
        profile.profile_image_phash = await _phash_url(str(profile.profile_image_url))
    except Exception as exc:
        logger.warning(
            "profile_image_hash_failed",
            username=profile.username,
            url=str(profile.profile_image_url),
            error=str(exc),
        )


async def _phash_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    with Image.open(BytesIO(response.content)) as image:
        return str(imagehash.phash(image))
