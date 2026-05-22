# Rate limits and safety

Automated reporting can put the reporter account at risk. The default flow requires manual review.

Safety controls:

- `auto_submit: false` by default.
- Live submission requires both `--execute` and `--confirm-live`.
- 5 reports per rolling 24 hours by default.
- Hard cap of 20 reports per rolling 24 hours.
- Random delay between live submissions.
- No credential rotation.
- No false-report assistance.
- Full audit package for every attempted report.
