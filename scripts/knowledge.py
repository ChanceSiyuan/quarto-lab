#!/usr/bin/env python3
"""Human- and agent-facing commands for trusted knowledge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from lib.knowledge import (
    build_knowledge_site,
    preview_knowledge_site,
    resolve_knowledge,
    validate_knowledge,
)


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate trusted knowledge")
    check.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    resolve = subparsers.add_parser("resolve", help="resolve a trusted reading bundle")
    resolve.add_argument("--query", required=True)
    resolve.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    build = subparsers.add_parser(
        "build",
        help="safely render and atomically publish trusted knowledge",
    )
    build.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    preview = subparsers.add_parser(
        "preview",
        help="preview the same validated execution-disabled projection",
    )
    preview.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        report = validate_knowledge(args.repo_root)
        if not report.ok:
            for diagnostic in report.diagnostics:
                print(diagnostic, file=sys.stderr)
            return 1
        print(
            f"Knowledge valid: {len(report.graph.pages)} pages "
            f"across {len(report.graph.topics)} topics."
        )
        return 0
    if args.command == "resolve":
        try:
            result = resolve_knowledge(args.query, args.repo_root)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "build":
        try:
            output = build_knowledge_site(repo_root=args.repo_root)
        except (
            OSError,
            RuntimeError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            print(error, file=sys.stderr)
            return 1
        relative_output = output.relative_to(args.repo_root)
        print(f"Knowledge site built: {relative_output.as_posix()}")
        return 0
    if args.command == "preview":
        try:
            preview_knowledge_site(repo_root=args.repo_root)
        except (
            OSError,
            RuntimeError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            print(error, file=sys.stderr)
            return 1
        print("Knowledge preview stopped.")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
