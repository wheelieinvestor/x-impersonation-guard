"""Pure scoring signal functions."""

from __future__ import annotations

from datetime import UTC, datetime

from rapidfuzz import fuzz

from x_impersonation_guard.models import AccountProfile
from x_impersonation_guard.utils.image_hash import (
    hamming_distance,
    similarity_from_hashes,
)

PARODY_TERMS = ("parody", "fan", "satire", "not affiliated", "unofficial", "joke")
CONFUSABLE_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "l",
        "5": "s",
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
    }
)


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().translate(CONFUSABLE_TRANSLATION).split())


def normalize_handle(value: str) -> str:
    return "".join(ch for ch in normalize_text(value.removeprefix("@")) if ch.isalnum())


def handle_similarity(candidate_handle: str, protected_handle: str) -> float:
    candidate = normalize_handle(candidate_handle).replace("rn", "m").replace("vv", "w")
    protected = normalize_handle(protected_handle).replace("rn", "m").replace("vv", "w")
    if not candidate or not protected:
        return 0.0
    base = fuzz.ratio(candidate, protected) / 100.0
    if protected in candidate and candidate != protected:
        base = max(base, 0.82)
    return min(1.0, base)


def display_name_similarity(candidate_name: str, protected_name: str) -> float:
    candidate = normalize_text(candidate_name)
    protected = normalize_text(protected_name)
    if not candidate or not protected:
        return 0.0
    return fuzz.token_set_ratio(candidate, protected) / 100.0


def bio_similarity(
    candidate_bio: str, protected_bio: str, protected_handle: str
) -> float:
    candidate = normalize_text(candidate_bio)
    protected = normalize_text(protected_bio)
    if not candidate:
        return 0.0
    score = fuzz.token_set_ratio(candidate, protected) / 100.0 if protected else 0.0
    if normalize_handle(protected_handle) in normalize_handle(candidate_bio):
        score = max(score, 0.9)
    return score


def profile_pic_similarity(
    candidate_phash: str | None, protected_phash: str | None
) -> float:
    return similarity_from_hashes(candidate_phash, protected_phash)


def account_age_signal(
    candidate_created_at: datetime | None, now: datetime | None = None
) -> float:
    if candidate_created_at is None:
        return 0.0
    now = now or datetime.now(UTC)
    if candidate_created_at.tzinfo is None:
        candidate_created_at = candidate_created_at.replace(tzinfo=UTC)
    age_days = max(0.0, (now - candidate_created_at).total_seconds() / 86_400)
    if age_days >= 365:
        return 0.0
    if age_days <= 7:
        return 1.0
    return max(0.0, min(1.0, (180.0 - age_days) / 180.0))


def follower_ratio_signal(
    candidate: AccountProfile, protected: AccountProfile
) -> float:
    if candidate.followers_count <= 50 and protected.followers_count >= 1_000:
        return 1.0
    if protected.followers_count and candidate.followers_count:
        ratio = candidate.followers_count / protected.followers_count
        if 0.8 <= ratio <= 1.2:
            return 0.8
    return 0.0


def follow_back_pattern_signal(candidate: AccountProfile) -> float:
    if candidate.protected_followers_followed <= 0:
        return 0.0
    if candidate.mutual_followers == 0:
        return 1.0
    ratio = candidate.protected_followers_followed / max(1, candidate.mutual_followers)
    return min(1.0, ratio / 10.0)


def posting_behavior_signal(candidate: AccountProfile, protected_handle: str) -> float:
    score = 0.0
    if candidate.tweet_count <= 10:
        score += 0.45
    if candidate.recent_posts_containing_protected_handle > 0:
        score += 0.55
    if normalize_handle(protected_handle) in normalize_handle(candidate.description):
        score = max(score, 0.6)
    return min(1.0, score)


def verified_status_signal(candidate: AccountProfile) -> float:
    return 1.0 if candidate.verified else 0.0


def contains_parody_disclaimer(profile: AccountProfile) -> bool:
    text = normalize_text(f"{profile.name} {profile.description}")
    return any(term in text for term in PARODY_TERMS)


def is_critical_image_match(
    candidate: AccountProfile, protected: AccountProfile
) -> bool:
    distance = hamming_distance(
        candidate.profile_image_phash, protected.profile_image_phash
    )
    if distance is None:
        return False
    return (
        distance <= 4
        and handle_similarity(candidate.username, protected.username) > 0.6
    )
