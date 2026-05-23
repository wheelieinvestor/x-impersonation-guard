from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from x_impersonation_guard.cli import DemoFixture, app
from x_impersonation_guard.config import AppConfig, default_config_dict
from x_impersonation_guard.scoring.scorer import score_candidate


def test_offline_demo_scan_list_and_dry_run_report(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config = tmp_path / "demo-config.yaml"

    scan = runner.invoke(app, ["scan-fixture", "--config", str(config)])
    assert scan.exit_code == 0, scan.output
    assert "Demo scan complete." in scan.output
    assert "3 high, 2 medium" in scan.output

    listed = runner.invoke(app, ["list", "--config", str(config)])
    assert listed.exit_code == 0, listed.output
    assert "@alex_charts1" in listed.output
    assert "@aIex_charts" in listed.output
    assert "@alex_chartss" in listed.output
    assert "priority=critical" in listed.output
    assert "priority=medium" in listed.output
    assert "detected=1h" in listed.output
    assert "detected=14h" in listed.output

    first_id_match = re.search(r"^(\d+):", listed.output, re.MULTILINE)
    assert first_id_match is not None
    first_id = first_id_match.group(1)

    report = runner.invoke(
        app, ["report", "--dry-run", first_id, "--config", str(config)]
    )
    assert report.exit_code == 0, report.output
    assert "dry-run evidence package created" in report.output
    report_dir_match = re.search(r"(/.*)$", report.output.strip())
    assert report_dir_match is not None
    report_dir = Path(report_dir_match.group(1))
    assert (report_dir / "evidence_profile.png").exists()
    assert (report_dir / "evidence_profile.html").exists()
    assert (report_dir / "score_breakdown.json").exists()
    assert (report_dir / "form_submission.png").exists()
    assert (report_dir / "form_response.html").exists()
    assert (report_dir / "report.json").exists()

    exported = runner.invoke(
        app,
        [
            "export-report",
            first_id,
            "--config",
            str(config),
            "--output",
            str(tmp_path / "report.zip"),
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert "exported report package" in exported.output
    with zipfile.ZipFile(tmp_path / "report.zip") as archive:
        assert "report.json" in archive.namelist()


def test_list_json_and_since_filter(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config = tmp_path / "demo-config.yaml"

    scan = runner.invoke(app, ["scan-fixture", "--config", str(config)])
    assert scan.exit_code == 0, scan.output

    listed = runner.invoke(app, ["list", "--config", str(config), "--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert payload[0]["handle"] == "alex_charts1"
    assert payload[0]["priority"] == "critical"
    assert payload[0]["status"] == "pending"
    assert "detected_at" in payload[0]

    recent = runner.invoke(
        app, ["list", "--config", str(config), "--since", "2h", "--json"]
    )
    assert recent.exit_code == 0, recent.output
    recent_payload = json.loads(recent.output)
    assert [item["handle"] for item in recent_payload] == ["alex_charts1"]

    iso = runner.invoke(
        app, ["list", "--config", str(config), "--since", "2026-01-01", "--json"]
    )
    assert iso.exit_code == 0, iso.output
    assert len(json.loads(iso.output)) == 5

    invalid = runner.invoke(app, ["list", "--config", str(config), "--since", "soon"])
    assert invalid.exit_code != 0
    assert "expected ISO date/time or relative value" in invalid.output


def test_list_json_empty_queue(config_path: Path, runner: CliRunner) -> None:
    listed = runner.invoke(app, ["list", "--config", str(config_path), "--json"])
    assert listed.exit_code == 0
    assert json.loads(listed.output) == []


def test_export_report_missing_id(config_path: Path, runner: CliRunner) -> None:
    exported = runner.invoke(
        app, ["export-report", "missing", "--config", str(config_path)]
    )
    assert exported.exit_code != 0
    assert "report not found" in exported.output


def test_demo_fixture_scores_match_story() -> None:
    raw = json.loads(Path("examples/demo_fixture.json").read_text())
    demo = DemoFixture.model_validate(raw)
    scan = demo.to_fixture_scan()
    cfg = AppConfig.model_validate(default_config_dict())
    identity = cfg.protected_identities[0].model_copy(
        update={
            "handle": scan.protected.username,
            "display_name": scan.protected.name,
        }
    )

    scored = {
        result.candidate.username: result
        for result in [
            score_candidate(scan.protected, candidate, identity, cfg.scoring)
            for candidate in scan.candidates
        ]
    }
    for candidate in demo.demo_candidates:
        low, high = candidate.expected_score_range
        assert low <= scored[candidate.handle].score <= high
        if candidate.expected_tier == "filtered":
            assert scored[candidate.handle].priority is None
        else:
            assert scored[candidate.handle].priority is not None
