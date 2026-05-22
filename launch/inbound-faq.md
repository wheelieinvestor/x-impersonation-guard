# Inbound FAQ

## Does this work for me if I am not a developer?

The alpha is CLI-first. If you are comfortable installing Python packages and editing a config file, yes. A hosted version is later-roadmap work.

## Will you build this for Threads, Bluesky, or Instagram?

Those are on the roadmap. The architecture supports platform-specific detectors and reporters, but each platform needs separate work.

## Can you scan my account for me?

No. The tool is designed to run locally on your machine so credentials, browser profiles, and evidence stay with you.

## Is this safe to run?

Fixture mode is safe: no live X calls and no reports submitted. Live mode is review-first and dry-run-first by default. Read `SECURITY.md` and `docs/status.md`.

## Can this be misused to mass-report enemies?

That is explicitly outside the project boundary. The scoring model includes mitigations for parody/fan accounts, live reports require approval by default, and the docs make misuse unacceptable.

## Does X remove the accounts?

X decides enforcement. The tool files structured reports and keeps evidence/audit packages.
