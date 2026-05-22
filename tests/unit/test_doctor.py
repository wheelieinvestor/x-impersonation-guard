from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from x_impersonation_guard.cli import app
from x_impersonation_guard.config import default_config_dict


def test_doctor_allows_missing_config_with_setup_guidance(
    tmp_path: Path, runner: CliRunner
) -> None:
    result = runner.invoke(app, ["doctor", "--config", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 0
    assert "WARN: config:" in result.output
    assert "xig scan-fixture" in result.output


def test_doctor_checks_valid_config(config_path: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "OK: config:" in result.output
    assert "OK: scan mode:" in result.output
    assert "OK: sqlite:" in result.output
    assert "X_API_BEARER_TOKEN is not set" in result.output


def test_doctor_fails_for_forced_api_without_token(
    tmp_path: Path, runner: CliRunner
) -> None:
    raw = default_config_dict()
    raw["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    raw["storage"]["evidence_dir"] = str(tmp_path / "evidence")
    raw["storage"]["reports_dir"] = str(tmp_path / "reports")
    raw["x_api"]["mode"] = "api"
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False))

    result = runner.invoke(app, ["doctor", "--config", str(config)])

    assert result.exit_code == 1
    assert "FAIL: scan mode:" in result.output
    assert "X_API_BEARER_TOKEN is required" in result.output
