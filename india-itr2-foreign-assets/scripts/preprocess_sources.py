#!/usr/bin/env python3
"""Normalize every queued source without per-file custom parsing scripts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from parse_source import (
    PARSER_VERSION,
    Limits,
    Options,
    atomic_json,
    parse_path,
)


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def normalized_path(workspace: Path, item: dict[str, Any]) -> Path:
    supplied = item.get("normalized_output")
    if supplied:
        return Path(supplied)
    return (
        workspace
        / "normalized"
        / item["source_id"]
        / f"{item['sha256']}.json"
    )


def preprocess_one(
    workspace: Path,
    item: dict[str, Any],
    options: Options,
    force: bool,
) -> dict[str, Any]:
    output = normalized_path(workspace, item)
    if output.exists() and not force:
        existing = load_json(output)
        if (
            existing.get("source", {}).get("sha256") == item["sha256"]
            and existing.get("parser", {}).get("version") == PARSER_VERSION
        ):
            return {
                "source_id": item["source_id"],
                "status": existing.get("status", "FAILED"),
                "normalized_output": str(output),
                "cached": True,
            }
    envelope = parse_path(Path(item["path"]), options)
    if envelope["source"]["sha256"] != item["sha256"]:
        return {
            "source_id": item["source_id"],
            "status": "FAILED",
            "normalized_output": str(output),
            "cached": False,
            "error": "source changed after scan; rescan before preprocessing",
        }
    atomic_json(output, envelope)
    return {
        "source_id": item["source_id"],
        "status": envelope["status"],
        "normalized_output": str(output),
        "cached": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preprocess every item in a source-store work queue"
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--password-env")
    parser.add_argument(
        "--ocr", choices=("auto", "always", "never"), default="auto"
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-rows", type=int, default=Limits.max_rows)
    parser.add_argument(
        "--max-json-leaves", type=int, default=Limits.max_json_leaves
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.expanduser().resolve()
    queue_path = workspace / "work_queue.json"
    try:
        queue = load_json(queue_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    items = queue.get("items")
    if not isinstance(items, list):
        print("error: work_queue.json has no items array", file=sys.stderr)
        return 2
    password = os.environ.get(args.password_env) if args.password_env else None
    if args.password_env and password is None:
        print(
            f"error: environment variable {args.password_env!r} is not set",
            file=sys.stderr,
        )
        return 2
    options = Options(
        password=password,
        ocr=args.ocr,
        limits=Limits(
            max_rows=args.max_rows,
            max_json_leaves=args.max_json_leaves,
        ),
    )
    results: dict[str, dict[str, Any]] = {}
    workers = max(1, min(args.jobs, len(items) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                preprocess_one, workspace, item, options, args.force
            ): item
            for item in items
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "source_id": item["source_id"],
                    "status": "FAILED",
                    "normalized_output": str(normalized_path(workspace, item)),
                    "cached": False,
                    "error": str(exc),
                }
            results[item["source_id"]] = result

    for item in items:
        result = results[item["source_id"]]
        item["normalized_output"] = result["normalized_output"]
        item["normalization_status"] = result["status"]
        item["normalization_cached"] = result["cached"]
        if result.get("error"):
            item["normalization_error"] = result["error"]
        else:
            item.pop("normalization_error", None)
    atomic_json(queue_path, queue)

    complete = sum(1 for result in results.values() if result["status"] == "COMPLETE")
    partial = sum(1 for result in results.values() if result["status"] == "PARTIAL")
    failed = sum(1 for result in results.values() if result["status"] == "FAILED")
    print(
        f"Preprocessed {len(items)} source(s): "
        f"{complete} complete, {partial} partial, {failed} failed"
    )
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
