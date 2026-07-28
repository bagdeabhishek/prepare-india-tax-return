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
from extract_standard_tax import (
    EXTRACTOR_VERSION as STANDARD_EXTRACTOR_VERSION,
    extract_standard_record,
)

DEFAULT_JOBS = min(16, max(4, os.cpu_count() or 4))


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


def deterministic_path(workspace: Path, item: dict[str, Any]) -> Path:
    return (
        workspace
        / "deterministic-records"
        / item["source_id"]
        / f"{item['sha256']}.json"
    )


def run_standard_extractor(
    workspace: Path,
    item: dict[str, Any],
    envelope: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    record_path = deterministic_path(workspace, item)
    record, handled = extract_standard_record(
        envelope, source_id=item["source_id"]
    )
    record["extractor"]["standard_version"] = STANDARD_EXTRACTOR_VERSION
    record["extractor"]["version"] = item.get(
        "requested_extractor_version"
    ) or (
        f"parser-{PARSER_VERSION}_standard-"
        f"{STANDARD_EXTRACTOR_VERSION}"
    )
    record["source"]["normalized_document"]["path"] = str(output)
    atomic_json(record_path, record)
    incoming = Path(item["agent_output"])
    agent_output_ready = False
    if handled:
        atomic_json(incoming, record)
    elif incoming.exists():
        try:
            prior = load_json(incoming)
        except ValueError:
            prior = {}
        prior_source = prior.get("source", {})
        prior_extractor = prior.get("extractor", {})
        if (
            prior_source.get("sha256") != item["sha256"]
            or prior_extractor.get("name") == record["extractor"]["name"]
        ):
            incoming.unlink()
        else:
            agent_output_ready = True
    return {
        "document_type": record["source"]["document_type"],
        "deterministic_record": str(record_path),
        "deterministic_claims": len(record["claims"]),
        "deterministic_handled": handled,
        "agent_required": (
            record["automation"]["needs_semantic_agent"]
            and not agent_output_ready
        ),
        "agent_output_ready": agent_output_ready,
        "user_action_required": record["automation"]["user_action_required"],
        "standard_extractor_version": STANDARD_EXTRACTOR_VERSION,
    }


def clone_envelope(
    workspace: Path,
    item: dict[str, Any],
    envelope: dict[str, Any],
    *,
    duplicate_reused: bool,
) -> dict[str, Any]:
    output = normalized_path(workspace, item)
    cloned = json.loads(json.dumps(envelope))
    cloned["source"]["path"] = str(Path(item["path"]).resolve())
    cloned["source"]["sha256"] = item["sha256"]
    cloned["source"]["size"] = item["size"]
    atomic_json(output, cloned)
    result = {
        "source_id": item["source_id"],
        "status": cloned.get("status", "FAILED"),
        "normalized_output": str(output),
        "cached": True,
        "duplicate_reused": duplicate_reused,
    }
    result.update(run_standard_extractor(workspace, item, cloned, output))
    return result


def preprocess_one(
    workspace: Path,
    item: dict[str, Any],
    options: Options,
    force: bool,
) -> dict[str, Any]:
    output = normalized_path(workspace, item)
    duplicate_source = item.get("duplicate_content_of")
    if duplicate_source and not force:
        duplicate_output = (
            workspace
            / "normalized"
            / duplicate_source
            / f"{item['sha256']}.json"
        )
        if duplicate_output.exists():
            existing_duplicate = load_json(duplicate_output)
            if (
                existing_duplicate.get("source", {}).get("sha256")
                == item["sha256"]
                and existing_duplicate.get("parser", {}).get("version")
                == PARSER_VERSION
            ):
                return clone_envelope(
                    workspace,
                    item,
                    existing_duplicate,
                    duplicate_reused=True,
                )
    if output.exists() and not force:
        existing = load_json(output)
        if (
            existing.get("source", {}).get("sha256") == item["sha256"]
            and existing.get("parser", {}).get("version") == PARSER_VERSION
        ):
            result = {
                "source_id": item["source_id"],
                "status": existing.get("status", "FAILED"),
                "normalized_output": str(output),
                "cached": True,
                "duplicate_reused": False,
            }
            result.update(
                run_standard_extractor(
                    workspace, item, existing, output
                )
            )
            return result
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
    result = {
        "source_id": item["source_id"],
        "status": envelope["status"],
        "normalized_output": str(output),
        "cached": False,
        "duplicate_reused": False,
    }
    result.update(run_standard_extractor(workspace, item, envelope, output))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preprocess every item in a source-store work queue"
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
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
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(item["sha256"], []).append(item)
    representatives = [group[0] for group in groups.values()]
    workers = max(1, min(args.jobs, len(representatives) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                preprocess_one, workspace, item, options, args.force
            ): item
            for item in representatives
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

    for group in groups.values():
        representative = group[0]
        for item in group[1:]:
            try:
                envelope = load_json(normalized_path(workspace, representative))
                result = clone_envelope(
                    workspace,
                    item,
                    envelope,
                    duplicate_reused=True,
                )
            except Exception as exc:
                result = {
                    "source_id": item["source_id"],
                    "status": "FAILED",
                    "normalized_output": str(normalized_path(workspace, item)),
                    "cached": False,
                    "duplicate_reused": False,
                    "agent_required": False,
                    "user_action_required": True,
                    "error": f"duplicate reuse failed: {exc}",
                }
            results[item["source_id"]] = result

    for item in items:
        result = results[item["source_id"]]
        item["normalized_output"] = result["normalized_output"]
        item["normalization_status"] = result["status"]
        item["normalization_cached"] = result["cached"]
        item["duplicate_reused"] = result.get("duplicate_reused", False)
        item["document_type"] = result.get("document_type", "UNKNOWN")
        item["deterministic_record"] = result.get("deterministic_record")
        item["deterministic_claims"] = result.get("deterministic_claims", 0)
        item["deterministic_handled"] = result.get(
            "deterministic_handled", False
        )
        item["standard_extractor_version"] = result.get(
            "standard_extractor_version"
        )
        item["agent_required"] = result.get("agent_required", True)
        item["agent_output_ready"] = result.get("agent_output_ready", False)
        item["user_action_required"] = result.get(
            "user_action_required", False
        )
        if result.get("error"):
            item["normalization_error"] = result["error"]
        else:
            item.pop("normalization_error", None)
    atomic_json(queue_path, queue)
    semantic_items = [
        item for item in items if item.get("agent_required", True)
    ]
    atomic_json(
        workspace / "semantic_queue.json",
        {
            "schema_version": "1.0",
            "generated_by": (
                f"parser-{PARSER_VERSION}_standard-"
                f"{STANDARD_EXTRACTOR_VERSION}"
            ),
            "items": semantic_items,
        },
    )

    complete = sum(1 for result in results.values() if result["status"] == "COMPLETE")
    partial = sum(1 for result in results.values() if result["status"] == "PARTIAL")
    failed = sum(1 for result in results.values() if result["status"] == "FAILED")
    print(
        f"Preprocessed {len(items)} source(s): "
        f"{complete} complete, {partial} partial, {failed} failed"
    )
    print(
        f"Parsed {len(groups)} unique content hash(es); "
        f"reused {len(items) - len(groups)} duplicate(s)"
    )
    automated = sum(
        1 for item in items if item.get("deterministic_handled")
    )
    user_action = sum(
        1 for item in items if item.get("user_action_required")
    )
    print(
        f"Deterministic extraction completed {automated} source(s); "
        f"{len(semantic_items)} source(s) require one-file semantic agents; "
        f"{user_action} source(s) require user action"
    )
    print(f"Semantic queue: {workspace / 'semantic_queue.json'}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
