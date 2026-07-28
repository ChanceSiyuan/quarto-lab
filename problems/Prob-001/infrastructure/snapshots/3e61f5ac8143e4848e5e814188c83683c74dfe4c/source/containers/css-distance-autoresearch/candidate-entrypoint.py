#!/usr/bin/env python3
"""Stable evaluator entrypoint: delegate to the candidate worktree program."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hx", required=True)
    parser.add_argument("--hz", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    program = Path("/candidate/candidate.py")
    if not program.is_file():
        print('{"status":"failed","reason":"missing_candidate_entrypoint"}')
        return 0
    completed = subprocess.run(
        [
            sys.executable,
            str(program),
            "--hx",
            args.hx,
            "--hz",
            args.hz,
            "--seed",
            str(args.seed),
            "--output-dir",
            args.output_dir,
        ],
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONUNBUFFERED": "1",
        },
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
