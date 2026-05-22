from datetime import UTC, datetime, timedelta

from x_impersonation_guard.models import AccountProfile
from x_impersonation_guard.scoring.signals import (
    bio_similarity,
    display_name_similarity,
    follow_back_pattern_signal,
    follower_ratio_signal,
    is_critical_image_match,
    posting_behavior_signal,
    profile_pic_similarity,
    verified_status_signal,
)
from x_impersonation_guard.utils.image_hash import hamming_distance


def test_similarity_signal_edge_cases() -> None:
    assert display_name_similarity("", "Wheelie Investor") == 0.0
    assert bio_similarity("follow @wheelieinvestor", "", "wheelieinvestor") == 0.9
    assert profile_pic_similarity(None, "0000000000000000") == 0.0
    assert hamming_distance(None, "0000000000000000") is None


def test_follower_ratio_close_to_protected_is_suspicious() -> None:
    protected = AccountProfile(
        id="1", username="wheelieinvestor", name="Wheelie", followers_count=1000
    )
    candidate = AccountProfile(
        id="2", username="fake", name="Fake", followers_count=950
    )
    assert follower_ratio_signal(candidate, protected) == 0.8


def test_follow_back_and_posting_behavior_signals() -> None:
    candidate = AccountProfile(
        id="2",
        username="fake",
        name="Fake",
        tweet_count=3,
        protected_followers_followed=100,
        mutual_followers=5,
        recent_posts_containing_protected_handle=1,
    )
    assert follow_back_pattern_signal(candidate) == 1.0
    assert posting_behavior_signal(candidate, "wheelieinvestor") == 1.0
    assert verified_status_signal(candidate) == 0.0


def test_critical_image_match_false_without_hashes() -> None:
    protected = AccountProfile(id="1", username="wheelieinvestor", name="Wheelie")
    candidate = AccountProfile(id="2", username="wheelieinvest0r", name="Wheelie")
    assert is_critical_image_match(candidate, protected) is False


def test_account_age_midpoint() -> None:
    from x_impersonation_guard.scoring.signals import account_age_signal

    now = datetime(2026, 5, 1, tzinfo=UTC)
    assert 0.3 < account_age_signal(now - timedelta(days=90), now) < 0.6
