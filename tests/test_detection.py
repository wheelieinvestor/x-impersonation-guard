from x_impersonation_guard.detection import DetectionConfig, score_candidate
from x_impersonation_guard.models import AccountProfile


def test_scores_exact_name_and_bio_similarity_with_protective_evidence() -> None:
    main = AccountProfile(
        id="1",
        username="mainacct",
        name="Main Account",
        description="Official founder account. No DMs for crypto.",
        verified=True,
        followers_count=100_000,
        following_count=100,
        created_at="2018-01-01T00:00:00Z",
        profile_image_url="https://example.com/main.jpg",
    )
    candidate = AccountProfile(
        id="2",
        username="mainacct_support",
        name="Main Account",
        description="Official founder account. DM me for crypto support.",
        verified=False,
        followers_count=43,
        following_count=880,
        created_at="2026-05-01T00:00:00Z",
        profile_image_url="https://example.com/main-copy.jpg",
    )

    result = score_candidate(main, candidate, DetectionConfig())

    assert result.action == "block_recommended"
    assert result.score >= 80
    assert "display name matches protected account" in result.reasons
    assert "bio is highly similar to protected account" in result.reasons
    assert "candidate is young and low-follower" in result.reasons


def test_does_not_recommend_block_for_legitimate_high_follow_context_account() -> None:
    main = AccountProfile(
        id="1",
        username="mainacct",
        name="Main Account",
        description="Official founder account.",
        verified=True,
        followers_count=100_000,
        following_count=100,
        created_at="2018-01-01T00:00:00Z",
        profile_image_url="https://example.com/main.jpg",
    )
    candidate = AccountProfile(
        id="3",
        username="mainaccountnews",
        name="Main Account News",
        description="Independent news and commentary about Main Account.",
        verified=True,
        followers_count=25_000,
        following_count=100,
        created_at="2019-01-01T00:00:00Z",
        profile_image_url="https://example.com/news.jpg",
    )

    result = score_candidate(main, candidate, DetectionConfig())

    assert result.action == "review"
    assert result.score < 80
    assert "candidate is verified" in result.mitigations
