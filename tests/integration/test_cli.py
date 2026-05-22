from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from x_impersonation_guard.cli import app
from x_impersonation_guard.config import load_config
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
    cfg = load_config(config)
    assert cfg.protected_identities[0].handle == "yourhandle"
    assert "Edit the starter identity fields" in result.output
    assert "WARNING" in result.stderr


def test_init_accepts_identity_options(tmp_path: Path, runner: CliRunner) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        [
            "init",
            "--config",
            str(config),
            "--handle",
            "@ExampleCreator",
            "--display-name",
            "Example Creator",
            "--reporter-name",
            "Example Legal",
            "--reporter-email",
            "reports@example.com",
        ],
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.handle == "examplecreator"
    assert identity.display_name == "Example Creator"
    assert identity.reporter_name == "Example Legal"
    assert identity.reporter_email == "reports@example.com"
    assert "Edit the starter identity fields" not in result.output


def test_init_guided_prompts_for_identity_fields(
    tmp_path: Path, runner: CliRunner
) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        ["init", "--guided", "--config", str(config)],
        input="@GuidedCreator\nGuided Creator\nGuided Legal\nguided@example.com\n",
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.handle == "guidedcreator"
    assert identity.display_name == "Guided Creator"
    assert identity.reporter_name == "Guided Legal"
    assert identity.reporter_email == "guided@example.com"
    assert "Edit the starter identity fields" not in result.output


def test_init_guided_accepts_default_reporter_name(
    tmp_path: Path, runner: CliRunner
) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        ["init", "--guided", "--config", str(config)],
        input="@GuidedCreator\nGuided Creator\n\nguided@example.com\n",
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.reporter_name == "Guided Creator"


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
    assert "Demo scan complete. 1 candidates queued" in scan.output

    listed = runner.invoke(app, ["list", "--config", str(config_path)])
    assert listed.exit_code == 0
    assert "@whee1ieinvestor" in listed.output

    reviewed = runner.invoke(app, ["review", "--config", str(config_path)])
    assert reviewed.exit_code == 0, reviewed.output
    assert "Pending review candidates: 1" in reviewed.output
    assert "xig review --show <id>" in reviewed.output
    assert "@whee1ieinvestor" in reviewed.output
    assert "handle is highly similar" in reviewed.output

    detail = runner.invoke(app, ["review", "--config", str(config_path), "--show", "1"])
    assert detail.exit_code == 0, detail.output
    assert "Candidate 1: @whee1ieinvestor" in detail.output
    assert "Profile: https://x.com/whee1ieinvestor" in detail.output
    assert "Reasons:" in detail.output
    assert "Top weighted signals:" in detail.output
    assert "Dry-run after approval: xig report --dry-run 1" in detail.output

    exported_json = runner.invoke(app, ["export", "json", "--config", str(config_path)])
    assert exported_json.exit_code == 0, exported_json.output
    payload = json.loads(exported_json.output)
    assert payload[0]["handle"] == "whee1ieinvestor"
    assert payload[0]["profile"]["username"] == "whee1ieinvestor"
    assert "score_breakdown" in payload[0]

    export_zip = tmp_path / "queue-export.zip"
    exported_zip = runner.invoke(
        app,
        [
            "export",
            "zip",
            "--config",
            str(config_path),
            "--output",
            str(export_zip),
        ],
    )
    assert exported_zip.exit_code == 0, exported_zip.output
    assert "Exported 1 queued candidates" in exported_zip.output
    with zipfile.ZipFile(export_zip) as archive:
        assert set(archive.namelist()) == {"queue.json", "EXPORT_MANIFEST.json"}
        queue = json.loads(archive.read("queue.json"))
        manifest = json.loads(archive.read("EXPORT_MANIFEST.json"))
    assert queue[0]["handle"] == "whee1ieinvestor"
    assert manifest["candidate_count"] == 1

    approved = runner.invoke(
        app, ["review", "--config", str(config_path), "--approve", "1"]
    )
    assert approved.exit_code == 0

    reported = runner.invoke(
        app, ["report", "--dry-run", "1", "--config", str(config_path)]
    )
    assert reported.exit_code == 0, reported.output
    assert "dry-run evidence package created" in reported.output

    history = runner.invoke(app, ["log", "--config", str(config_path)])
    assert history.exit_code == 0
    assert "dry_run" in history.output
