# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project uses prerelease alpha tags while live validation is in progress.

## [Unreleased]

### Added

- Guided setup prompts and starter-config warnings for safer first runs.
- `xig doctor` checks for Playwright Chromium, starter identity placeholders, token presence, storage access, and SQLite queue access.
- `xig review --show <id>` evidence details with score reasons, mitigations, weighted signals, profile metadata, and next safe commands.
- Review queue snooze and restore workflow in both CLI and Textual TUI.
- `xig list --status ...` and `xig status` queue visibility for pending, snoozed, approved, dismissed, reported, and failed candidates.
- JSON and zip queue exports with manifests for handoff and local analysis.
- Redacted diagnostic report bundles for safer public issue reports.
- Estimated X API scan cost guard with configurable per-request estimate.
- Cached image-hash lookup in the default scan path.
- Offline scorer calibration command with precision, recall, F1, and miss reporting.
- JSON calibration evidence export for comparing scorer validation runs.

### Changed

- Live Help Center submissions now require both `--execute` and `--confirm-live`.
- Multi-identity review and report actions fail closed when `--identity` does not own the candidate.
- Dry-run report output points users toward redacted report bundles before sharing diagnostics.

### Verified

- Local CLI, docs, lint, mypy, and test gates cover the added review, export, redaction, queue status, cost guard, and cached image lookup workflows.
- GitHub Actions `docs`, `lint`, and `test` checks pass on `main` after each merged hardening PR.

## [0.2.0-alpha] - 2026-05-22

### Added

- Typer CLI with `xig` entry point.
- Offline fixture scan and dry-run evidence package flow.
- SQLite review queue.
- Mode selector for API, scrape, and auto scan modes.
- Fail-closed Playwright Help Center reporter checks.
- Public alpha README, demo assets, issue templates, and CI.
- PyPI prerelease package `x-impersonation-guard==0.2.0a0`.
- PyPI-facing project URLs, classifiers, keywords, and typed-package marker.

### Verified

- PyPI install on Linux Python 3.11.
- PyPI install on Linux Python 3.12.
- PyPI install on macOS Python 3.11.
- Offline demo from scan to dry-run report package.

## [0.1.0-alpha] - 2026-05-22

### Added

- Initial MVP scaffold.
- Account profile model.
- Basic impersonation scoring.
- Early reporting and review flow prototypes.
