from __future__ import annotations

import json
import re
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
