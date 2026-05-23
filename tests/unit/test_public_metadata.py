from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

from x_impersonation_guard.config import AppConfig


def test_package_metadata_is_public_launch_ready() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]

    assert project["name"] == "x-impersonation-guard"
    assert "impersonation" in project["keywords"]
    assert "security" in project["keywords"]
    assert "creator-tools" in project["keywords"]
    assert "Topic :: Security" in project["classifiers"]
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert Path("src/x_impersonation_guard/py.typed").exists()

    urls = project["urls"]
    assert urls["Documentation"].startswith("https://")
    assert urls["Issues"].endswith("/issues")
    assert urls["Source"].endswith("/x-impersonation-guard")


def test_launch_copy_has_no_internal_placeholders() -> None:
    launch_text = "\n".join(
        path.read_text() for path in sorted(Path("launch").glob("*.md"))
    )

    assert "Dean will fill in" not in launch_text
    assert "replace this" not in launch_text
    assert "TBD" not in launch_text


def test_example_configs_are_generic_and_valid() -> None:
    examples = sorted(Path("examples").glob("config.*.yaml"))
    assert examples

    combined = "\n".join(path.read_text() for path in examples)
    assert "Dean Ahrens" not in combined
    assert "dean@" not in combined
    assert "wheelieinvestor" not in combined
    assert "wheelhousecapital.com" not in combined

    for path in examples:
        raw = yaml.safe_load(path.read_text())
        cfg = AppConfig.model_validate(raw)
        assert cfg.protected_identities
        for identity in cfg.protected_identities:
            assert identity.handle.startswith("example")
            assert identity.reporter_email.endswith("@example.com")


def test_status_docs_do_not_reference_stale_phase_gate() -> None:
    status = Path("docs/status.md").read_text()
    index = Path("docs/index.md").read_text()
    readme = Path("README.md").read_text()

    assert "Phase 2 starts after" not in status
    assert "pending Phase 2 validation" not in index
    assert "pending Phase 2 validation" not in readme
    assert "controlled live validation" in status


def test_changelog_tracks_post_alpha_hardening() -> None:
    changelog = Path("CHANGELOG.md").read_text()

    assert "## [Unreleased]" in changelog
    assert "Review queue snooze and restore workflow" in changelog
    assert "Estimated X API scan cost guard" in changelog
    assert "Cached image-hash lookup in the default scan path" in changelog
    assert "Offline scorer calibration command" in changelog
    assert "JSON calibration evidence export" in changelog
    assert "Controlled live-validation runbook" in changelog
    assert "`xig quickstart` onboarding command" in changelog
    assert "Broader `xig redact-report` secret scrubbing" in changelog
    assert "`--confirm-live`" in changelog


def test_live_validation_runbook_is_publicly_linked() -> None:
    readme = Path("README.md").read_text()
    index = Path("docs/index.md").read_text()
    status = Path("docs/status.md").read_text()
    mkdocs = Path("docs/site/mkdocs.yml").read_text()
    runbook = Path("docs/live-validation.md").read_text()
    issue_template = Path(".github/ISSUE_TEMPLATE/live_validation.yml").read_text()

    assert "docs/live-validation.md" in readme
    assert "live-validation.md" in index
    assert "live-validation.md" in status
    assert "Live validation: live-validation.md" in mkdocs
    assert "Do not paste X API tokens" in runbook
    assert "xig calibrate" in runbook
    assert "xig report" in runbook
    assert "API tokens, cookies, browser profiles" in issue_template
