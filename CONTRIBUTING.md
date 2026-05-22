# Contributing

Thanks for considering a contribution. This project is intentionally local-first, safety-first, and transparent. Contributions should preserve those properties.

## Development setup

```bash
git clone https://github.com/wheelieinvestor/x-impersonation-guard.git
cd x-impersonation-guard
uv sync --all-groups
uv run playwright install chromium
```

Run the checks before opening a PR:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## Good first issues

Look for issues labeled `good first issue`. Each should include a problem statement, suggested approach, and definition of done.

## Pull request process

- Keep PRs small and focused.
- Use conventional commit style when practical: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Include tests for behavior changes.
- Do not commit credentials, `.env` files, cookies, browser profiles, screenshots with private data, or live evidence packages.
- Do not add live X API calls to tests.

## Adding a detector

1. Implement the detector behind the `Detector` protocol.
2. Keep network access behind a client boundary.
3. Add fixture or mocked tests.
4. Document the signal in `docs/scoring.md` if it affects scoring.

## Adding a scoring signal

1. Add the pure signal function.
2. Update the scorer weights and validation.
3. Add unit tests for true positives and mitigations.
4. Update README and docs so users understand the signal.

## Ethical boundary

This tool is for accurate impersonation reports. It is not for mass-reporting critics, parody accounts, fan accounts, or unrelated users.
