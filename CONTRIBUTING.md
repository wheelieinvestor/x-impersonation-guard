# Contributing

Use conventional commits and small PRs.

Before opening a PR:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

Do not commit credentials, `.env`, screenshots containing private data, or live evidence packages.
