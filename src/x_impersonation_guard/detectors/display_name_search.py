"""Display name search detector."""

from __future__ import annotations

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.detectors.base import Detector, XProfileLookup
from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    DetectionCandidate,
)


class DisplayNameSearchDetector(Detector):
    source = CandidateSource.DISPLAY_NAME_SEARCH

    def __init__(self, lookup: XProfileLookup) -> None:
        self.lookup = lookup

    async def detect(
        self,
        identity: ProtectedIdentity,
        protected_profile: AccountProfile,
    ) -> list[DetectionCandidate]:
        del protected_profile
        names = [identity.display_name, *identity.extra_display_variants]
        seen: set[str] = set()
        candidates: list[DetectionCandidate] = []
        for name in names:
            for profile in await self.lookup.search_users_by_display_name(name):
                if profile.id in seen:
                    continue
                seen.add(profile.id)
                candidates.append(
                    DetectionCandidate(
                        identity_handle=identity.handle,
                        source=self.source,
                        profile=profile,
                        raw={"display_name_query": name},
                    )
                )
        return candidates
