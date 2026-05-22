# Configuration

`config.yaml` defines protected identities, API mode, scoring thresholds, reporting limits, storage, and logging.

Generate a starter file:

```bash
uv run xig init \
  --config config.yaml \
  --handle yourhandle \
  --display-name "Your Name" \
  --reporter-name "Your Legal Name" \
  --reporter-email you@example.com
```

If you omit the identity options, the generated file uses generic placeholder values instead of a maintainer account. Edit those fields before running a live scan, or use `uv run xig init --guided --config config.yaml` to answer prompts.

Inspect the active config without printing reporter emails or token values:

```bash
uv run xig config --config config.yaml
uv run xig config --config config.yaml --json
```

`x_api.max_cost_per_scan_usd` defaults to `2.0`. API-backed scans use `x_api.estimated_cost_per_request_usd` to stop before exceeding the configured estimated scan budget. The default request estimate is intentionally conservative and configurable because actual X API pricing depends on your account and plan.

`auto_submit` defaults to false. `max_reports_per_24h` defaults to 5 and cannot exceed 20.
