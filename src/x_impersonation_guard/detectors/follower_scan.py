"""Follower sample detector."""

from __future__ import annotations

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector, XProfileLookup
from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    DetectionCandidate,
)


class FollowerScanDetector(Detector):
    source = CandidateSource.FOLLOWER_SCAN

    def __init__(self, lookup: XProfileLookup, sample_limit: int = 500) -> None:
        self.lookup = lookup
        self.sample_limit = sample_limit

    async def detect(
        self,
        identity: ProtectedIdentity,
        protected_profile: AccountProfile,
    ) -> list[DetectionCandidate]:
        if not identity.user_id and not protected_profile.id:
            return []
        user_id = identity.user_id or protected_profile.id
        profiles = await self.lookup.sample_followers(user_id, self.sample_limit)
        return [
            DetectionCandidate(
                identity_handle=identity.handle,
                source=self.source,
                profile=profile,
                raw={"sample_limit": self.sample_limit},
            )
            for profile in profiles
        ]
