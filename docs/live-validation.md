# Controlled live validation

Use this runbook before treating the alpha as ready for broad public launch. The goal is to prove the live path with a small, reversible, well-documented run before encouraging many people to use it.

Do not paste X API tokens, cookies, browser profiles, private DMs, private evidence packages, or unredacted follower data into GitHub issues, docs, chats, or screenshots.

## Exit criteria

Phase 3 launch is not ready until all of these are true:

- One read-only X API scan completed within the configured cost budget.
- One labeled real-world calibration set was evaluated with `xig calibrate --output`.
- False positives and false negatives from that set were reviewed and documented.
- One dry-run report package was created for a real high-confidence candidate.
- At most one approved live Help Center report was submitted manually.
- Selector drift, report outcome, and any manual browser steps were recorded.
- No secret, cookie, private evidence, or browser-profile material was committed or posted publicly.

## 1. Prepare the environment

Start from a clean install and a private local workspace:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --pre x-impersonation-guard
playwright install chromium
xig init --guided
xig doctor --config config.yaml
```

Confirm `xig doctor` reports:

- config is valid;
- starter placeholders are gone;
- storage is writable;
- SQLite is reachable;
- Chromium is installed;
- token presence is detected without printing the token.

## 2. Set an API budget

Keep the first live scan intentionally small:

```yaml
x_api:
  max_cost_per_scan_usd: 1.00
  estimated_cost_per_request_usd: 0.01
```

Export the token only in the shell that runs the scan:

```bash
export X_API_BEARER_TOKEN="..."
```

Never put the token in `config.yaml`, docs, shell history screenshots, GitHub issues, or report bundles.

## 3. Build a labeled calibration set

Create a private JSON file with:

- one protected profile;
- known impersonators;
- known benign lookalikes, fan accounts, parody accounts, or support accounts;
- a short note for each label.

Run calibration with a JSON evidence artifact:

```bash
xig calibrate \
  --config config.yaml \
  --input private-calibration-set.json \
  --output calibration-results.json
```

Review `calibration-results.json` before sharing. Redact handles if needed, and do not publish accounts that would expose private victims or followers.

## 4. Run one read-only scan

Run a live scan without reporting anything:

```bash
xig scan --config config.yaml
xig status --config config.yaml
xig list --config config.yaml --status all
```

Check whether the queued candidates match the labeled expectations. Record:

- scan mode;
- configured cost budget;
- estimated spend;
- candidate count;
- false positives;
- false negatives;
- any account that should be snoozed or dismissed.

## 5. Review and dry-run one candidate

Pick the highest-confidence real impersonator that is safe to report:

```bash
xig review --config config.yaml --show <candidate_id>
xig report --config config.yaml --dry-run <candidate_id>
```

Inspect the dry-run package locally. Confirm the evidence is factual, relevant, and does not include unrelated private information.

## 6. Submit at most one live report

Only after manual review:

```bash
xig review --config config.yaml --approve <candidate_id>
xig report --config config.yaml <candidate_id> --execute --confirm-live
```

Use headed browser mode for the first run. Stop if selectors drift, required fields are missing, the form changes materially, or the browser asks for an unexpected step.

## 7. Record the validation result

Open a live validation issue with:

- environment and package version;
- scan mode;
- calibration metrics;
- redacted false-positive and false-negative notes;
- dry-run package status;
- Help Center selector status;
- live report result;
- any manual browser steps.

Do not attach raw evidence packages unless they are redacted and safe for public review.

## Expansion rule

After the first successful live report, expand slowly:

1. Re-run calibration with a larger labeled set.
2. Keep live report volume low.
3. Prefer snooze or dismiss for ambiguous accounts.
4. Re-check selectors before each larger reporting batch.
5. Update the status page only with evidence-backed results.
