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
| Live X API scan | Pending Phase 2 | No live X API calls during Phase 2.6. |
| Live help.x.com report submission | Pending Phase 2 | Dry-run only during Phase 2.6. |
| Real-world scorer calibration | Pending Phase 2 | Current calibration is fixture-based. |

## Phase 2 entry gate

Phase 2 starts after the install validation PR lands and Dean answers the open Phase 2 questions about X API readiness, labeling time, first-report candidate selection, acceptable false-positive rate, and brand identity scope.
