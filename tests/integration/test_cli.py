from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from typer.testing import CliRunner

from x_impersonation_guard.cli import app
from x_impersonation_guard.config import AppConfig, default_config_dict, load_config
from x_impersonation_guard.models import AccountProfile, CandidateSource
from x_impersonation_guard.scoring.scorer import score_candidate
from x_impersonation_guard.storage.repository import ReviewStore


def _fixture(path: Path) -> Path:
    protected = AccountProfile(
        id="1",
        username="wheelieinvestor",
        name="Wheelie Investor",
        followers_count=100_000,
        created_at=datetime(2019, 1, 1, tzinfo=UTC),
        profile_image_phash="0000000000000000",
    )
    candidate = AccountProfile(
        id="2",
        username="whee1ieinvestor",
        name="Wheelie Investor",
        followers_count=5,
        following_count=800,
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        profile_image_phash="0000000000000001",
    )
    fixture_path = path / "fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "protected": protected.model_dump(mode="json"),
                "candidates": [candidate.model_dump(mode="json")],
            }
        )
    )
    return fixture_path


def test_init_writes_config(tmp_path: Path, runner: CliRunner) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(app, ["init", "--config", str(config)])
    assert result.exit_code == 0
    assert config.exists()
    cfg = load_config(config)
    assert cfg.protected_identities[0].handle == "yourhandle"
    assert "Edit the starter identity fields" in result.output
    assert "WARNING" in result.stderr


def test_init_accepts_identity_options(tmp_path: Path, runner: CliRunner) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        [
            "init",
            "--config",
            str(config),
            "--handle",
            "@ExampleCreator",
            "--display-name",
            "Example Creator",
            "--reporter-name",
            "Example Legal",
            "--reporter-email",
            "reports@example.com",
        ],
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.handle == "examplecreator"
    assert identity.display_name == "Example Creator"
    assert identity.reporter_name == "Example Legal"
    assert identity.reporter_email == "reports@example.com"
    assert "Edit the starter identity fields" not in result.output


def test_init_guided_prompts_for_identity_fields(
    tmp_path: Path, runner: CliRunner
) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        ["init", "--guided", "--config", str(config)],
        input="@GuidedCreator\nGuided Creator\nGuided Legal\nguided@example.com\n",
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.handle == "guidedcreator"
    assert identity.display_name == "Guided Creator"
    assert identity.reporter_name == "Guided Legal"
    assert identity.reporter_email == "guided@example.com"
    assert "Edit the starter identity fields" not in result.output


def test_init_guided_accepts_default_reporter_name(
    tmp_path: Path, runner: CliRunner
) -> None:
    config = tmp_path / "config.yaml"
    result = runner.invoke(
        app,
        ["init", "--guided", "--config", str(config)],
        input="@GuidedCreator\nGuided Creator\n\nguided@example.com\n",
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(config)
    identity = cfg.protected_identities[0]
    assert identity.reporter_name == "Guided Creator"


def test_calibrate_reports_precision_and_recall(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "calibrate",
            "--config",
            "examples/config.individual.yaml",
            "--input",
            "examples/calibration.sample.json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Calibration candidates: 4" in result.output
    assert "precision=1.00" in result.output
    assert "recall=1.00" in result.output
    assert "tp=2 fp=0 tn=2 fn=0" in result.output
    assert "No calibration misses." in result.output


def test_calibrate_writes_json_evidence(tmp_path: Path, runner: CliRunner) -> None:
    output = tmp_path / "validation" / "calibration-results.json"
    result = runner.invoke(
        app,
        [
            "calibrate",
            "--config",
            "examples/config.individual.yaml",
            "--input",
            "examples/calibration.sample.json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"Calibration evidence written to {output}" in result.output
    payload = json.loads(output.read_text())
    assert payload["threshold"] == 70
    assert payload["candidate_count"] == 4
    assert payload["identity_handle"] == "examplecreator"
    assert payload["metrics"] == {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "true_positive": 2,
        "false_positive": 0,
        "true_negative": 2,
        "false_negative": 0,
    }
    assert payload["misses"] == []
    assert payload["candidates"][0]["profile_url"].startswith("https://x.com/")
    assert "signals" in payload["candidates"][0]


def test_scan_fixture_lists_and_dry_run_report(
    tmp_path: Path,
    config_path: Path,
    runner: CliRunner,
) -> None:
    fixture = _fixture(tmp_path)
    scan = runner.invoke(
        app,
        ["scan-fixture", "--config", str(config_path), "--input", str(fixture)],
    )
    assert scan.exit_code == 0, scan.output
    assert "Demo scan complete. 1 candidates queued" in scan.output

    listed = runner.invoke(app, ["list", "--config", str(config_path)])
    assert listed.exit_code == 0
    assert "@whee1ieinvestor" in listed.output
    status = runner.invoke(app, ["status", "--config", str(config_path)])
    assert status.exit_code == 0, status.output
    assert "pending=1" in status.output
    assert "snoozed=0" in status.output

    reviewed = runner.invoke(app, ["review", "--config", str(config_path)])
    assert reviewed.exit_code == 0, reviewed.output
    assert "Pending review candidates: 1" in reviewed.output
    assert "xig review --show <id>" in reviewed.output
    assert "@whee1ieinvestor" in reviewed.output
    assert "handle is highly similar" in reviewed.output

    next_detail = runner.invoke(app, ["review", "--config", str(config_path), "--next"])
    assert next_detail.exit_code == 0, next_detail.output
    assert "Candidate 1: @whee1ieinvestor" in next_detail.output
    assert "Next steps:" in next_detail.output

    detail = runner.invoke(app, ["review", "--config", str(config_path), "--show", "1"])
    assert detail.exit_code == 0, detail.output
    assert "Candidate 1: @whee1ieinvestor" in detail.output
    assert "Profile: https://x.com/whee1ieinvestor" in detail.output
    assert "Reasons:" in detail.output
    assert "Top weighted signals:" in detail.output
    assert "Snooze: xig review --snooze 1" in detail.output
    assert "Dry-run after approval: xig report --dry-run 1" in detail.output

    exported_json = runner.invoke(app, ["export", "json", "--config", str(config_path)])
    assert exported_json.exit_code == 0, exported_json.output
    payload = json.loads(exported_json.output)
    assert payload[0]["handle"] == "whee1ieinvestor"
    assert payload[0]["profile"]["username"] == "whee1ieinvestor"
    assert "score_breakdown" in payload[0]

    export_zip = tmp_path / "queue-export.zip"
    exported_zip = runner.invoke(
        app,
        [
            "export",
            "zip",
            "--config",
            str(config_path),
            "--output",
            str(export_zip),
        ],
    )
    assert exported_zip.exit_code == 0, exported_zip.output
    assert "Exported 1 queued candidates" in exported_zip.output
    with zipfile.ZipFile(export_zip) as archive:
        assert set(archive.namelist()) == {"queue.json", "EXPORT_MANIFEST.json"}
        queue = json.loads(archive.read("queue.json"))
        manifest = json.loads(archive.read("EXPORT_MANIFEST.json"))
    assert queue[0]["handle"] == "whee1ieinvestor"
    assert manifest["candidate_count"] == 1

    snoozed = runner.invoke(
        app, ["review", "--config", str(config_path), "--snooze", "1"]
    )
    assert snoozed.exit_code == 0, snoozed.output
    assert "Snoozed candidate 1" in snoozed.output
    status_after_snooze = runner.invoke(app, ["status", "--config", str(config_path)])
    assert status_after_snooze.exit_code == 0, status_after_snooze.output
    assert "pending=0" in status_after_snooze.output
    assert "snoozed=1" in status_after_snooze.output
    listed_after_snooze = runner.invoke(app, ["list", "--config", str(config_path)])
    assert listed_after_snooze.exit_code == 0, listed_after_snooze.output
    assert "No pending candidates." in listed_after_snooze.output
    next_after_snooze = runner.invoke(
        app, ["review", "--config", str(config_path), "--next"]
    )
    assert next_after_snooze.exit_code == 0, next_after_snooze.output
    assert "No pending candidates." in next_after_snooze.output
    listed_snoozed = runner.invoke(
        app, ["list", "--config", str(config_path), "--status", "snoozed"]
    )
    assert listed_snoozed.exit_code == 0, listed_snoozed.output
    assert "@whee1ieinvestor" in listed_snoozed.output
    assert "status=snoozed" in listed_snoozed.output
    listed_all = runner.invoke(
        app, ["list", "--config", str(config_path), "--status", "all"]
    )
    assert listed_all.exit_code == 0, listed_all.output
    assert "status=snoozed" in listed_all.output
    restored = runner.invoke(
        app, ["review", "--config", str(config_path), "--restore", "1"]
    )
    assert restored.exit_code == 0, restored.output
    assert "Restored candidate 1 to pending" in restored.output

    approved = runner.invoke(
        app, ["review", "--config", str(config_path), "--approve", "1"]
    )
    assert approved.exit_code == 0, approved.output
    assert "Dry-run report: xig report --dry-run 1" in approved.output
    assert (
        "Live report after inspecting dry-run evidence: xig report --execute --confirm-live 1"
        in approved.output
    )
    status_after_approval = runner.invoke(app, ["status", "--config", str(config_path)])
    assert status_after_approval.exit_code == 0, status_after_approval.output
    assert "approved=1" in status_after_approval.output

    live_without_confirm = runner.invoke(
        app,
        ["report", "--execute", "1", "--config", str(config_path)],
        color=False,
    )
    assert live_without_confirm.exit_code != 0

    reported = runner.invoke(
        app, ["report", "--dry-run", "1", "--config", str(config_path)]
    )
    assert reported.exit_code == 0, reported.output
    assert "dry-run evidence package created" in reported.output
    assert (
        "Live report after inspecting evidence: xig report --execute --confirm-live 1"
        in reported.output
    )

    history = runner.invoke(app, ["log", "--config", str(config_path)])
    assert history.exit_code == 0
    assert "dry_run" in history.output


def test_identity_filter_guards_review_and_report_actions(
    tmp_path: Path, runner: CliRunner
) -> None:
    raw = default_config_dict(
        handle="firstcreator",
        display_name="First Creator",
        reporter_name="First Creator",
        reporter_email="first@example.com",
    )
    raw["protected_identities"].append(
        default_config_dict(
            handle="secondcreator",
            display_name="Second Creator",
            reporter_name="Second Creator",
            reporter_email="second@example.com",
        )["protected_identities"][0]
    )
    raw["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    raw["storage"]["evidence_dir"] = str(tmp_path / "evidence")
    raw["storage"]["reports_dir"] = str(tmp_path / "reports")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False))
    cfg = AppConfig.model_validate(raw)
    store = ReviewStore(cfg.storage.db_path)
    protected = AccountProfile(
        id="first",
        username="firstcreator",
        name="First Creator",
        followers_count=50_000,
    )
    candidate = AccountProfile(
        id="candidate-first",
        username="firstcreator_help",
        name="First Creator",
        followers_count=5,
        following_count=800,
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    result = score_candidate(
        protected, candidate, cfg.protected_identities[0], cfg.scoring
    )
    candidate_id = store.upsert_scored_candidate(
        "firstcreator", CandidateSource.FIXTURE, result
    )
    assert candidate_id is not None

    wrong_identity = runner.invoke(
        app,
        [
            "review",
            "--config",
            str(config),
            "--identity",
            "secondcreator",
            "--approve",
            str(candidate_id),
        ],
    )
    assert wrong_identity.exit_code != 0
    assert "does not belong to @secondcreator" in wrong_identity.output

    wrong_report_identity = runner.invoke(
        app,
        [
            "report",
            "--dry-run",
            "--config",
            str(config),
            "--identity",
            "secondcreator",
            str(candidate_id),
        ],
    )
    assert wrong_report_identity.exit_code != 0
    assert "does not belong to @secondcreator" in wrong_report_identity.output

    right_identity = runner.invoke(
        app,
        [
            "review",
            "--config",
            str(config),
            "--identity",
            "firstcreator",
            "--dismiss",
            str(candidate_id),
        ],
    )
    assert right_identity.exit_code == 0, right_identity.output
    assert f"Dismissed candidate {candidate_id}" in right_identity.output
