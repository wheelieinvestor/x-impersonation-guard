# FAQ

## Who should use this?

Creators, operators, journalists, investors, builders, and public figures who are repeatedly copied on X and need a structured way to find likely impersonators, review the evidence, and file official reports.

The current alpha is best for one person protecting one or more personal identities. Brand, company, and agency workflows are possible, but they still need more live validation before they are treated as first-class.

## What is the fastest safe way to try it?

Use the offline demo first:

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig demo
xig review
xig report --dry-run 1
```

`xig demo` uses fictional accounts, stores state under `.xig-demo/`, and never touches the live X site. Run `xig demo --reset` when you want a clean repeatable demo.

## Does this remove impersonators?

No. It detects and reports likely impersonators. X decides whether an account violates its rules and whether enforcement happens.

The tool helps with the parts you control: discovery, evidence, review, dry-run report packages, live report submission through the official Help Center, and a local audit trail.

## Can it report through the X API?

No. X does not offer a public impersonation-report API. Reporting uses Playwright against X's official Help Center form.

That is why live submission is deliberately gated. A candidate must be approved first, and the command still requires both `--execute` and `--confirm-live`.

## Do I need an X API token?

No for the offline demo and fixture mode. No token is needed to inspect the workflow, review demo candidates, or create dry-run evidence packages.

For real scans, API mode is preferred when you have access because it is more stable than browser scraping. Scrape mode exists for users without API credentials, but it is inherently more likely to break when X changes the site.

## Is scrape mode reliable?

It is useful as a fallback, not a guarantee. Browser scraping depends on public page behavior, network state, and X UI changes.

Run `xig doctor` before live use. It checks Playwright, Chromium, config validity, starter identity placeholders, token environment state, storage access, and SQLite queue access without printing secret values.

## What data stays on my machine?

By default, config, queue state, evidence packages, report packages, diagnostics, and audit records are local files. The tool is local-first and does not send your data to a hosted service.

Treat original report packages as private. They may contain handles, screenshots, HTML, and reporter contact fields.

## What is safe to share in a GitHub issue?

Prefer privacy-safe diagnostics:

```bash
xig doctor --json
xig status --json
xig support-bundle --output xig-support.zip
```

The support bundle excludes config files, API tokens, cookies, browser profiles, screenshots, raw report packages, and private evidence. For report-specific bugs, use `xig redact-report <report_dir>` and still review the output before posting it publicly.

## Can I auto-submit reports?

Yes, but it is off by default and intentionally discouraged for the alpha. Manual review is safer because false positives can harm legitimate parody, fan, commentary, or unrelated accounts.

Live Help Center submission requires an approved candidate plus `--execute --confirm-live`. The default config also caps live reports per 24 hours.

## How does it avoid false positives?

Scoring uses multiple signals instead of one brittle match: handle similarity, display-name similarity, bio overlap, profile image similarity, account age, follower ratio, follow-back patterns, posting behavior, and verification status.

Mitigations reduce scores for parody/fan disclaimers, affiliation mismatches, and older accounts that predate the protected identity. You still make the final call in the review queue.

## What if I protect more than one account?

Use `--identity <handle>` when reviewing or reporting:

```bash
xig review --identity yourhandle
xig report --identity yourhandle --dry-run 1
```

Review and report actions fail closed when the candidate belongs to a different protected identity. Generated follow-up commands preserve `--config` and `--identity` so multi-identity users do not accidentally act on the wrong queue.

## Does this work for brands or companies?

Not as a polished first-class workflow yet. The alpha is optimized for individual identities, but the config model supports identity type, reporter details, and multiple protected identities.

If you use it for a brand, keep live reporting manual, document your validation run, and avoid auto-submit until you have labeled calibration data.

## Is this against X's rules?

The tool is designed to use public APIs or public pages for detection and X's official Help Center for reporting. It does not bypass rate limits, rotate credentials, fabricate evidence, or submit through private endpoints.

You are responsible for using it within X's current terms and your local laws.

## Will this get my account banned?

Any reporting workflow can create account risk if abused. The defaults are conservative: local-first execution, manual review, `auto_submit: false`, randomized delays, 24-hour report limits, dry-run evidence packages, and explicit live-confirmation flags.

Do not mass-report gray-area accounts. Start with obvious impersonators, keep evidence, and submit at most one controlled live report during validation.

## Does X actually remove reported accounts?

Sometimes, at X's discretion. This project cannot promise enforcement outcomes.

The value is that reports become consistent, evidence-backed, and auditable instead of scattered across screenshots and browser tabs.

## Can I run this on a server?

Technically yes, but the current defaults assume a local operator and a visible browser for sensitive live steps. Headless or unattended reporting increases risk and should be treated as advanced usage.

For public alpha use, run locally, review candidates yourself, and keep live reporting explicit.

## What should I do before live validation?

Follow the [controlled live validation runbook](live-validation.md). At minimum:

- run `xig doctor`;
- run a real scan without submitting reports;
- review candidates manually;
- create a dry-run evidence package;
- run scorer calibration against labeled examples;
- submit at most one controlled live Help Center report.

Keep tokens, cookies, browser profiles, screenshots, and private evidence out of public issues.

## What about Threads, Bluesky, Instagram, or TikTok?

Those are later platform integrations. The current implementation targets X because the detector assumptions, profile URLs, and Help Center reporter are platform-specific.

## How can I help?

The most useful contributions are privacy-safe bug reports, selector drift reports, labeled calibration feedback, docs improvements, and review of the safety model.

If you hit setup trouble, attach `xig support-bundle --output xig-support.zip` to the issue instead of raw config or screenshots.
