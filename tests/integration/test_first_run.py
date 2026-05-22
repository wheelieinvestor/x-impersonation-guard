from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from x_impersonation_guard import __version__
from x_impersonation_guard.cli import app
from x_impersonation_guard.config import default_config_dict


def test_first_run_without_config_prints_helpful_message(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "It looks like this is your first run" in result.output
    assert "xig scan-fixture" in result.output
    assert "xig init" in result.output


def test_quickstart_without_config_prints_demo_and_setup_paths(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["quickstart"])

    assert result.exit_code == 0, result.output
    assert "Safe offline demo:" in result.output
    assert "xig scan-fixture" in result.output
    assert "xig report --dry-run 1" in result.output
    assert "No config found" in result.output
    assert "xig init --guided" in result.output
    assert "--execute --confirm-live" in result.output
    assert not Path("config.yaml").exists()


def test_quickstart_with_config_prints_real_next_steps(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("config.yaml").write_text(yaml.safe_dump(default_config_dict()))

    result = runner.invoke(app, ["quickstart"])

    assert result.exit_code == 0, result.output
    assert "Config found at config.yaml: 1 protected identity" in result.output
    assert "WARN:" in result.output
    assert "X_API_BEARER_TOKEN: not set" in result.output
    assert "xig doctor --config config.yaml" in result.output
    assert "xig report --config config.yaml --dry-run <candidate_id>" in result.output
    assert "docs/live-validation.md" in result.output


def test_no_command_with_config_prints_command_help(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("config.yaml").write_text("protected_identities: []")
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "scan-fixture" in result.output
    assert "first run" not in result.output


def test_version_flag_works_without_config(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"x-impersonation-guard {__version__}" in result.output
    assert "first run" not in result.output
