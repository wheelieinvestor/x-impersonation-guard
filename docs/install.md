# Install

## Offline demo

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig quickstart
xig demo
xig scan-fixture
xig config
xig doctor
xig list
xig report --dry-run 1
```

Fixture mode does not call the live X API and does not submit reports. `xig demo` keeps demo config, queue, evidence, and reports inside `.xig-demo/`; use `xig demo --reset` for a clean repeatable demo.

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
xig config
xig status
xig status --json
xig review
xig review --next
xig review --show 1
xig list --status snoozed
xig export zip --output queue-export.zip
xig validation-template
xig report --dry-run 1
```

Use `xig config` or `xig config --json` to inspect the active config without printing reporter emails or token values. Use `xig status` to see queue counts by status and 24-hour reporting usage, or `xig status --json` to save the same data for scripts and validation records. Use `xig review --next` to inspect the highest-priority pending candidate without copying an ID, or `xig review --show <id>` to inspect a specific account. Use `xig review --snooze <id>` or the TUI `s` key to defer gray-area candidates, `xig list --status snoozed` to find deferred candidates, and `xig review --restore <id>` to move one back to pending. Use `xig list --status all` for a full local queue view. Use `xig export json` or `xig export zip --output queue-export.zip` to save a portable copy of the pending review queue. Use `xig validation-template` to write a public-safe checklist before controlled live validation. If you configure more than one protected identity, pass `--identity <handle>` to review and report commands to guard against acting on the wrong candidate. Approval and dry-run commands print the next safe reporting command, preserving config and identity flags where needed. Live submission requires an approved candidate plus `--execute --confirm-live`.

## Setup check

`xig quickstart` is the safest orientation command for new users. With no config, it prints the offline demo path and real-account setup commands. With a config, it shows the next scan, status, review, and dry-run commands without making network calls or submitting reports. For multi-identity configs, it prints scoped commands with `--identity <handle>` so you can repeat the sequence for each protected account.

`xig doctor` is safe to run before or after creating `config.yaml`. It verifies:

- Python 3.11 or newer.
- Playwright package availability and Chromium browser installation.
- Config validity when a config file exists.
- Starter identity placeholders that should be replaced before live scans.
- Selected scan mode and whether the configured X API token environment variable is set.
- Storage directory writability.
- SQLite review queue access.

It never prints token values. Use `xig doctor --json` to save the same privacy-safe diagnostics for support issues, scripts, or live-validation records. Use `xig support-bundle --output xig-support.zip` to create a small public-safe diagnostic zip with `doctor.json`, `status.json`, and a manifest. It excludes config files, tokens, cookies, browser profiles, screenshots, raw report packages, and private evidence.

## Troubleshooting

- If `xig` is not found, confirm your Python scripts directory is on `PATH`.
- If you need to confirm the installed package version, run `xig --version`.
- If Playwright browser install fails, rerun `playwright install chromium`.
- If no candidates appear in fixture mode, rerun the isolated demo with `xig demo --reset`.
