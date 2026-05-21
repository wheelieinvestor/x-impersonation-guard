import json

import pytest

from x_impersonation_guard.xurl_client import XurlClient, XurlError


def test_block_requires_explicit_execute() -> None:
    calls: list[list[str]] = []
    client = XurlClient(runner=lambda argv: calls.append(argv) or "{}")

    result = client.block_user("123", execute=False)

    assert result["dry_run"] is True
    assert calls == []


def test_block_executes_expected_x_api_endpoint() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        calls.append(argv)
        return json.dumps({"data": {"blocking": True}})

    client = XurlClient(authenticated_user_id="999", runner=runner)

    result = client.block_user("123", execute=True)

    assert result == {"data": {"blocking": True}}
    assert calls == [
        [
            "xurl",
            "-X",
            "POST",
            "/2/users/999/blocking",
            "-d",
            '{"target_user_id":"123"}',
        ]
    ]


def test_block_fails_closed_without_authenticated_user_id() -> None:
    client = XurlClient(runner=lambda _argv: "{}")

    with pytest.raises(XurlError, match="authenticated user id"):
        client.block_user("123", execute=True)
