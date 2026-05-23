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
| PyPI install on Linux Python 3.11 | Verified | `phase2.6/install-validation-A.log` |
| PyPI install on Linux Python 3.12 | Verified | `phase2.6/install-validation-B.log` |
| PyPI install on macOS Python 3.11 | Verified | `phase2.6/install-validation-C.log` |

## Implemented but not yet verified live

| Capability | Status | Notes |
|------------|--------|-------|
| Live X API scan | Pending controlled live validation | No live X API evidence has been recorded in this repo yet. |
| Live help.x.com report submission | Pending controlled live validation | Dry-run reporting is verified; live submission still needs a tightly scoped first report. |
| Real-world scorer calibration | Pending controlled live validation | Current calibration is fixture-based. |

## Controlled live-validation gate

Before this repo should be promoted as live-ready, record evidence for one controlled validation pass:

- one real X API scan with no reports submitted;
- one reviewed dry-run evidence package for a real candidate;
- real-world scorer calibration against labeled impersonator and non-impersonator examples;
- at most one approved live Help Center report, only after the dry-run evidence is inspected.
