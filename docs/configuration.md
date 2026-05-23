# Configuration

`config.yaml` defines protected identities, API mode, scoring thresholds, reporting limits, storage, and logging.

Generate a starter file:

```bash
uv run xig init --config config.yaml
```

The default identity is `wheelieinvestor`. `auto_submit` defaults to false. `max_reports_per_24h` defaults to 5 and cannot exceed 20.
