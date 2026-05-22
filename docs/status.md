# Project status

Last updated: 2026-05-22

## Release

Current public alpha: `v0.2.0-alpha`

Published package: `x-impersonation-guard==0.2.0a0`

## What's verified end-to-end

| Capability | Status | Verification |
|------------|--------|--------------|
| Offline demo pipeline | Verified | `tests/integration/test_offline_demo.py` |
| Reporter fail-closed safety | Verified | `tests/unit/test_reporter_fail_closed.py` |
| Mode selector | Verified | `tests/unit/test_mode_selector.py` |
| Local setup doctor | Verified | `tests/unit/test_doctor.py` |
| Image hash signal in default scan | Verified | `tests/integration/test_detection_pipeline.py` |
| Cached image lookup in default scan | Verified | `tests/integration/test_detection_pipeline.py` |
| PyPI install on Linux Python 3.11 | Verified | `phase2.6/install-validation-A.log` |
| PyPI install on Linux Python 3.12 | Verified | `phase2.6/install-validation-B.log` |
| PyPI install on macOS Python 3.11 | Verified | `phase2.6/install-validation-C.log` |
| User-first config generation | Verified | `xig init --handle ... --reporter-email ...`; `tests/integration/test_cli.py` |
| Dependency security posture | Verified | Dependabot alerts clear; grouped update policy in `.github/dependabot.yml` |
| Estimated API scan budget guard | Verified | `tests/unit/test_cost_guard.py` |

## Implemented but not yet verified live

| Capability | Status | Notes |
|------------|--------|-------|
| Live X API scan | Pending live validation | Requires an X API bearer token and a selected test identity. |
| Live help.x.com report submission | Pending live validation | Dry-run packages are verified; live submission should start with one approved low-risk candidate. |
| Real-world scorer calibration | Pending live validation | Current calibration is fixture-based and should be checked against labeled real accounts. |

## Next validation gate

The next gate is controlled live validation:

1. Confirm X API token readiness and acceptable API budget.
2. Pick one protected identity and a small labeled candidate set.
3. Run a read-only live scan and compare scores against expected labels.
4. Dry-run evidence for the highest-confidence candidate.
5. Submit at most one live Help Center report after manual approval.
6. Record selector drift, false positives, false negatives, and report outcome before expanding usage.
