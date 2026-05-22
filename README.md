# X Impersonation Guard

Automatically detect and report X accounts impersonating you.

Public figures get cloned constantly. Reporting each clone by hand is slow, repetitive, and easy to miss. X does not provide an API endpoint for impersonation reports, so this tool separates detection, review, and official Help Center submission.

X Impersonation Guard is built for local control. Your credentials stay on your machine. You review candidates before reports are submitted by default.

## Status

Private alpha foundation. Core scoring, review queue storage, safety limits, and dry-run reporting are implemented. Live X API and Help Center form automation are structured behind adapters so they can be tested without live credentials.

## Quickstart

```bash
git clone https://github.com/wheelieinvestor/x-impersonation-guard.git
cd x-impersonation-guard
uv sync --all-groups
uv run xig init --config config.yaml
uv run xig scan --config config.yaml
uv run xig list --config config.yaml
```

## What the default scan does

`xig scan` runs four detection steps:

1. **Handle variant lookup**: generates username variants of your protected handle and checks which accounts exist.
2. **Display name search**: searches recent posts and profiles for your display name.
3. **Follower scan**: samples followers for accounts that match suspicious patterns.
4. **Profile image hashing**: fetches and perceptually hashes profile pictures of candidates from steps 1-3 when image URLs are available.

Detection mode:

- If `X_API_BEARER_TOKEN` is set in your environment, scan uses the official X API.
- Otherwise, scan falls back to authenticated browser scraping via Playwright. This is slower, less reliable, and free.

You can force a mode with `x_api.mode: api` or `x_api.mode: scrape` in `config.yaml`.

## How it works

```text
config.yaml -> detectors -> scorer -> SQLite review queue -> user approval -> Playwright reporter -> audit log
```

Three pipelines stay separate:

1. Detection finds candidate accounts through handle variants, display-name matches, follower scans, cached image hashes, or scrape fallback.
2. Scoring ranks each candidate from 0 to 100 with an explainable signal breakdown.
3. Reporting uses Playwright to submit X's official Help Center impersonation form after approval.

## Safety warning

Mass reporting can put the reporter account at risk. X may flag accounts that submit too many reports.

Defaults are conservative:

- Manual review queue enabled.
- `auto_submit: false`.
- Maximum 5 reports per identity per rolling 24 hours.
- Hard configuration cap of 20 reports per rolling 24 hours.
- Random delay between submissions.
- Evidence and audit package saved for every attempted report.

If you enable auto-submit, you are accepting that risk explicitly.

## Configuration

Run:

```bash
uv run xig init --config config.yaml
```

The generated config is designed for `@wheelieinvestor` and can be edited for another individual identity.

API mode is preferred when `X_API_BEARER_TOKEN` is configured. Scrape mode is slower and more fragile because X can change page markup.

## Commands

```bash
xig init
xig scan
xig scan --identity wheelieinvestor
xig list
xig review
xig report <candidate_id>
xig log
xig status
xig daemon
xig export json
```

## What this tool does NOT do

- It does not guarantee account removal. X decides enforcement outcomes.
- It does not submit reports through the X API. X has no impersonation report endpoint.
- It does not bypass X rate limits or rotate credentials to evade platform controls.
- It does not fabricate evidence.
- It does not silence critics, parody accounts, fan accounts, or people you dislike.
- It does not provide legal advice.
- It does not yet provide a hosted SaaS dashboard, nightly E2E selector monitoring, or cross-platform Threads/Bluesky support.

## Limits

There is no X API endpoint for impersonation reports. Reporting requires browser automation against X's Help Center form. The user may still need to confirm emailed verification links from X.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## Roadmap

- Harden Playwright selectors against live Help Center changes.
- Add nightly selector e2e checks with staging credentials.
- Add richer Textual review workflows.
- Add Hermes adapter for agent-operated scans and summaries.
- Add Threads and Bluesky detection support after X v1.0 is stable.

## License

MIT

## Author

Wheelhouse Capital LLC. Built for Dean Ahrens, @WheelieInvestor.
