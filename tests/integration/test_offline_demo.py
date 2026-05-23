from __future__ import annotations

import json
import re
import zipfile
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
    assert "xig redact-report" in report.output
    assert (
        f"Approve before live submission: xig review --config {config} --approve {first_id}"
        in report.output
    )
    report_dir_match = re.search(
        r"dry-run evidence package created: (/.*)$", report.output, re.MULTILINE
    )
    assert report_dir_match is not None
    report_dir = Path(report_dir_match.group(1))
    assert (report_dir / "evidence_profile.png").exists()
    assert (report_dir / "evidence_profile.html").exists()
    assert (report_dir / "score_breakdown.json").exists()
    assert (report_dir / "form_submission.png").exists()
    assert (report_dir / "form_response.html").exists()
    assert (report_dir / "report.json").exists()
    (report_dir / "failure_diagnostic.json").write_text(
        json.dumps(
            {
                "Authorization": "Bearer live-token-value",
                "session_cookie": "auth_token=abc123",
                "nested": {
                    "csrfToken": "csrf-secret",
                    "message": "token=abc123 email=dean@example.com https://x.com/alex_charts",
                },
            }
        )
    )
    (report_dir / "failure.log").write_text(
        "authorization: Bearer live-token-value\n"
        "cookie=sessionid=abc123\n"
        "contact dean@example.com at https://x.com/alex_charts\n"
    )

    bundle = tmp_path / "redacted-report.zip"
    redacted = runner.invoke(
        app,
        [
            "redact-report",
            str(report_dir),
            "--output",
            str(bundle),
        ],
    )
    assert redacted.exit_code == 0, redacted.output
    assert "Created redacted report bundle" in redacted.output
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "report.json" in names
        assert "score_breakdown.json" in names
        assert "failure_diagnostic.json" in names
        assert "failure.log" in names
        assert "REDACTION_MANIFEST.json" in names
        assert "evidence_profile.html" not in names
        assert "evidence_profile.png" not in names
        report_json = archive.read("report.json").decode()
        diagnostic_json = archive.read("failure_diagnostic.json").decode()
        failure_log = archive.read("failure.log").decode()
        manifest = json.loads(archive.read("REDACTION_MANIFEST.json"))

    assert "demo@example.com" not in report_json
    assert "alex_charts" not in report_json.lower()
    assert '"reporter_email": "<redacted>"' in report_json
    assert "live-token-value" not in diagnostic_json
    assert "auth_token" not in diagnostic_json
    assert "csrf-secret" not in diagnostic_json
    assert "abc123" not in diagnostic_json
    assert "dean@example.com" not in diagnostic_json
    assert "alex_charts" not in diagnostic_json.lower()
    assert "live-token-value" not in failure_log
    assert "abc123" not in failure_log
    assert "dean@example.com" not in failure_log
    assert "alex_charts" not in failure_log.lower()
    assert "evidence_profile.html" in manifest["excluded"]
    assert "failure.log" in manifest["redacted"]


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
