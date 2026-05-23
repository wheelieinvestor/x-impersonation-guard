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

If you omit the identity options, the generated file uses generic placeholder values instead of a maintainer account. Edit those fields before running a live scan.

`auto_submit` defaults to false. `max_reports_per_24h` defaults to 5 and cannot exceed 20.
