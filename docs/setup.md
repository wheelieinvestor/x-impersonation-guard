# Setup and operating rules

## Recommended deployment model

Best setup for public GitHub distribution:

1. Open-source the scanner and scoring logic.
2. Require each operator to bring their own X Developer app and `xurl` authentication.
3. Run detection as a scheduled local job or self-hosted worker.
4. Produce a report of candidates first.
5. Only block after review, with an explicit `--execute` command.

This avoids shared credentials, avoids accidental mass blocking, and keeps every block action tied to the account owner who authorized it.

## X API rules this project follows

From the X API/xurl docs:

- Use Bearer/app or OAuth read context for public users/posts.
- Use OAuth user context for account actions like block/follow/mute.
- Request only needed fields with `user.fields`, `tweet.fields`, and `expansions`.
- Handle rate limits and 429 responses in production.
- Keep credentials outside source control.
- Do not use verbose auth output in AI/agent sessions because it can expose tokens.

## xurl authentication

Install `xurl` from the official X Developer Platform project, then authenticate outside this app.

```bash
xurl auth status
xurl whoami
```

If auth is missing, create an X Developer app and complete OAuth setup per the official `xurl` docs. Do not paste credentials into issue reports or chat logs.

## Detection workflow

1. Identify the protected account.
2. Search recent posts that mention the protected name/handle.
3. Expand `author_id` into user profiles.
4. Score each author against the protected account.
5. Review all `block_recommended` accounts manually.
6. Execute a block only for reviewed candidates.

## Why blocking is not fully automatic

False positives are expensive. News accounts, parody accounts, fan accounts, and legitimate support accounts can look similar by text alone. The project can recommend action, but the account owner should approve the final write action.

## Production hardening still needed

Before running this as a multi-user hosted service, add:

- OAuth app sign-in per tenant
- encrypted token storage
- per-account rate limiting
- audit log of every block decision
- appeal/allowlist support
- separate report-only and write roles
