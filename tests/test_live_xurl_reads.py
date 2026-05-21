from x_impersonation_guard.xurl_client import XurlClient


def test_lookup_user_by_username_requests_profile_fields() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        calls.append(argv)
        return '{"data":{"id":"1","username":"mainacct","name":"Main Account"}}'

    client = XurlClient(runner=runner)

    result = client.lookup_user_by_username("@mainacct")

    assert result["data"]["id"] == "1"
    assert calls == [
        [
            "xurl",
            "/2/users/by/username/mainacct?user.fields=created_at,description,profile_image_url,public_metrics,verified",
        ]
    ]


def test_search_recent_authors_requests_expanded_user_objects() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> str:
        calls.append(argv)
        return '{"includes":{"users":[]}}'

    client = XurlClient(runner=runner)

    result = client.search_recent_authors('"Main Account" -is:retweet', max_results=10)

    assert result == {"includes": {"users": []}}
    assert calls == [
        [
            "xurl",
            "/2/tweets/search/recent?query=%22Main+Account%22+-is%3Aretweet&max_results=10&expansions=author_id&tweet.fields=created_at,author_id&user.fields=created_at,description,profile_image_url,public_metrics,verified",
        ]
    ]
