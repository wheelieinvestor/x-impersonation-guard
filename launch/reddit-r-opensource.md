# r/opensource draft

Title: x-impersonation-guard: local-first tool for detecting X impersonator accounts

I released a public alpha of `x-impersonation-guard`, an MIT-licensed Python CLI that helps creators find likely X impersonators, review explainable scores, and prepare official Help Center reports.

It is not a mass-reporting tool. The default flow is review-first, dry-run-first, and local-first. It explicitly mitigates parody/fan accounts and keeps an audit trail for every report package.

The repo includes a realistic offline demo fixture, PyPI prerelease package, CI, docs, and good-first issues for contributors.

Try it:

```bash
pip install --pre x-impersonation-guard
xig scan-fixture
xig review
```

Repo: https://github.com/wheelieinvestor/x-impersonation-guard
