"""Explainable impersonation scorer."""

from __future__ import annotations

from datetime import UTC, datetime

from x_impersonation_guard.config import ProtectedIdentity, ScoringConfig
from x_impersonation_guard.models import (
    AccountProfile,
    Priority,
    ScoreResult,
    SignalBreakdown,
)
from x_impersonation_guard.scoring import signals

SIGNAL_NAMES = tuple(SignalBreakdown.model_fields.keys())


def score_candidate(
    protected: AccountProfile,
    candidate: AccountProfile,
    identity: ProtectedIdentity,
    config: ScoringConfig,
    now: datetime | None = None,
) -> ScoreResult:
    if (
        candidate.id == protected.id
        or candidate.username.lower() == protected.username.lower()
    ):
        return _discard(candidate, "candidate is the protected account")

    breakdown = SignalBreakdown(
        handle_similarity=signals.handle_similarity(
            candidate.username, protected.username
        ),
        name_similarity=signals.display_name_similarity(
            candidate.name, identity.display_name
        ),
        bio_similarity=signals.bio_similarity(
            candidate.description,
            protected.description,
            protected.username,
        ),
        image_similarity=signals.profile_pic_similarity(
            candidate.profile_image_phash,
            protected.profile_image_phash,
        ),
        account_age=signals.account_age_signal(candidate.created_at, now),
        follower_ratio=signals.follower_ratio_signal(candidate, protected),
        follow_back_pattern=signals.follow_back_pattern_signal(candidate),
        posting_behavior=signals.posting_behavior_signal(candidate, protected.username),
        verified_status=signals.verified_status_signal(candidate),
    )
    weights = config.weights.model_dump()
    signal_values = breakdown.model_dump()
    weighted_scores = {
        name: signal_values[name] * weights[name] for name in SIGNAL_NAMES
    }
    raw_score = sum(weighted_scores.values())
    reasons = _reasons(breakdown)
    mitigations: list[str] = []

    if signals.is_critical_image_match(candidate, protected):
        raw_score = 100.0
        reasons.append("profile image is near-identical and handle is similar")

    if candidate.verified_affiliation:
        raw_score -= 50
        mitigations.append("verified affiliation badge points elsewhere")
    if signals.contains_parody_disclaimer(candidate):
        raw_score -= 40
        mitigations.append(
            "profile clearly labels itself parody, fan, satire, or unofficial"
        )
    if protected.created_at and candidate.created_at:
        protected_created = _aware(protected.created_at)
        candidate_created = _aware(candidate.created_at)
        if candidate_created < protected_created:
            raw_score -= 30
            mitigations.append("candidate predates protected account")

    score = max(0, min(100, round(raw_score)))
    priority, queue = _priority(score, config)
    return ScoreResult(
        candidate=candidate,
        score=score,
        priority=priority,
        signals=breakdown,
        weighted_scores=weighted_scores,
        reasons=reasons,
        mitigations=mitigations,
        should_store=score >= 40,
        queue=queue,
    )


def _discard(candidate: AccountProfile, reason: str) -> ScoreResult:
    zero = SignalBreakdown(**{name: 0.0 for name in SIGNAL_NAMES})
    return ScoreResult(
        candidate=candidate,
        score=0,
        priority=None,
        signals=zero,
        weighted_scores={name: 0.0 for name in SIGNAL_NAMES},
        reasons=[],
        mitigations=[reason],
        should_store=False,
        queue=None,
    )


def _reasons(breakdown: SignalBreakdown) -> list[str]:
    reasons: list[str] = []
    if breakdown.handle_similarity >= 0.75:
        reasons.append("handle is highly similar")
    if breakdown.name_similarity >= 0.8:
        reasons.append("display name is highly similar")
    if breakdown.bio_similarity >= 0.75:
        reasons.append("bio overlaps protected identity")
    if breakdown.image_similarity >= 0.875:
        reasons.append("profile image hash is close")
    if breakdown.account_age >= 0.7:
        reasons.append("account is recently created")
    if breakdown.follower_ratio >= 0.7:
        reasons.append("follower pattern is suspicious")
    if breakdown.follow_back_pattern >= 0.7:
        reasons.append("follow-back pattern targets protected audience")
    if breakdown.posting_behavior >= 0.7:
        reasons.append("posting behavior references protected identity")
    if breakdown.verified_status > 0:
        reasons.append("candidate has paid verification")
    return reasons


def _priority(score: int, config: ScoringConfig) -> tuple[Priority | None, str | None]:
    if score < 40:
        return None, None
    if score < config.thresholds.review_queue_medium:
        return Priority.LOW, "low_confidence"
    if score < config.thresholds.review_queue_high:
        return Priority.MEDIUM, "review_queue"
    if score < 100:
        return Priority.HIGH, "review_queue"
    return Priority.CRITICAL, "review_queue"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
