"""Image hash detector for cached candidates."""

from __future__ import annotations

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector
from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    DetectionCandidate,
)
from x_impersonation_guard.utils.image_hash import hamming_distance


class ImageLookupDetector(Detector):
    source = CandidateSource.IMAGE_LOOKUP

    def __init__(
        self, cached_profiles: list[AccountProfile], max_distance: int = 8
    ) -> None:
        self.cached_profiles = cached_profiles
        self.max_distance = max_distance

    async def detect(
        self,
        identity: ProtectedIdentity,
        protected_profile: AccountProfile,
    ) -> list[DetectionCandidate]:
        if not protected_profile.profile_image_phash:
            return []
        candidates: list[DetectionCandidate] = []
        for profile in self.cached_profiles:
            distance = hamming_distance(
                profile.profile_image_phash,
                protected_profile.profile_image_phash,
            )
            if distance is not None and distance <= self.max_distance:
                candidates.append(
                    DetectionCandidate(
                        identity_handle=identity.handle,
                        source=self.source,
                        profile=profile,
                        raw={"hamming_distance": distance},
                    )
                )
        return candidates
