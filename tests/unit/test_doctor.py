from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import x_impersonation_guard.cli as cli
from x_impersonation_guard.cli import app
from x_impersonation_guard.config import default_config_dict


def test_doctor_allows_missing_config_with_setup_guidance(
    tmp_path: Path, runner: CliRunner
) -> None:
    result = runner.invoke(app, ["doctor", "--config", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 0
    assert "WARN: config:" in result.output
    assert "xig scan-fixture" in result.output


def test_doctor_checks_valid_config(
    config_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_chromium_executable_path", lambda: config_path)
    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "OK: config:" in result.output
    assert "OK: scan mode:" in result.output
    assert "OK: chromium:" in result.output
    assert "OK: sqlite:" in result.output
    assert "X_API_BEARER_TOKEN is not set" in result.output


def test_doctor_json_reports_setup_without_secret_values(
    config_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_chromium_executable_path", lambda: config_path)
    monkeypatch.setenv("X_API_BEARER_TOKEN", "secret-token-value")

    result = runner.invoke(app, ["doctor", "--config", str(config_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["config"] == str(config_path)
    assert "secret-token-value" not in result.output
    checks = {(check["label"], check["state"]): check for check in payload["checks"]}
    assert ("config", "OK") in checks
    assert ("scan mode", "OK") in checks
    assert ("sqlite", "OK") in checks
    assert checks[("x api token", "OK")]["detail"] == "X_API_BEARER_TOKEN is set"


def test_doctor_json_allows_missing_config_with_setup_guidance(
    tmp_path: Path, runner: CliRunner
) -> None:
    missing = tmp_path / "missing.yaml"

    result = runner.invoke(app, ["doctor", "--config", str(missing), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["config"] == str(missing)
    assert payload["checks"][-1]["state"] == "WARN"
    assert payload["checks"][-1]["label"] == "config"
    assert "xig init" in payload["checks"][-1]["detail"]


def test_support_bundle_writes_privacy_safe_diagnostics(
    config_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "_chromium_executable_path", lambda: config_path)
    monkeypatch.setenv("X_API_BEARER_TOKEN", "secret-token-value")
    bundle = tmp_path / "support" / "xig-support.zip"

    result = runner.invoke(
        app, ["support-bundle", "--config", str(config_path), "--output", str(bundle)]
    )

    assert result.exit_code == 0, result.output
    assert f"Support bundle written to {bundle}" in result.output
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert names == {
            "SUPPORT_README.md",
            "doctor.json",
            "status.json",
            "MANIFEST.json",
        }
        doctor = json.loads(archive.read("doctor.json"))
        status = json.loads(archive.read("status.json"))
        manifest = json.loads(archive.read("MANIFEST.json"))
        combined = "\n".join(
            archive.read(name).decode("utf-8") for name in sorted(names)
        )
    assert doctor["ok"] is True
    assert status["identities"][0]["handle"] == "wheelieinvestor"
    assert status["identities"][0]["reports_24h"] == 0
    assert manifest["doctor_ok"] is True
    assert "status.json" in manifest["files"]
    assert "secret-token-value" not in combined
    assert "config files" in combined
    assert "xig redact-report <report_dir>" in combined

    duplicate = runner.invoke(app, ["support-bundle", "--output", str(bundle)])
    assert duplicate.exit_code != 0
    assert "already exists; pass --force" in duplicate.output


def test_doctor_warns_when_chromium_is_missing(
    config_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_chromium_executable_path", lambda: None)
    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "WARN: chromium:" in result.output
    assert "playwright install chromium" in result.output


def test_doctor_warns_for_starter_identity_values(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = default_config_dict()
    raw["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    raw["storage"]["evidence_dir"] = str(tmp_path / "evidence")
    raw["storage"]["reports_dir"] = str(tmp_path / "reports")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False))
    monkeypatch.setattr(cli, "_chromium_executable_path", lambda: config)

    result = runner.invoke(app, ["doctor", "--config", str(config)])

    assert result.exit_code == 0, result.output
    assert "WARN: identity:" in result.output
    assert "starter values" in result.output
    assert "handle, display_name, reporter_name, reporter_email" in result.output
    assert "xig init --guided" in result.output


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
