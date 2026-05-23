from datetime import UTC, datetime, timedelta

from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.models import AccountProfile, Priority
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.scoring.signals import (
    account_age_signal,
    contains_parody_disclaimer,
    handle_similarity,
)


def _cfg() -> AppConfig:
    return AppConfig.model_validate(default_config_dict())


def _protected() -> AccountProfile:
    return AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        description="Options seller and investor",
        followers_count=100_000,
        created_at=datetime(2019, 1, 1, tzinfo=UTC),
        profile_image_phash="0000000000000000",
    )


def test_handle_similarity_accounts_for_confusables() -> None:
    assert handle_similarity("whee1ieinvestor", "wheelieinvestor") > 0.9
    assert handle_similarity("wheelieinvestⓞr", "wheelieinvestor") > 0.9
    assert handle_similarity("wheelieinvest$r", "wheelieinvestor") > 0.8
    assert handle_similarity("totallydifferent", "wheelieinvestor") < 0.5


def test_account_age_signal_scores_new_accounts_high() -> None:
    now = datetime(2026, 5, 1, tzinfo=UTC)
    assert account_age_signal(now - timedelta(days=2), now) == 1.0
    assert account_age_signal(now - timedelta(days=400), now) == 0.0


def test_score_candidate_critical_image_and_handle_match() -> None:
    cfg = _cfg()
    candidate = AccountProfile(
        id="2",
        username="whee1ieinvestor",
        name="Wheelie Investor",
        description="Options seller and investor",
        followers_count=10,
        following_count=900,
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
        profile_image_phash="0000000000000001",
    )
    result = score_candidate(
        _protected(), candidate, cfg.protected_identities[0], cfg.scoring
    )
    assert result.score == 100
    assert result.priority == Priority.CRITICAL
    assert result.queue == "review_queue"
    assert "profile image is near-identical and handle is similar" in result.reasons


def test_score_candidate_lowers_parody_accounts() -> None:
    cfg = _cfg()
    candidate = AccountProfile(
        id="3",
        username="wheelieinvestorfan",
        name="Wheelie Investor Fan",
        description="unofficial fan account not affiliated",
        followers_count=10,
        following_count=900,
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    result = score_candidate(
        _protected(), candidate, cfg.protected_identities[0], cfg.scoring
    )
    assert contains_parody_disclaimer(candidate)
    assert result.score < 70
    assert any("parody" in item for item in result.mitigations)


def test_score_candidate_discards_protected_account() -> None:
    cfg = _cfg()
    result = score_candidate(
        _protected(), _protected(), cfg.protected_identities[0], cfg.scoring
    )
    assert result.should_store is False
    assert result.score == 0
