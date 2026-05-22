# Installation

```bash
git clone https://github.com/wheelieinvestor/x-impersonation-guard.git
cd x-impersonation-guard
uv sync --all-groups
uv run xig init \
  --config config.yaml \
  --handle yourhandle \
  --display-name "Your Name" \
  --reporter-name "Your Legal Name" \
  --reporter-email you@example.com
```

For API-backed detection, export your own X bearer token:

```bash
export X_API_BEARER_TOKEN=...
```

Scrape fallback is available through the client layer, but API mode is preferred.

Use `uv run xig init --guided --config config.yaml` if you prefer prompts over command flags.
