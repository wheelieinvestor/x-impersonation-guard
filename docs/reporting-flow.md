# Reporting flow

X has no public API endpoint for impersonation reports. The reporter uses Playwright against X Help Center.

A report package contains:

- `evidence_profile.png`
- `evidence_profile.html`
- `score_breakdown.json`
- `form_submission.png`
- `form_response.html`
- `report.json`

Dry run mode creates an evidence package without submitting. Live submission requires an approved candidate plus `--execute --confirm-live`. If your config has more than one protected identity, use `xig report --identity <handle> <candidate_id>` so the command fails closed when the candidate belongs to a different identity.

## Sharing diagnostics

Report packages can include reporter contact fields, account handles, screenshots, and HTML from the browser session. Treat the original directory as private.

For public bug reports, create a redacted bundle:

```bash
xig redact-report ~/.x-impersonation-guard/reports/<report_dir>
```

The redacted bundle includes JSON diagnostics with sensitive fields replaced and excludes screenshots or HTML by default. Review any original image or HTML file manually before sharing it.
