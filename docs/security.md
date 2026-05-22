# Security

Do not paste tokens, cookies, browser profiles, or unredacted evidence packages into public issues.

Use `xig redact-report <report_dir>` before attaching report diagnostics to a public issue. It creates a zip with redacted JSON, text, and log diagnostics, removes common token/cookie/session fields, and excludes screenshots or HTML by default.

## Reporting vulnerabilities

Use GitHub Security Advisories for private vulnerability reports once enabled for the repository. Until then, contact the maintainer privately through the repository owner profile.

## Sensitive local data

The tool stores local state under `~/.x-impersonation-guard/` by default:

- SQLite review queue.
- Evidence packages.
- Playwright browser profile.

Treat those files as private.

## Safety boundaries

- No credential rotation.
- No fabricated evidence.
- No bypass of X rate limits.
- Manual review before live reporting by default.

## Supply-chain controls

- Dependabot opens weekly update PRs for Python/uv dependencies and GitHub Actions, grouped by ecosystem to keep routine maintenance PRs reviewable.
- Dependency review runs on pull requests and fails on newly introduced high-severity vulnerable dependencies.
- GPL-family licenses are denied in dependency review to keep the MIT package distribution straightforward.
- Release workflows use OIDC-capable permissions rather than committed package credentials.
