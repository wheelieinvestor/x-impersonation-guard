from pathlib import Path

import pytest
from typer.testing import CliRunner

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
