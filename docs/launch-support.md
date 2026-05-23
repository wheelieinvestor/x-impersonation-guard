# Launch Support Runbook

This runbook is for launch-day triage after public promotion. It keeps support work bounded, reproducible, and safe while live X validation is still controlled.

## Triage Rules

1. Never ask users to paste X API tokens, cookies, browser profile files, or unredacted evidence packages into public issues.
2. Reproduce install and offline-demo bugs before changing code.
3. Treat live-reporting bugs as safety-sensitive until proven otherwise.
4. Keep fixes small and scoped to one failure mode.
5. Update `docs/status.md` when a verification state changes.

## Issue Labels

Use these labels to keep launch feedback sortable:

| Label | Use |
|-------|-----|
| `bug` | Reproducible product or packaging defect. |
| `docs` | README, docs site, examples, or wording fix. |
| `install` | pip, PyPI, dependency, Playwright, or PATH issue. |
| `live-validation` | Controlled live scan/report validation work. |
| `scoring` | Candidate score, threshold, false positive, or false negative issue. |
| `reporting` | Evidence packages, dry-run reporting, or Help Center form behavior. |
| `security` | Secret handling, privacy, dependency, or abuse-prevention issue. |
| `selector-drift` | Help Center form or X page selector changed. |
| `good first issue` | Small, low-risk, well-scoped contribution. |

## First Response Checklist

For every bug report, ask for:

- `xig version` output.
- OS and Python version.
- Exact command sequence.
- Redacted terminal output.
- Whether the failure happens with `xig scan-fixture`.
- Whether the failure involved `--execute`.

If `--execute` was involved, ask the reporter to stop live submissions until the issue is understood.

## Clean Install Reproduction

Use this path for install and packaging reports:

```bash
TEMP_VENV=$(mktemp -d)
python3.11 -m venv "$TEMP_VENV/.venv"
source "$TEMP_VENV/.venv/bin/activate"
pip install --pre x-impersonation-guard
playwright install chromium
HOME="$TEMP_VENV" xig scan-fixture
HOME="$TEMP_VENV" xig list
HOME="$TEMP_VENV" xig report --dry-run 1
HOME="$TEMP_VENV" xig export-report 1
deactivate
rm -rf "$TEMP_VENV"
```

Expected result:

- `xig scan-fixture` queues fictional `@alex_charts` candidates.
- `xig list` prints pending candidates.
- `xig report --dry-run 1` creates a local evidence package.
- `xig export-report 1` creates a zip archive.
- No live X calls or live Help Center submissions happen.

## Hotfix Workflow

1. Confirm `main` is clean and CI is green.
2. Create a focused branch:

```bash
git switch main
git pull --ff-only
git switch -c fix/<short-failure-name>
```

3. Add a regression test before or with the fix.
4. Run the full gate:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv build
uvx --from mkdocs-material==9.6.23 mkdocs build -f docs/site/mkdocs.yml --strict
```

5. Open a focused PR with:

- Failure summary.
- Root cause.
- Verification commands.
- Safety notes.

6. Merge only after CI is green.

## Secret Exposure Response

If a token, cookie, browser profile, or unredacted evidence package is exposed:

1. Do not quote the secret in comments or commits.
2. Ask the owner to revoke or rotate the credential immediately.
3. Delete or redact the public artifact where possible.
4. Force-push only if the exposed secret is in git history and the maintainer explicitly approves history rewrite.
5. Record the incident privately.
6. Add a prevention issue or test if the leak came from project behavior.

For X API bearer tokens:

- Revoke the token in the X developer portal.
- Create a new token.
- Set it locally as `X_API_BEARER_TOKEN`.
- Re-run `xig doctor`; it reports token presence without printing the token.

For PyPI tokens:

- Revoke the token at `https://pypi.org/manage/account/token/`.
- Create a new project-scoped token when possible.
- Set it only in the local shell for the publish session.

## Live-Validation Guardrails

Until `docs/status.md` says live validation is complete:

- Use fixture mode for public reproduction.
- Use dry-run reporting for support.
- Run live read-only scans only with explicit maintainer approval.
- Submit live Help Center reports only for an exact approved candidate id and command.
- Stop after one live submission and document the result.

## Release Support

Before publishing a hotfix release:

1. Confirm the bug affects the published package or blocks launch support.
2. Bump to the next alpha patch version.
3. Build and inspect artifacts.
4. Publish only after explicit approval.
5. Validate PyPI install from Linux Python 3.11, Linux Python 3.12, and macOS Python 3.11.
6. Update `docs/status.md` and `CHANGELOG.md`.
