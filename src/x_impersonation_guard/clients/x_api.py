"""X API wrapper.

This module keeps live API access behind an interface so tests can run offline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from x_impersonation_guard.detectors.base import XProfileLookup
from x_impersonation_guard.models import AccountProfile


class XApiClient(XProfileLookup):
    def __init__(self, bearer_token: str) -> None:
        self.bearer_token = bearer_token
        import tweepy

        self.client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

    async def get_user_by_username(self, username: str) -> AccountProfile | None:
        response = self.client.get_user(
            username=username,
            user_fields=[
                "created_at",
                "description",
                "profile_image_url",
                "public_metrics",
                "verified",
                "verified_type",
            ],
        )
        if response.data is None:
            return None
        return _profile_from_tweepy_user(response.data)

    async def search_users_by_display_name(
        self, display_name: str
    ) -> list[AccountProfile]:
        query = f'"{display_name}"'
        response = self.client.search_recent_tweets(
            query=query,
            max_results=25,
            expansions=["author_id"],
            user_fields=[
                "created_at",
                "description",
                "profile_image_url",
                "public_metrics",
                "verified",
                "verified_type",
            ],
        )
        users = response.includes.get("users", []) if response.includes else []
        return [_profile_from_tweepy_user(user) for user in users]

    async def sample_followers(self, user_id: str, limit: int) -> list[AccountProfile]:
        response = self.client.get_users_followers(
            id=user_id,
            max_results=min(limit, 1000),
            user_fields=[
                "created_at",
                "description",
                "profile_image_url",
                "public_metrics",
                "verified",
                "verified_type",
            ],
        )
        return [_profile_from_tweepy_user(user) for user in response.data or []]


def _profile_from_tweepy_user(user: Any) -> AccountProfile:
    metrics = getattr(user, "public_metrics", None) or {}
    created_at = getattr(user, "created_at", None)
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return AccountProfile(
        id=str(user.id),
        username=str(user.username),
        name=str(user.name),
        description=str(getattr(user, "description", "") or ""),
        verified=bool(getattr(user, "verified", False)),
        verified_affiliation=getattr(user, "verified_type", None),
        followers_count=int(metrics.get("followers_count", 0)),
        following_count=int(metrics.get("following_count", 0)),
        tweet_count=int(metrics.get("tweet_count", 0)),
        created_at=created_at,
        profile_image_url=getattr(user, "profile_image_url", None),
    )
