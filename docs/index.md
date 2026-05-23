# x-impersonation-guard

![x-impersonation-guard demo](demo/hero.gif)

Detect and report X accounts impersonating you. Local-first, explainable, safe by default.

## Try it in 60 seconds

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig quickstart
xig scan-fixture
xig doctor
xig review
```

The offline demo runs against fictional `@alex_charts` candidates and never touches the real X.

## Why it exists

Creators get cloned constantly. Impersonators DM followers, run scams, and erode trust. Manual reporting is repetitive and leaves no local audit trail.

`x-impersonation-guard` keeps detection, review, and reporting local:

- Multi-signal scoring for likely impersonators.
- SQLite review queue with explainable signal breakdowns and `xig review --show <id>` evidence details.
- JSON and zip queue exports for handoff, audit, or local analysis.
- `xig doctor` setup checks for Python, Playwright, Chromium, config, starter identity fields, storage, token state, and SQLite.
- Dry-run evidence packages before live submission.
- Playwright Help Center reporter that fails closed when selectors drift.
- Offline scorer calibration with precision, recall, F1, miss reporting, and optional JSON evidence.

## Status

Current public alpha: `v0.2.0-alpha`.

Offline demo, PyPI install, first-run config generation, and dependency security posture are verified. Live X API scans and live report submission are pending controlled live validation.

[Read the status matrix](status.md)

[Follow the live validation runbook](live-validation.md)
