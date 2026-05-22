## Summary
- 

## Checklist
- [ ] Commit message follows conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, etc.)
- [ ] Tests added or updated where behavior changed
- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run mypy src tests` passes
- [ ] README/docs updated if user-facing behavior changed
- [ ] No secrets, cookies, tokens, or private personal data committed

## Safety notes
- [ ] Reporting changes remain dry-run by default
- [ ] Live submission still requires explicit user action
- [ ] Selector failures fail closed, not partially submitted
