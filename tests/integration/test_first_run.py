from pathlib import Path

import pytest
from typer.testing import CliRunner

from x_impersonation_guard import __version__
from x_impersonation_guard.cli import app


def test_first_run_without_config_prints_helpful_message(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "It looks like this is your first run" in result.output
    assert "xig scan-fixture" in result.output
    assert "xig init" in result.output


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


def test_version_command_prints_runtime_details(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"x-impersonation-guard {__version__}" in result.output
    assert "python " in result.output
    assert "platform " in result.output
    assert "playwright " in result.output
    assert "first run" not in result.output
