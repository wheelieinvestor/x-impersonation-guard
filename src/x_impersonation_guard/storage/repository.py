"""Review queue repository."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from x_impersonation_guard.models import (
    AccountProfile,
    CandidateSource,
    QueueStatus,
    ScoreResult,
)
from x_impersonation_guard.storage.models import Base, CandidateRecord, ReportRecord


class ReviewStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def upsert_scored_candidate(
        self,
        identity_handle: str,
        source: CandidateSource,
        result: ScoreResult,
    ) -> int | None:
        if not result.should_store:
            return None
        now = datetime.now(UTC)
        with self.session_factory() as session:
            existing = session.scalar(
                select(CandidateRecord).where(
                    CandidateRecord.identity_handle == identity_handle,
                    CandidateRecord.x_user_id == result.candidate.id,
                )
            )
            if existing is None:
                existing = CandidateRecord(
                    identity_handle=identity_handle,
                    x_user_id=result.candidate.id,
                    handle=result.candidate.username,
                    display_name=result.candidate.name,
                    source=source.value,
                    profile_json=result.candidate.model_dump_json(),
                    score=result.score,
                    priority=result.priority.value if result.priority else None,
                    queue=result.queue,
                    status=QueueStatus.PENDING.value,
                    score_breakdown_json=result.model_dump_json(),
                    created_at=now,
                    updated_at=now,
                )
                session.add(existing)
            else:
                existing.handle = result.candidate.username
                existing.display_name = result.candidate.name
                existing.source = source.value
                existing.profile_json = result.candidate.model_dump_json()
                existing.score = result.score
                existing.priority = result.priority.value if result.priority else None
                existing.queue = result.queue
                existing.score_breakdown_json = result.model_dump_json()
                existing.updated_at = now
            session.commit()
            return existing.id

    def list_queue(
        self,
        identity_handle: str | None = None,
        status: QueueStatus = QueueStatus.PENDING,
    ) -> list[CandidateRecord]:
        with self.session_factory() as session:
            stmt = select(CandidateRecord).where(CandidateRecord.status == status.value)
            if identity_handle:
                stmt = stmt.where(CandidateRecord.identity_handle == identity_handle)
            stmt = stmt.order_by(
                CandidateRecord.score.desc(), CandidateRecord.updated_at.desc()
            )
            return list(session.scalars(stmt).all())

    def queue_status_counts(self, identity_handle: str | None = None) -> dict[str, int]:
        counts = {status.value: 0 for status in QueueStatus}
        with self.session_factory() as session:
            stmt = select(CandidateRecord.status, func.count()).group_by(
                CandidateRecord.status
            )
            if identity_handle:
                stmt = stmt.where(CandidateRecord.identity_handle == identity_handle)
            for status, count in session.execute(stmt):
                counts[str(status)] = int(count)
        return counts

    def get_candidate(self, candidate_id: int) -> CandidateRecord | None:
        with self.session_factory() as session:
            return session.get(CandidateRecord, candidate_id)

    def set_status(self, candidate_id: int, status: QueueStatus) -> None:
        with self.session_factory() as session:
            record = session.get(CandidateRecord, candidate_id)
            if record is None:
                raise ValueError(f"candidate not found: {candidate_id}")
            record.status = status.value
            record.updated_at = datetime.now(UTC)
            session.commit()

    def record_report(
        self,
        candidate_id: int,
        identity_handle: str,
        candidate_handle: str,
        status: str,
        report_dir: Path | None = None,
        error: str | None = None,
    ) -> int:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            record = ReportRecord(
                candidate_id=candidate_id,
                identity_handle=identity_handle,
                candidate_handle=candidate_handle,
                status=status,
                report_dir=str(report_dir) if report_dir else None,
                error=error,
                created_at=now,
            )
            session.add(record)
            session.commit()
            return record.id

    def reports_in_window(self, identity_handle: str, hours: int = 24) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        with self.session_factory() as session:
            rows = session.scalars(
                select(ReportRecord).where(
                    ReportRecord.identity_handle == identity_handle,
                    ReportRecord.created_at >= cutoff,
                    ReportRecord.status == "submitted",
                )
            ).all()
            return len(rows)

    def list_reports(self, identity_handle: str | None = None) -> list[ReportRecord]:
        with self.session_factory() as session:
            stmt = select(ReportRecord)
            if identity_handle:
                stmt = stmt.where(ReportRecord.identity_handle == identity_handle)
            stmt = stmt.order_by(ReportRecord.created_at.desc())
            return list(session.scalars(stmt).all())

    def cached_profiles(
        self, identity_handle: str | None = None
    ) -> list[AccountProfile]:
        with self.session_factory() as session:
            stmt = select(CandidateRecord)
            if identity_handle:
                stmt = stmt.where(CandidateRecord.identity_handle == identity_handle)
            records = session.scalars(stmt).all()
            return [profile_from_record(record) for record in records]


def profile_from_record(record: CandidateRecord) -> AccountProfile:
    raw = json.loads(record.profile_json)
    return AccountProfile.model_validate(raw)
