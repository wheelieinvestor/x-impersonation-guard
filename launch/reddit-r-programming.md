# r/programming draft

Title: I built an open-source CLI to detect and report X impersonation accounts

I built `x-impersonation-guard`, a local-first Python CLI for detecting likely X impersonation accounts and preparing official Help Center reports.

The architecture is intentionally boring: Typer CLI, SQLite review queue, deterministic scoring, Playwright for the Help Center flow, and dry-run evidence packages before any live submission.

The scorer uses multiple explainable signals: handle similarity, display name, profile image perceptual hash, account age, follower patterns, posting behavior, and mitigations for parody/fan/older accounts.

The public alpha is on PyPI and has an offline demo:

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig scan-fixture
xig review
```

No live X calls are made in fixture mode. Live validation is a separate phase.

Repo: https://github.com/wheelieinvestor/x-impersonation-guard
