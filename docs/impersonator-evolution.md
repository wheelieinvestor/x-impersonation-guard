# How impersonators evolve

Impersonators usually start with low-effort cloning and become harder to spot as
the obvious handles get reported. The scorer uses multiple signals because no
single clue is reliable on its own.

## Common clone patterns

| Pattern | Example | Signal |
|---------|---------|--------|
| Suffixes | `alex_charts1`, `alex_chartss` | Handle similarity |
| Official-sounding handles | `alex_charts_official` | Handle and bio similarity |
| Homoglyphs | `aIex_charts`, `alex_chart$` | Normalized handle/name similarity |
| Copied images | Same avatar with small edits | Perceptual image hash |
| Giveaway scams | "DM me", "airdrop", "private group" | Posting behavior and bio overlap |
| Fresh accounts | Created recently with few followers | Account age and follower ratio |

## Why false positives matter

Not every similar account is malicious. Fan accounts, parody accounts, and older
unrelated accounts can look close at first glance. `x-impersonation-guard`
intentionally reduces scores when profiles clearly say they are fan/parody
accounts or when the candidate predates the protected identity.

See [Scoring explained](scoring.md) for the exact signals and demo examples.
