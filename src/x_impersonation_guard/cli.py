"""Command line interface for X Impersonation Guard."""

import json
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ValidationError

from x_impersonation_guard.detection import DetectionConfig, score_candidate
from x_impersonation_guard.models import AccountProfile, DetectionResult
from x_impersonation_guard.xurl_client import XurlClient, XurlError


class FixtureScan(BaseModel):
    """Offline fixture format for repeatable scans and tests."""

    protected: AccountProfile
    candidates: list[AccountProfile]


def build_parser() -> ArgumentParser:
    """Build the command line parser."""

    parser = ArgumentParser(prog="x-impersonation-guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_fixture = subparsers.add_parser(
        "scan-fixture",
        help="Score candidate accounts from a local JSON fixture; no live API calls.",
    )
    scan_fixture.add_argument("--input", required=True, type=Path)
    scan_fixture.add_argument(
        "--block-threshold",
        default=80,
        type=int,
        help="Score at or above this value gets block_recommended.",
    )

    block = subparsers.add_parser(
        "block",
        help=(
            "Block a reviewed target ID through xurl; dry-run unless --execute is set."
        ),
    )
    block.add_argument("--target-user-id", required=True)
    block.add_argument("--authenticated-user-id", required=True)
    block.add_argument("--execute", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan-fixture":
        return _scan_fixture(args.input, args.block_threshold)
    if args.command == "block":
        return _block(
            target_user_id=args.target_user_id,
            authenticated_user_id=args.authenticated_user_id,
            execute=args.execute,
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


def _scan_fixture(input_path: Path, block_threshold: int) -> int:
    try:
        scan = FixtureScan.model_validate_json(input_path.read_text())
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        print(f"Fixture invalid: {exc}", file=sys.stderr)
        return 1

    config = DetectionConfig(block_threshold=block_threshold)
    results = [
        score_candidate(scan.protected, candidate, config)
        for candidate in scan.candidates
    ]
    print(_render_report(scan.protected, results))
    print("No accounts were blocked. Re-run a reviewed block action with --execute.")
    return 0


def _block(*, target_user_id: str, authenticated_user_id: str, execute: bool) -> int:
    client = XurlClient(authenticated_user_id=authenticated_user_id)
    try:
        result = client.block_user(target_user_id, execute=execute)
    except (XurlError, json.JSONDecodeError) as exc:
        print(f"Block failed closed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    if not execute:
        print("Dry run only. No accounts were blocked.")
    return 0


def _render_report(protected: AccountProfile, results: list[DetectionResult]) -> str:
    lines = [
        f"X Impersonation Guard report for @{protected.username}",
        "",
    ]
    for result in sorted(results, key=lambda item: item.score, reverse=True):
        lines.extend(
            [
                f"@{result.candidate.username}: {result.action} ({result.score}/100)",
                f"  id: {result.candidate.id}",
                f"  reasons: {', '.join(result.reasons) or 'none'}",
                f"  mitigations: {', '.join(result.mitigations) or 'none'}",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
