# X Impersonation Guard

Read-first X impersonation detector with optional user-approved blocking through the official X API via `xurl`.

This project is designed for creators, founders, analysts, and public accounts that are being copied by low-quality/bought-looking accounts. It produces a ranked report first. Blocking is fail-closed and requires an explicit `--execute` flag.

## What it does

- Scores candidate accounts against a protected/main account.
- Flags common impersonation signals:
  - matching or near-matching display name
  - handle containing the protected handle
  - copied/similar bio
  - matching profile image URL
  - low-follower / high-following profile shape
- Mitigates false positives when a candidate is verified or has meaningful follower context.
- Runs fixture/offline scans for repeatable review.
- Wraps `xurl` for X API reads and blocking without storing credentials in this repo.

## What it does not do

- It does **not** prove an account was bought. The report says suspicious/impersonation risk, not platform-side ownership history.
- It does **not** auto-block from detection alone.
- It does **not** ship shared X credentials. Each user must authenticate their own X app/account.
- It does **not** post public accusations.

## Install locally

```bash
python3.11 -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
```

## Offline fixture scan

```bash
x-impersonation-guard scan-fixture --input examples/sample_accounts.json
```

Output includes ranked candidates and ends with:

```text
No accounts were blocked. Re-run a reviewed block action with --execute.
```

## Blocking after review

Dry run:

```bash
x-impersonation-guard block --authenticated-user-id YOUR_USER_ID --target-user-id TARGET_ID
```

Execute after manual review:

```bash
x-impersonation-guard block --authenticated-user-id YOUR_USER_ID --target-user-id TARGET_ID --execute
```

## X API / xurl setup

This project expects users to authenticate `xurl` themselves. Do not paste API keys into this repo or into an AI chat.

Required X capabilities:

- read public users/posts for detection
- OAuth user context for blocking
- rate-limit handling for production scans

See `docs/setup.md` for the operational setup and safety rules.

## Development

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check .
./.venv/bin/python -m ruff format --check .
```

## Safety posture

Default behavior is report-only. Any write action to X must be intentionally invoked by the authenticated account owner.
