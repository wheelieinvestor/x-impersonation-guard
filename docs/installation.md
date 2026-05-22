# Installation

```bash
git clone https://github.com/wheelieinvestor/x-impersonation-guard.git
cd x-impersonation-guard
uv sync --all-groups
uv run xig init --config config.yaml
```

For API-backed detection, export your own X bearer token:

```bash
export X_API_BEARER_TOKEN=...
```

Scrape fallback is available through the client layer, but API mode is preferred.
