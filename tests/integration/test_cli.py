from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from x_impersonation_guard.cli import app
from x_impersonation_guard.models import AccountProfile


def _fixture(path: Path) -> Path:
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        followers_count=100_000,
        created_at=datetime(2019, 1, 1, tzinfo=UTC),
        profile_image_phash="0000000000000000",
    )
    candidate = AccountProfile(
        id="2",
        username="whee1ieinvestor",
        name="Wheelie Investor",
        followers_count=5,
        following_count=800,
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        profile_image_phash="0000000000000001",
    )
    fixture_path = path / "fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "protected": protected.model_dump(mode="json"),
                "candidates": [candidate.model_dump(mode="json")],
            }
        )
    )
    return fixture_path


def test_init_writes_config(tmp_path: Path, runner: CliRunner) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(app, ["init", "--config", str(config)])
    assert result.exit_code == 0
    assert config.exists()
    assert "WARNING" in result.stderr


def test_scan_fixture_lists_and_dry_run_report(
    tmp_path: Path,
    config_path: Path,
    runner: CliRunner,
) -> None:
    fixture = _fixture(tmp_path)
    scan = runner.invoke(
        app,
        ["scan-fixture", "--config", str(config_path), "--input", str(fixture)],
    )
    assert scan.exit_code == 0, scan.output
    assert "score=100" in scan.output

    listed = runner.invoke(app, ["list", "--config", str(config_path)])
    assert listed.exit_code == 0
    assert "@whee1ieinvestor" in listed.output

    approved = runner.invoke(
        app, ["review", "--config", str(config_path), "--approve", "1"]
    )
    assert approved.exit_code == 0

    reported = runner.invoke(app, ["report", "1", "--config", str(config_path)])
    assert reported.exit_code == 0, reported.output
    assert "dry-run evidence package created" in reported.output

    history = runner.invoke(app, ["log", "--config", str(config_path)])
    assert history.exit_code == 0
    assert "dry_run" in history.output
