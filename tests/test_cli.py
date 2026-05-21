import json
from pathlib import Path

from x_impersonation_guard.cli import main


def test_scan_fixture_writes_report_without_live_api(tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "accounts.json"
    fixture.write_text(
        json.dumps(
            {
                "protected": {
                    "id": "1",
                    "username": "mainacct",
                    "name": "Main Account",
                    "description": "Official founder account. No DMs.",
                    "verified": True,
                    "followers_count": 100000,
                    "following_count": 10,
                    "created_at": "2018-01-01T00:00:00Z",
                    "profile_image_url": "https://example.com/main.jpg",
                },
                "candidates": [
                    {
                        "id": "2",
                        "username": "mainacct_help",
                        "name": "Main Account",
                        "description": "Official founder account. DM for help.",
                        "verified": False,
                        "followers_count": 5,
                        "following_count": 700,
                        "created_at": "2026-05-01T00:00:00Z",
                        "profile_image_url": "https://example.com/main-copy.jpg",
                    }
                ],
            }
        )
    )

    exit_code = main(["scan-fixture", "--input", str(fixture)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "block_recommended" in captured.out
    assert "No accounts were blocked" in captured.out
