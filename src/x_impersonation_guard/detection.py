"""Deterministic impersonation scoring.

The detector intentionally recommends review/block candidates; it does not claim to
prove an account was bought or compromised. That proof requires platform-side data.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from x_impersonation_guard.models import AccountProfile, DetectionResult


@dataclass(frozen=True)
class DetectionConfig:
    """Thresholds for deterministic impersonation recommendations."""

    block_threshold: int = 80
    review_threshold: int = 30
    low_follower_threshold: int = 100
    high_following_threshold: int = 500


def score_candidate(
    protected: AccountProfile,
    candidate: AccountProfile,
    config: DetectionConfig,
) -> DetectionResult:
    """Score one candidate account against a protected main account."""

    score = 0
    reasons: list[str] = []
    mitigations: list[str] = []

    protected_name = _norm(protected.name)
    candidate_name = _norm(candidate.name)
    protected_user = _norm(protected.username)
    candidate_user = _norm(candidate.username)

    if protected_name and protected_name == candidate_name:
        score += 35
        reasons.append("display name matches protected account")
    elif protected_name and protected_name in candidate_name:
        score += 30
        reasons.append("display name contains protected account name")
    elif protected_name and _similarity(protected_name, candidate_name) >= 0.82:
        score += 22
        reasons.append("display name is similar to protected account")

    if (
        protected_user
        and protected_user in candidate_user
        and protected_user != candidate_user
    ):
        score += 20
        reasons.append("username contains protected handle")
    elif protected_user and _similarity(protected_user, candidate_user) >= 0.82:
        score += 16
        reasons.append("username is similar to protected handle")

    if protected.description and candidate.description:
        protected_bio = _norm(protected.description)
        candidate_bio = _norm(candidate.description)
        bio_similarity = _similarity(protected_bio, candidate_bio)
        if bio_similarity >= 0.65:
            score += 20
            reasons.append("bio is highly similar to protected account")
        elif protected_name and protected_name in candidate_bio:
            score += 15
            reasons.append("bio references protected account name")

    if _same_profile_image(protected, candidate):
        score += 25
        reasons.append("profile image URL matches protected account")

    if (
        candidate.followers_count <= config.low_follower_threshold
        and candidate.following_count >= config.high_following_threshold
    ):
        score += 15
        reasons.append("candidate is young and low-follower")

    if candidate.verified:
        score -= 10
        mitigations.append("candidate is verified")

    if candidate.followers_count >= max(10_000, protected.followers_count // 10):
        score -= 5
        mitigations.append("candidate has meaningful follower context")

    score = max(0, min(100, score))
    action = _action(score, config)
    return DetectionResult(
        candidate=candidate,
        score=score,
        action=action,
        reasons=reasons,
        mitigations=mitigations,
    )


def _action(score: int, config: DetectionConfig) -> str:
    if score >= config.block_threshold:
        return "block_recommended"
    if score >= config.review_threshold:
        return "review"
    return "ignore"


def _norm(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left, b=right).ratio()


def _same_profile_image(protected: AccountProfile, candidate: AccountProfile) -> bool:
    if not protected.profile_image_url or not candidate.profile_image_url:
        return False
    return protected.profile_image_url == candidate.profile_image_url
