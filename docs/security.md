# Security

Do not paste tokens, cookies, browser profiles, or unredacted evidence packages into public issues.

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
