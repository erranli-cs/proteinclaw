from __future__ import annotations

import argparse
from pathlib import Path

from proteinclaw.learning import export_learning_dataset
from proteinclaw.pipeline import run_campaign
from proteinclaw.scouting import run_heartbeat


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
    plan.add_argument(
        "--interactive",
        action="store_true",
        help="Ask the high-value clarification questions interactively.",
    )
    plan.add_argument(
        "--epitope",
        default=None,
        help="Optional clarification override for epitope selection.",
    )
    plan.add_argument(
        "--modality",
        default=None,
        help="Optional clarification override for modality selection.",
    )

    heartbeat = subparsers.add_parser("heartbeat", help="Write the scouting queue artifact.")
    heartbeat.add_argument("--root", default=".", help="Workspace root where artifacts should be written.")

    export = subparsers.add_parser("export-learning", help="Export a simple learning dataset from campaign artifacts.")
    export.add_argument("--root", default=".", help="Workspace root where artifacts should be read and written.")
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
            interactive=args.interactive,
            clarifications={key: value for key, value in {"epitope": args.epitope, "modality": args.modality}.items() if value is not None},
        )
        print(result["manifest"]["report_path"])
        return 0
    if args.command == "heartbeat":
        output = run_heartbeat(Path(args.root).resolve())
        print(output)
        return 0
    if args.command == "export-learning":
        output = export_learning_dataset(Path(args.root).resolve())
        print(output)
        return 0
    return 1
