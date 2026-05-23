from datetime import UTC, datetime, timedelta

from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.models import AccountProfile, Priority
from x_impersonation_guard.scoring.scorer import score_candidate


def _cfg() -> AppConfig:
    return AppConfig.model_validate(default_config_dict())


def test_score_candidate_affiliation_and_predates_mitigations() -> None:
    cfg = _cfg()
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        followers_count=100_000,
    )
    candidate = AccountProfile(
        id="2",
        username="wheelieinvest0r",
        name="Wheelie Investor",
        verified=True,
        verified_affiliation="Other Org",
        created_at=datetime(2019, 1, 1, tzinfo=UTC),
        followers_count=10,
        tweet_count=1,
    )
    result = score_candidate(
        protected, candidate, cfg.protected_identities[0], cfg.scoring
    )
    assert result.score < 70
    assert any("affiliation" in item for item in result.mitigations)
    assert any("predates" in item for item in result.mitigations)


def test_score_candidate_low_confidence_stored_outside_default_queue() -> None:
    cfg = _cfg()
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        followers_count=100_000,
    )
    candidate = AccountProfile(
        id="2",
        username="wheelieinvestorx",
        name="Wheelie Investor",
        description="follow @wheelieinvestor for options ideas",
        followers_count=500,
        tweet_count=1,
        created_at=datetime.now(UTC) - timedelta(days=300),
    )
    result = score_candidate(
        protected, candidate, cfg.protected_identities[0], cfg.scoring
    )
    assert 40 <= result.score < 70
    assert result.priority == Priority.LOW
    assert result.queue == "low_confidence"
