from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from x_impersonation_guard.cli import app


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
    assert "3 high, 1 medium" in scan.output

    listed = runner.invoke(app, ["list", "--config", str(config)])
    assert listed.exit_code == 0, listed.output
    assert "priority=critical" in listed.output
    assert "priority=medium" in listed.output

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
