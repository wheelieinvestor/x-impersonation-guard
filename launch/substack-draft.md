# Substack outline

## Working title

I built an open-source agent to find the accounts impersonating me on X

## Hook

Open with the concrete impersonator story Dean will fill in before launch: who cloned the account, what they sent followers, and why manual reporting was not enough.

## Why this matters for FinTwit

- Trust is the distribution layer.
- Clone accounts monetize urgency and confusion.
- Followers often cannot tell the difference fast enough.

## What I built

- Local-first CLI.
- Multi-signal scoring.
- Review queue.
- Dry-run evidence packages.
- Playwright Help Center reporter.

## Safety story

- Review-first by default.
- No fabricated evidence.
- Parody/fan mitigations.
- Reporting caps and audit trail.
- Live submissions require explicit approval.

## How to try it

```bash
pip install --pre x-impersonation-guard
playwright install chromium
xig scan-fixture
xig review
```

## What's next

- Phase 2 live validation.
- Real-world scorer calibration.
- Selector-drift monitoring.
- Brand identity support.

## Ask

Try the offline demo. Open issues. Send feedback. If you have this problem too, help make the tool better.
