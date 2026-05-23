# Scoring explained

Candidates are scored from 0 to 100. The default model is deterministic and explainable.

| Signal | Weight | Purpose |
|--------|--------|---------|
| Handle similarity | 20 | Catches suffixes, one-character edits, and homoglyph-style handles. |
| Display-name similarity | 15 | Catches copied profile names. |
| Bio similarity | 10 | Catches "official", support, backup, and protected-handle references. |
| Image similarity | 25 | Uses perceptual hashing when profile image URLs or fixture hashes exist. |
| Account age | 10 | Fresh accounts are more suspicious. |
| Follower ratio | 5 | Tiny follower counts against a larger protected account are suspicious. |
| Follow-back pattern | 5 | Accounts targeting the protected audience get extra weight. |
| Posting behavior | 5 | Scam posts and protected-handle mentions raise the score. |
| Verified status | 5 | Paid verification can make clones more dangerous. |

Mitigations reduce scores for parody/fan disclaimers, verified affiliation mismatches, and accounts that predate the protected identity.

For a narrative explanation of how clone tactics change over time, see
[How impersonators evolve](impersonator-evolution.md).

## Demo examples

- `@alex_charts1`: critical. Similar handle, identical profile image, new account, scam posts.
- `@alex_charts_giveaway`: medium. Suspicious promo account, but weaker image match.
- `@alex_charts_fan`: filtered. Explicit fan-account disclaimer.
- `@alex_charts_real`: filtered. Older unrelated account.
