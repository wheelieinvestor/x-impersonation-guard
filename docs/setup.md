# Setup and operating rules

## Recommended deployment model

Best setup for public GitHub distribution:

1. Run the tool locally with your own X API bearer token when possible.
2. Keep browser sessions in the local persistent Playwright profile.
3. Run detection on a schedule or on demand.
4. Review candidates in SQLite-backed queue before reporting.
5. Submit reports through X Help Center only after approval.

This avoids shared credentials, keeps evidence local, and makes every report traceable to the operator who authorized it.

## X API rules this project follows

- Use official X API reads for detection when `X_API_BEARER_TOKEN` is configured.
- Request only needed profile fields.
- Enforce the configured estimated API scan budget before making another API request.
- Use fixture/offline mode for tests and demos.
- Keep credentials outside source control.
- Do not paste tokens, cookies, browser profiles, or evidence packages into issue reports.

## Browser reporting setup

X does not provide an impersonation report API. Reporting uses Playwright against X Help Center:

```bash
uv run playwright install chromium
uv run xig report <candidate_id> --config config.yaml
```

The command above is dry-run by default. Live submission requires review approval plus `--execute`:

```bash
uv run xig review --config config.yaml --approve <candidate_id>
uv run xig report <candidate_id> --config config.yaml --execute --confirm-live
```

Use headed mode unless you have a specific reason to run headless. The first live report may require manual login or form confirmation in the browser.

## Detection workflow

1. Load the protected identity from `config.yaml`.
2. Find candidate accounts with handle variants, display-name search, follower sampling, and cached image hash lookup.
3. Score each candidate with an explainable multi-signal model.
4. Store scores from 40 to 69 in low confidence.
5. Store scores 70 and above in the review queue.
6. Let reviewers approve, dismiss, or snooze candidates.
7. Use `xig status` to monitor pending, snoozed, approved, reported, and failed counts.
8. Use `xig list --status snoozed` or `xig list --status all` to revisit deferred or historical queue items.
9. Pass `--identity <handle>` to review and report commands when more than one protected identity is configured.
10. Submit only approved reports.

## Scorer calibration

Use `xig calibrate` with a labeled offline set before widening live usage:

```bash
uv run xig calibrate --config examples/config.individual.yaml --input examples/calibration.sample.json
```

The command prints precision, recall, F1, and any false positives or false negatives at the selected threshold. Use `--threshold <score>` to test a stricter or looser review threshold against the same labels.

Write a JSON evidence file when you want to compare calibration runs or share a redacted validation artifact:

```bash
uv run xig calibrate \
  --config examples/config.individual.yaml \
  --input examples/calibration.sample.json \
  --output calibration-results.json
```

The JSON includes the threshold, precision, recall, F1, confusion-matrix counts, every scored candidate, and any misses.

## Why reporting is not fully automatic by default

False positives are expensive. News accounts, parody accounts, fan accounts, and legitimate support accounts can look similar by text alone. X also may flag reporters that file too many reports. Manual review is the safe default.

## Production hardening still needed before v1.0

- Live Help Center selector verification.
- Real-world scorer calibration against known impersonator and non-impersonator sets.
