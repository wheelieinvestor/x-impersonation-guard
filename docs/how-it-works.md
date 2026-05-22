# How it works

X Impersonation Guard has three isolated pipelines.

1. Detection finds possible impersonators through handle variants, display-name searches, follower scans, image hashes, and scrape fallback.
2. Scoring assigns a 0 to 100 score and stores an explainable signal breakdown.
3. Reporting uses Playwright to file X Help Center reports after user approval.

The pipelines communicate through SQLite so each stage can be tested independently.
