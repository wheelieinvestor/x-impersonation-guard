from datetime import UTC, datetime

from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.models import AccountProfile, CandidateSource, QueueStatus
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.storage.repository import ReviewStore, profile_from_record


def _wheelie_config() -> AppConfig:
    return AppConfig.model_validate(
        default_config_dict(
            handle="wheelieinvestor",
            display_name="Wheelie Investor",
            reporter_name="Dean Ahrens",
            reporter_email="dean@example.com",
        )
    )


def test_review_store_inserts_and_updates_scored_candidate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _wheelie_config()
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        followers_count=100_000,
    )
    candidate = AccountProfile(
        id="2",
        username="whee1ieinvestor",
        name="Wheelie Investor",
        followers_count=10,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    result = score_candidate(
        protected, candidate, cfg.protected_identities[0], cfg.scoring
    )
    store = ReviewStore(tmp_path / "db.sqlite")

    first = store.upsert_scored_candidate(
        "wheelieinvestor", CandidateSource.FIXTURE, result
    )
    second = store.upsert_scored_candidate(
        "wheelieinvestor", CandidateSource.FIXTURE, result
    )

    assert first == second
    rows = store.list_queue("wheelieinvestor")
    assert len(rows) == 1
    assert profile_from_record(rows[0]).username == "whee1ieinvestor"
    assert store.cached_profiles("wheelieinvestor")[0].username == "whee1ieinvestor"
    assert store.cached_profiles("unknown") == []
    assert store.queue_status_counts("wheelieinvestor")["pending"] == 1
    assert store.queue_status_counts("unknown")["pending"] == 0


def test_review_store_status_and_report_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = ReviewStore(tmp_path / "db.sqlite")
    report_id = store.record_report(
        candidate_id=1,
        identity_handle="wheelieinvestor",
        candidate_handle="fake",
        status="submitted",
    )
    assert report_id == 1
    assert store.reports_in_window("wheelieinvestor") == 1
    store.record_report(2, "wheelieinvestor", "fake2", "dry_run")
    assert store.reports_in_window("wheelieinvestor") == 1

    # missing candidate status changes fail closed
    import pytest

    with pytest.raises(ValueError):
        store.set_status(99, QueueStatus.APPROVED)
