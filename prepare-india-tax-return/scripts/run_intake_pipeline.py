#!/usr/bin/env python3
"""Run the fast scan → normalize → rigid extract → merge → reassess pipeline."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from extract_standard_tax import EXTRACTOR_VERSION
from parse_source import PARSER_VERSION

DEFAULT_JOBS = min(16, max(4, os.cpu_count() or 4))


def run(command: list[str]) -> int:
    result = subprocess.run(command, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process ITR source files and produce only the residual agent queue"
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--source-dir", action="append", default=[])
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    parser.add_argument("--password-env")
    parser.add_argument("--ocr", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--replace-inventory", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.source and not args.source_dir:
        print("error: provide --source or --source-dir", file=sys.stderr)
        return 2
    scripts = Path(__file__).resolve().parent
    python = sys.executable
    extractor_version = (
        f"parser-{PARSER_VERSION}_standard-{EXTRACTOR_VERSION}"
    )

    scan = [
        python,
        str(scripts / "source_store.py"),
        "scan",
        "--workspace",
        str(args.workspace),
        "--extractor-version",
        extractor_version,
    ]
    for source in args.source:
        scan.extend(["--source", source])
    for directory in args.source_dir:
        scan.extend(["--source-dir", directory])
    if args.replace_inventory:
        scan.append("--replace-inventory")
    if args.force:
        scan.append("--force")
    if run(scan):
        return 2

    preprocess = [
        python,
        str(scripts / "preprocess_sources.py"),
        "--workspace",
        str(args.workspace),
        "--jobs",
        str(args.jobs),
        "--ocr",
        args.ocr,
    ]
    if args.password_env:
        preprocess.extend(["--password-env", args.password_env])
    if args.force:
        preprocess.append("--force")
    preprocess_status = run(preprocess)
    if preprocess_status not in {0, 2}:
        return preprocess_status

    if run(
        [
            python,
            str(scripts / "source_store.py"),
            "merge",
            "--workspace",
            str(args.workspace),
        ]
    ):
        return 2

    state_path = args.workspace.expanduser().resolve() / "intake_state.json"
    if state_path.exists():
        run(
            [
                python,
                str(scripts / "intake_manager.py"),
                "assess",
                "--workspace",
                str(args.workspace),
            ]
        )
    print(
        "\nDeterministic processing is complete. Dispatch one parallel agent per "
        "item remaining in semantic_queue.json; do not reprocess automated files."
    )
    return preprocess_status


if __name__ == "__main__":
    raise SystemExit(main())
