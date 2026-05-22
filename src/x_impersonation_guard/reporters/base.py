"""Reporter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from x_impersonation_guard.config import ProtectedIdentity
from x_impersonation_guard.models import AccountProfile, ScoreResult


@dataclass(frozen=True)
class ReportResult:
    submitted: bool
    report_dir: Path
    message: str


class Reporter(ABC):
    @abstractmethod
    async def submit(
        self,
        identity: ProtectedIdentity,
        candidate_id: int,
        candidate: AccountProfile,
        score: ScoreResult,
    ) -> ReportResult:
        raise NotImplementedError
