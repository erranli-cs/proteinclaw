from __future__ import annotations

import argparse
from pathlib import Path

from proteinclaw.pipeline import run_campaign


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proteinclaw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Run a minimal Clawd campaign.")
    plan.add_argument("--prompt", required=True, help="Natural-language campaign prompt.")
    plan.add_argument(
        "--execution-mode",
        choices=("academic", "commercial_safe"),
        default="academic",
        help="License-aware execution mode.",
    )
    plan.add_argument(
        "--root",
        default=".",
        help="Workspace root where artifacts should be written.",
    )
    plan.add_argument(
        "--use-fixture",
        action="store_true",
        help="Use bundled fixture data instead of live network retrieval.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "plan":
        result = run_campaign(
            prompt=args.prompt,
            root=Path(args.root).resolve(),
            execution_mode=args.execution_mode,
            use_fixture=args.use_fixture,
        )
        print(result["manifest"]["report_path"])
        return 0
    return 1
