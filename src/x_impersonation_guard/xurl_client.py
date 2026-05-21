"""Small xurl wrapper with fail-closed write behavior."""

import json
import subprocess
from collections.abc import Callable
from typing import Any
from urllib.parse import quote_plus


class XurlError(RuntimeError):
    """Raised when an X write action cannot be safely performed."""


class XurlClient:
    """Call the official xurl CLI without exposing credentials to application code."""

    def __init__(
        self,
        *,
        authenticated_user_id: str | None = None,
        runner: Callable[[list[str]], str] | None = None,
    ) -> None:
        self.authenticated_user_id = authenticated_user_id
        self._runner = runner or self._run

    def block_user(self, target_user_id: str, *, execute: bool) -> dict[str, Any]:
        """Block a target account only when execute=True and caller ID is known."""

        if not execute:
            return {"dry_run": True, "target_user_id": target_user_id}
        if not self.authenticated_user_id:
            raise XurlError("authenticated user id is required before blocking")

        payload = json.dumps({"target_user_id": target_user_id}, separators=(",", ":"))
        output = self._runner(
            [
                "xurl",
                "-X",
                "POST",
                f"/2/users/{self.authenticated_user_id}/blocking",
                "-d",
                payload,
            ]
        )
        return json.loads(output or "{}")

    def lookup_user_by_username(self, username: str) -> dict[str, Any]:
        """Read one public user profile by handle."""

        handle = username.strip().removeprefix("@")
        endpoint = (
            f"/2/users/by/username/{handle}?"
            "user.fields=created_at,description,profile_image_url,public_metrics,verified"
        )
        return json.loads(self._runner(["xurl", endpoint]) or "{}")

    def search_recent_authors(self, query: str, *, max_results: int) -> dict[str, Any]:
        """Search recent posts and expand author profiles for candidate discovery."""

        endpoint = (
            "/2/tweets/search/recent?"
            f"query={quote_plus(query)}&"
            f"max_results={max_results}&"
            "expansions=author_id&"
            "tweet.fields=created_at,author_id&"
            "user.fields=created_at,description,profile_image_url,public_metrics,verified"
        )
        return json.loads(self._runner(["xurl", endpoint]) or "{}")

    @staticmethod
    def _run(argv: list[str]) -> str:
        try:
            return subprocess.check_output(argv, text=True, stderr=subprocess.PIPE)
        except FileNotFoundError as exc:
            raise XurlError("xurl is not installed or not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            raise XurlError(exc.stderr.strip() or "xurl command failed") from exc
