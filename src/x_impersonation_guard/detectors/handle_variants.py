"""Username variant detector."""

from __future__ import annotations

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector, XProfileLookup
from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    DetectionCandidate,
)
from x_impersonation_guard.utils.handle_variants import generate_handle_variants


class HandleVariantDetector(Detector):
    source = CandidateSource.HANDLE_VARIANT

    def __init__(self, lookup: XProfileLookup, max_variants: int = 400) -> None:
        self.lookup = lookup
        self.max_variants = max_variants

    async def detect(
        self,
        identity: ProtectedIdentity,
        protected_profile: AccountProfile,
    ) -> list[DetectionCandidate]:
        del protected_profile
        candidates: list[DetectionCandidate] = []
        variants = generate_handle_variants(
            identity.handle,
            identity.extra_handle_variants,
        )[: self.max_variants]
        for username in variants:
            profile = await self.lookup.get_user_by_username(username)
            if profile is None:
                continue
            candidates.append(
                DetectionCandidate(
                    identity_handle=identity.handle,
                    source=self.source,
                    profile=profile,
                    raw={"variant": username},
                )
            )
        return candidates
