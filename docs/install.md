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
xig init
```

Edit `config.yaml` with your handle, display name, reporter name, and reporter email.

Then run:

```bash
xig doctor
xig scan
xig review
xig report --dry-run 1
```

Live submission requires an approved candidate and `--execute`.

## Setup check

`xig doctor` is safe to run before or after creating `config.yaml`. It verifies:

- Python 3.11 or newer.
- Playwright package availability.
- Config validity when a config file exists.
- Selected scan mode and whether the configured X API token environment variable is set.
- Storage directory writability.
- SQLite review queue access.

It never prints token values.

## Troubleshooting

- If `xig` is not found, confirm your Python scripts directory is on `PATH`.
- If you need to confirm the installed package version, run `xig --version`.
- If Playwright browser install fails, rerun `playwright install chromium`.
- If no candidates appear in fixture mode, remove the demo database at `~/.x-impersonation-guard/db.sqlite` and rerun `xig scan-fixture`.
