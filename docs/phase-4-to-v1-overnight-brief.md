# Hermes Mission Brief: x-impersonation-guard - Overnight Path to Public-Ready v1

## Current State

- Repository: `/Users/deanahrens/Code/x-impersonation-guard`
- GitHub: `wheelieinvestor/x-impersonation-guard`
- Phase 3 launch polish is complete.
- `main` was previously synced and green after the Phase 3 cleanup, good-first issue batch, and superseded asset cleanup.
- `v0.2.0-alpha` is expected to be on PyPI from the prior release bridge.
- Offline demo behavior is polished and verified.
- Live X API scans, live real-world calibration, and live Help Center report submission still need controlled validation.

Before acting, re-verify the current state because another agent may have changed the repo, GitHub PRs, issues, tags, releases, or CI since this brief was written.

## Mission

Move `x-impersonation-guard` from polished offline public alpha toward a credible public-ready v1 candidate.

Work continuously and autonomously where safe. Stop only at explicit approval gates, missing credentials, live-submission gates, publish/tag/release gates, or true blockers.

The product must remain truthful: never claim live behavior is verified until it has actually been verified. Prefer small focused PRs, strong tests, and status documentation over broad rewrites.

## Global Rules

- Work from `/Users/deanahrens/Code/x-impersonation-guard`.
- Start by inspecting:
  - `git status --short --branch`
  - `git log -5 --oneline --decorate`
  - open PRs
  - open issues
  - recent CI runs
  - tags/releases
  - PyPI package state
  - `docs/status.md`
- Do not commit or expose secrets.
- Do not ask Dean to paste secrets into chat.
- No live X API calls until Dean explicitly confirms the token/config is ready.
- No live Help Center report submissions without an exact, explicit approval for the specific command and candidate id.
- No PyPI publish, git tag, GitHub release, or public launch action without explicit approval.
- Dry-run/read-only work is allowed where credentials are not required.
- Keep `main` green.
- Use small branches and focused PRs.
- If another agent polluted main or created confusing PRs, repair repo state first before proceeding.
- Update `docs/status.md` whenever verification status changes.
- Run the repo's full verification gate before opening each implementation PR:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv build`
  - docs build if docs changed
- Treat failures as real until proven otherwise.

## Phase 4: Live-Validation Readiness

Goal: make sure the repo is ready for controlled live validation without changing live behavior yet.

Tasks:

1. Re-audit the current local and GitHub state.
2. Verify there are no stale open PRs that conflict with the intended path.
3. Re-run the full local verification gate.
4. Run a fresh clean-venv install from the local wheel.
5. Run the offline demo smoke path:
   - `xig scan-fixture`
   - `xig list`
   - `xig report --dry-run 1`
   - `xig export-report 1`
6. Inspect config handling and make sure live commands fail clearly when required credentials/config are absent.
7. Confirm live report submission defaults remain safe and dry-run oriented.
8. Update `docs/status.md` only if the current state is stale or inaccurate.

Acceptance:

- Main state is understood.
- Local verification is green or blockers are documented.
- Offline install/demo path is still healthy.
- No live calls have been made.

## Phase 5: Controlled Live Read-Only Scan

Goal: validate one read-only live scan path without submitting reports.

Approval gate:

Stop and ask Dean to confirm:

- X API account is ready.
- Bearer token is configured locally outside chat.
- Spending cap is in place.
- Which protected identity/account should be used for the first read-only scan.

Do not proceed without that approval.

Tasks after approval:

1. Verify token presence without printing it.
2. Run any existing config/doctor checks.
3. Run one bounded live read-only scan using the safest supported mode.
4. Save a redacted transcript under a suitable validation folder if the repo already has a convention, otherwise propose a small docs/validation location.
5. Run:
   - `xig list`
   - `xig list --json`
6. Do not submit any live report.
7. Update `docs/status.md` with the exact live-read-only result.

Acceptance:

- One live read-only scan is verified, or a specific blocker is documented.
- No secrets are logged.
- No live report is submitted.

## Phase 6: Scoring Calibration From Real Candidates

Goal: calibrate scoring against a small, real, manually reviewed set.

Tasks:

1. Build a small redacted candidate review set from the read-only scan.
2. Ask Dean to label a bounded set of candidates if needed.
3. Compare scores against labels.
4. Adjust only deterministic scoring thresholds/weights if evidence supports it.
5. Add or update tests for any scoring changes.
6. Document limitations and calibration status.

Constraints:

- No ML model training.
- No opaque scoring.
- Do not overfit to one account.
- Keep synthetic fixture tests intact.

Acceptance:

- Real-candidate scoring behavior is understood.
- Any scoring changes are tested.
- False-positive/false-negative risks are documented.

## Phase 7: First Dry-Run Report From Real Candidate

Goal: produce a real-candidate dry-run evidence package without submitting it.

Tasks:

1. Pick the highest-confidence candidate from validated read-only scan output.
2. Ask Dean to confirm the candidate if needed.
3. Run dry-run report generation only.
4. Export the report package.
5. Inspect the package contents for completeness, safety, and redaction needs.
6. Update status documentation.

Acceptance:

- One real-candidate dry-run evidence package exists.
- The package is reviewable and does not leak credentials.
- No live report submission occurred.

## Phase 8: First Live Report Approval Gate

Goal: perform the first live report only with exact user approval.

Hard stop:

Before any live report submission, ask Dean for explicit approval in this form:

> Approve one live Help Center report submission for candidate `<id>` using command `<exact command>`.

Also summarize:

- Candidate identity.
- Evidence package path.
- Known risks.
- Whether the report path has already been dry-run.
- The exact command to be executed.

Do not proceed unless Dean explicitly approves that exact action.

Tasks after approval:

1. Run the one approved live submission.
2. Capture non-secret output.
3. Stop immediately after the one submission.
4. Update status documentation.

Acceptance:

- One live report is submitted, or the phase is explicitly deferred.
- No additional live submissions are attempted.

## Phase 9: Post-Live Hardening

Goal: fix only issues surfaced by live validation.

Tasks:

1. Triage all live validation problems.
2. Separate bugs from product limitations.
3. Create focused issues or PRs.
4. Add regression tests where possible.
5. Keep docs/status truthful.
6. Re-run full verification.

Acceptance:

- Live validation bugs are fixed or explicitly documented.
- Main remains green.
- Status docs match reality.

## Phase 10: v0.2.1-alpha Release Candidate

Goal: prepare the next alpha only if live validation produced meaningful fixes or documentation updates.

Approval gate:

Do not tag, publish, or create a release until Dean explicitly approves.

Tasks:

1. Compare current main against `v0.2.0-alpha`.
2. Decide whether version should be `0.2.1a0` or another pre-release.
3. Update changelog/status docs if needed.
4. Run full verification gate.
5. Build fresh artifacts.
6. Inspect wheel contents.
7. Prepare release notes.

Acceptance:

- Release candidate is ready.
- Nothing is published without approval.

## Phase 11: Publish v0.2.1-alpha

Goal: publish and validate the next alpha only after approval.

Approval gate:

Dean must explicitly approve:

- Tag name.
- PyPI publish.
- GitHub release.

Credential handling:

- If a PyPI token is required, tell Dean exactly where to set it in his terminal.
- Do not ask him to paste it into chat.
- Do not print it.
- Do not commit it.

Tasks:

1. Tag the approved release.
2. Publish to PyPI.
3. Wait for propagation.
4. Create GitHub pre-release.
5. Attach wheel and sdist.
6. Validate install from PyPI in:
   - Linux Python 3.11
   - Linux Python 3.12
   - macOS Python 3.11
7. Save validation logs.
8. Update status docs.

Acceptance:

- Published package installs cleanly.
- Offline demo works from PyPI.
- Status docs record the validation.

## Phase 12: Public Launch Readiness Audit

Goal: prepare for public promotion without actually launching.

Tasks:

1. Review README for truthful public-alpha positioning.
2. Verify docs site routes return 200.
3. Verify demo GIF/screenshots still render.
4. Verify GitHub social preview and pinned discussion if accessible.
5. Review issue templates, PR template, license, security posture, contributing docs, and release notes.
6. Draft launch copy, but do not post it.
7. Create a final launch checklist.

Acceptance:

- Repo is public-facing and coherent.
- Launch copy is prepared but not posted.
- Known limitations are explicit.

## Phase 13: Launch Support Prep

Goal: make the repo easier to operate after public attention.

Tasks:

1. Create or update a launch support runbook.
2. Define labels for bug, docs, install, live-validation, scoring, reporting, and security issues.
3. Document hotfix workflow.
4. Document how to revoke/rotate tokens if a secret is accidentally exposed.
5. Document how to reproduce the offline demo from a clean install.

Acceptance:

- Dean has a launch-day support checklist.
- The repo has clear triage and hotfix guidance.

## Final Completion Criteria

The overnight mission is complete when:

- Offline demo remains verified.
- Live read-only scan is verified or a precise blocker is documented.
- First real-candidate dry-run report is verified, if live scan produced candidates.
- First live report is either submitted with explicit approval or intentionally deferred.
- `docs/status.md` truthfully reflects all verification states.
- Changelog/release docs are accurate.
- Repo polish remains intact.
- Any published release has passed install validation.
- Launch readiness checklist exists.
- Main is green.
- There are no confusing stale open PRs.

## End Instruction

Work continuously overnight. Stop only at explicit approval gates, missing credentials, live submission gates, publish/tag/release gates, or true blockers. When stopped, report:

- The exact blocker.
- What has already been verified.
- The next exact command or approval needed.
