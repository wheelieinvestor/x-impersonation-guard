# Substack outline

## Working title

I built an open-source agent to find the accounts impersonating me on X

## Hook

X impersonation stops being theoretical the moment a copied profile starts sending your followers into DMs. The account can reuse your name, your profile image, and enough of your language to make a rushed follower hesitate before realizing something is wrong.

The frustrating part is not just finding the clone. It is collecting evidence, deciding whether the account is actually impersonating you, filing the same report flow again, and remembering what has already been submitted. That is manageable once. It is not a system.

So I built `x-impersonation-guard`: a local-first, open-source CLI for detecting likely impersonators, reviewing explainable scores, and preparing official X Help Center reports without turning reporting into an unsafe auto-submit machine.

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
