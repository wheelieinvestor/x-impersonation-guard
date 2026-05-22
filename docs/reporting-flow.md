# Reporting flow

X has no public API endpoint for impersonation reports. The reporter uses Playwright against X Help Center.

A report package contains:

- `evidence_profile.png`
- `evidence_profile.html`
- `score_breakdown.json`
- `form_submission.png`
- `form_response.html`
- `report.json`

Dry run mode creates an evidence package without submitting. Live submission requires `--execute` and an approved candidate.
