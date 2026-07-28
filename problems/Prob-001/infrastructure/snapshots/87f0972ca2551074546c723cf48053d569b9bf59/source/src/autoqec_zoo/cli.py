from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from autoqec_zoo.build import build_zoo
from autoqec_zoo.eczoo import build_eczoo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoqec-zoo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Validate and build Zoo artifacts")
    build_parser.add_argument("--root", default="zoo", help="Path to the zoo root directory")
    build_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Generation date for built artifacts",
    )

    eczoo_parser = subparsers.add_parser(
        "eczoo", help="Build the eczoo mirror index and views"
    )
    eczoo_parser.add_argument("--root", default="zoo", help="Path to the zoo root directory")
    eczoo_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Generation date for built artifacts",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"zoo root does not exist: {root}")
        build_zoo(root, generated_at=args.date)
        print(f"built zoo artifacts under {root}")
        return 0

    if args.command == "eczoo":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"zoo root does not exist: {root}")
        result = build_eczoo(root, generated_at=args.date)
        print(
            f"built eczoo mirror: {result['indexed_count']} codes, "
            f"{result['edge_count']} edges, {result['skipped_count']} skipped"
        )
        if result["skipped"]:
            print("skipped files:")
            for line in result["skipped"]:
                print(f"  - {line}")
        if result["unresolved"]:
            print(f"unresolved relation targets: {len(result['unresolved'])}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
