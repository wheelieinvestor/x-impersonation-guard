from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from x_impersonation_guard.config import default_config_dict


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    raw = default_config_dict(
        handle="wheelieinvestor",
        display_name="Wheelie Investor",
        reporter_name="Dean Ahrens",
        reporter_email="dean@example.com",
    )
    raw["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    raw["storage"]["evidence_dir"] = str(tmp_path / "evidence")
    raw["storage"]["reports_dir"] = str(tmp_path / "reports")
    path = tmp_path / "config.yaml"
    import yaml

    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path
