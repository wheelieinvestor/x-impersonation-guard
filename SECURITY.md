# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security vulnerabilities.

Use GitHub Security Advisories for private reports once enabled for this repository. If that is not available, contact the maintainer privately through the repository owner profile and include:

- A concise description of the issue.
- Steps to reproduce.
- Impact.
- Whether any credentials, cookies, browser profiles, or evidence packages may be exposed.

Expected response target: acknowledgement within 7 days.

## Scope

In scope:

- Credential handling.
- Local browser profile handling.
- Evidence-package privacy.
- Report-submission safety.
- Dependency or packaging vulnerabilities.

Out of scope:

- Attacks requiring access to the user's local machine.
- Vulnerabilities in X, Playwright, or third-party services unless this project worsens the risk.
- Requests to bypass X rate limits or reporting controls.

## Handling sensitive files

Do not paste tokens, cookies, browser profiles, or unredacted evidence packages into GitHub issues, discussions, pull requests, or chat transcripts.

## Supply-chain controls

- Dependabot checks Python/uv dependencies and GitHub Actions weekly, grouped by ecosystem to keep routine maintenance PRs reviewable.
- Pull requests that change dependency manifests run GitHub dependency review.
- Dependency review fails on newly introduced high-severity vulnerabilities and on GPL-family licenses that are not compatible with this project's MIT distribution model.
- Release builds use GitHub OIDC permissions for trusted publishing workflows; package credentials should not be committed or stored in the repo.
