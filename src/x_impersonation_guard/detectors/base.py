"""Detector interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    DetectionCandidate,
)


class XProfileLookup(ABC):
    @abstractmethod
    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        raise NotImplementedError

    @abstractmethod
    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        raise NotImplementedError


class Detector(ABC):
    source: CandidateSource

    @abstractmethod
    async def detect(
        self,
        identity: ProtectedIdentity,
        protected_profile: AccountProfile,
    ) -> list[DetectionCandidate]:
        raise NotImplementedError
