"""Detection plus scoring orchestration."""

from __future__ import annotations

from x_impersonation_guard.config import AppConfig, ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector, XProfileLookup
from x_impersonation_guard.detectors.display_name_search import (
    DisplayNameSearchDetector,
)
from x_impersonation_guard.detectors.follower_scan import FollowerScanDetector
from x_impersonation_guard.detectors.handle_variants import HandleVariantDetector
from x_impersonation_guard.models import AccountProfile, DetectionCandidate, ScoreResult
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.storage.repository import ReviewStore


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
    detectors = detectors or [
        HandleVariantDetector(lookup),
        DisplayNameSearchDetector(lookup),
        FollowerScanDetector(lookup),
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
        result = score_candidate(protected, candidate.profile, identity, config.scoring)
        store.upsert_scored_candidate(identity.handle, candidate.source, result)
        results.append(result)
    return sorted(results, key=lambda item: item.score, reverse=True)
