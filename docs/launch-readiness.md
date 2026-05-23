# Launch Readiness Checklist

This page is a pre-launch checklist and copy bank. It is not approval to publish, tag, release, submit live reports, or post publicly.

## Current Launch Position

Use this positioning until live validation is complete:

> `x-impersonation-guard` is a public alpha for detecting X impersonation candidates, reviewing them locally, and creating dry-run evidence packages. Offline demo, packaging, install path, scoring fixtures, and fail-closed reporting safety are verified. Live X API scans and live Help Center report submissions are implemented but still pending controlled validation.

Do not call it live-ready until `docs/status.md` records:

- one controlled live read-only scan;
- one reviewed dry-run evidence package for a real candidate;
- real-world scoring calibration notes;
- one approved live Help Center report, or an explicit decision to defer live submission.

## Pre-Post Checklist

Before any public post:

- [ ] `main` is clean and synced with `origin/main`.
- [ ] Latest `main` CI is green for lint, tests, and docs.
- [ ] No confusing stale open PRs.
- [ ] No launch-blocking open issues.
- [ ] `docs/status.md` matches the true verification state.
- [ ] README says public alpha, not live-ready.
- [ ] PyPI install command works for the currently promoted version.
- [ ] Docs site routes return 200 for Home, Install, Status, Security, and Launch support.
- [ ] Demo GIF and screenshots render in README/docs.
- [ ] GitHub social preview is set.
- [ ] Pinned welcome discussion is present.
- [ ] No secrets, tokens, cookies, browser profiles, or unredacted evidence packages are in the repo.

## First Post Draft

Use this only after the pre-post checklist passes:

```text
I open-sourced x-impersonation-guard, a local-first tool for finding X impersonation accounts, reviewing candidates, and generating evidence packages for official reports.

Public alpha: offline demo, dry-run reports, packaging, and fail-closed safety are verified. Live validation is still in progress.

Repo: https://github.com/wheelieinvestor/x-impersonation-guard
```

## Technical Follow-Up Draft

```text
Under the hood, x-impersonation-guard scores candidates with handle similarity, display-name match, profile-image perceptual hashing, bio/post signals, account age, follower patterns, and verification status.

It stores a local SQLite review queue and defaults to dry-run evidence packages before any live Help Center submission.

Status matrix: https://wheelieinvestor.github.io/x-impersonation-guard/status/
```

## Demo Reply Draft

```text
Try the offline demo with no credentials and no live X calls:

pip install --pre x-impersonation-guard
playwright install chromium
xig scan-fixture
xig list
xig report --dry-run 1
```

## Limitations Reply Draft

```text
Important limits: this is not a removal guarantee, not legal advice, and not a tool for targeting critics/parody/fan accounts. Live X API scans and live Help Center submissions are still being validated carefully.
```

## Launch-Day Monitoring

After posting:

1. Watch new issues and discussions for install problems first.
2. Ask reporters to reproduce with `xig scan-fixture` before debugging live paths.
3. Move safety-sensitive reports to private channels if they include evidence, tokens, or personal data.
4. Keep any hotfix small and run the full verification gate.
5. Update `docs/status.md` if live verification status changes.

## Stop Conditions

Pause promotion if any of these happen:

- PyPI install fails from a clean environment.
- `xig scan-fixture` no longer creates candidates.
- Dry-run reporting fails to create an evidence package.
- A user reports accidental live submission.
- A secret or unredacted evidence package is exposed.
- Main CI turns red.
