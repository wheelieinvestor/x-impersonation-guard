# Install

## Offline demo

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig scan-fixture
xig doctor
xig list
xig report --dry-run 1
```

Fixture mode does not call the live X API and does not submit reports.

## Real account setup

```bash
export X_API_BEARER_TOKEN="your_token_here"
xig init \
  --handle yourhandle \
  --display-name "Your Name" \
  --reporter-name "Your Legal Name" \
  --reporter-email you@example.com
```

If you skip those identity options, `xig init` writes a generic starter config and tells you which fields to edit before live use. Use `xig init --guided` if you prefer prompts.

Then run:

```bash
xig doctor
xig scan
xig status
xig review
xig review --show 1
xig list --status snoozed
xig export zip --output queue-export.zip
xig report --dry-run 1
```

Use `xig status` to see queue counts by status and 24-hour reporting usage. Use `xig review --show <id>` to inspect score reasons, mitigations, profile metadata, and the next safe commands. Use `xig review --snooze <id>` or the TUI `s` key to defer gray-area candidates, `xig list --status snoozed` to find deferred candidates, and `xig review --restore <id>` to move one back to pending. Use `xig list --status all` for a full local queue view. Use `xig export json` or `xig export zip --output queue-export.zip` to save a portable copy of the pending review queue. If you configure more than one protected identity, pass `--identity <handle>` to review and report commands to guard against acting on the wrong candidate. Live submission requires an approved candidate plus `--execute --confirm-live`.

## Setup check

`xig doctor` is safe to run before or after creating `config.yaml`. It verifies:

- Python 3.11 or newer.
- Playwright package availability and Chromium browser installation.
- Config validity when a config file exists.
- Starter identity placeholders that should be replaced before live scans.
- Selected scan mode and whether the configured X API token environment variable is set.
- Storage directory writability.
- SQLite review queue access.

It never prints token values.

## Troubleshooting

- If `xig` is not found, confirm your Python scripts directory is on `PATH`.
- If you need to confirm the installed package version, run `xig --version`.
- If Playwright browser install fails, rerun `playwright install chromium`.
- If no candidates appear in fixture mode, remove the demo database at `~/.x-impersonation-guard/db.sqlite` and rerun `xig scan-fixture`.
