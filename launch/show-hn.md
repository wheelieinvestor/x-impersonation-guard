# Show HN draft

Title: Show HN: x-impersonation-guard - Detect and report X accounts impersonating you

I built a local-first CLI for finding X accounts that impersonate a protected identity and preparing official Help Center reports.

The interesting constraint is that X does not expose an impersonation-report API. Detection can use API or browser-backed lookup, but report submission has to go through the Help Center form. The project keeps those stages separate: detection, scoring, review, and reporting.

The scorer is intentionally explainable rather than ML-heavy. It combines handle similarity, display-name similarity, profile-image perceptual hashes, account age, follower patterns, posting behavior, and mitigations for parody/fan/older legitimate accounts.

The default path is safe: run an offline fixture demo, review candidates locally in SQLite, generate dry-run evidence packages, and only submit live reports after approval. Live X validation is still pending; the public alpha is meant for feedback on install path, UX, scoring transparency, and safety model.

Repo: https://github.com/wheelieinvestor/x-impersonation-guard
