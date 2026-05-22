from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from x_impersonation_guard.config import AppConfig, default_config_dict, load_config


def test_default_config_is_valid() -> None:
    cfg = AppConfig.model_validate(default_config_dict())
    assert cfg.protected_identities[0].handle == "wheelieinvestor"
    assert cfg.reporting.auto_submit is False


def test_reporting_cap_cannot_exceed_twenty() -> None:
    raw = default_config_dict()
    raw["reporting"]["max_reports_per_24h"] = 21
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_weights_must_sum_to_100() -> None:
    raw = default_config_dict()
    raw["scoring"]["weights"]["handle_similarity"] = 21
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_load_config_expands_storage_paths(tmp_path: Path) -> None:
    raw = default_config_dict()
    raw["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    path = tmp_path / "config.yaml"
    import yaml

    path.write_text(yaml.safe_dump(raw))
    cfg = load_config(path)
    assert cfg.storage.db_path == tmp_path / "db.sqlite"
