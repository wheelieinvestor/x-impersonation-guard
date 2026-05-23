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
- If you need to confirm installed versions for a bug report, run `xig version`.
- If no candidates appear in fixture mode, remove the demo database at `~/.x-impersonation-guard/db.sqlite` and rerun `xig scan-fixture`.

### Playwright browser install failures

`xig` depends on Playwright Chromium for scrape fallback and Help Center report
automation. If browser startup fails, run:

```bash
playwright install chromium
```

On Linux containers or minimal VMs, install browser system dependencies too:

```bash
playwright install chromium --with-deps
```

On macOS, make sure the active virtual environment is the same one where
`x-impersonation-guard` is installed, then rerun `playwright install chromium`.

If setup still fails, include `xig version`, your OS, and the exact Playwright
error in a bug report. Do not paste tokens, cookies, emails, or private handles.
