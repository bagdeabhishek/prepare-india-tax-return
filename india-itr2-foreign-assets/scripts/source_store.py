#!/usr/bin/env python3
"""Incremental, provenance-preserving source store for ITR workpapers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
MANIFEST = "manifest.json"
QUEUE = "work_queue.json"
CENTRAL = "central_store.json"
FACTS = "reconciled_facts.json"
INCOMING = "incoming"
RECORDS = "source-records"


class StoreError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise StoreError(f"Missing JSON file: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise StoreError(f"Invalid JSON in {path}: {exc}") from exc


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_source_id(path: Path) -> str:
    normalized = str(path.resolve()).encode("utf-8")
    return "src-" + hashlib.sha256(normalized).hexdigest()[:16]


def claim_id(
    source_id: str, source_sha256: str, extractor_version: str, local_id: str
) -> str:
    raw = (
        f"{source_id}\0{source_sha256}\0{extractor_version}\0{local_id}"
    ).encode("utf-8")
    return "claim-" + hashlib.sha256(raw).hexdigest()[:24]


def workspace_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def require_workspace(workspace: Path) -> dict[str, Any]:
    manifest_path = workspace / MANIFEST
    if not manifest_path.exists():
        raise StoreError(
            f"{workspace} is not initialized; run the init command first"
        )
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise StoreError("Unsupported manifest schema_version")
    return manifest


def init_workspace(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / INCOMING).mkdir(exist_ok=True)
    (workspace / RECORDS).mkdir(exist_ok=True)

    gitignore = workspace / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# Private taxpayer workpaper: do not commit anything here.\n*\n",
            encoding="utf-8",
        )

    manifest_path = workspace / MANIFEST
    if not manifest_path.exists():
        atomic_json(
            manifest_path,
            {
                "schema_version": SCHEMA_VERSION,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "sources": [],
            },
        )
    if not (workspace / FACTS).exists():
        atomic_json(
            workspace / FACTS,
            {"schema_version": SCHEMA_VERSION, "facts": []},
        )
    if not (workspace / CENTRAL).exists():
        atomic_json(
            workspace / CENTRAL,
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": None,
                "sources": [],
                "claims": [],
                "reconciled_facts": [],
                "pending_sources": [],
                "warnings": [],
            },
        )
    print(f"Initialized private source store: {workspace}")


def iter_source_paths(args: argparse.Namespace, workspace: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []
    for raw in args.source or []:
        candidates.append(Path(raw).expanduser())
    for raw in args.source_dir or []:
        source_dir = Path(raw).expanduser()
        if not source_dir.is_dir():
            raise StoreError(f"Source directory not found: {source_dir}")
        candidates.extend(path for path in source_dir.rglob("*") if path.is_file())

    for candidate in sorted(candidates, key=lambda item: str(item)):
        resolved = candidate.resolve()
        if workspace == resolved or workspace in resolved.parents:
            continue
        if resolved in seen:
            continue
        if not resolved.is_file():
            raise StoreError(f"Source file not found: {resolved}")
        seen.add(resolved)
        yield resolved


def scan_sources(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    manifest = require_workspace(workspace)
    existing = {item["source_id"]: item for item in manifest.get("sources", [])}
    by_hash: dict[str, str] = {
        item["sha256"]: item["source_id"]
        for item in existing.values()
        if item.get("sha256")
    }
    queue: list[dict[str, Any]] = []
    found = False
    scanned_ids: set[str] = set()

    for path in iter_source_paths(args, workspace):
        found = True
        stat = path.stat()
        digest = sha256_file(path)
        source_id = stable_source_id(path)
        scanned_ids.add(source_id)
        old = existing.get(source_id, {})
        version_changed = old.get("sha256") != digest
        if (
            version_changed
            and old.get("sha256")
            and by_hash.get(old["sha256"]) == source_id
        ):
            by_hash.pop(old["sha256"], None)
        record_rel = f"{RECORDS}/{source_id}/{digest}.json"
        incoming_rel = f"{INCOMING}/{source_id}.json"
        record_ready = (workspace / record_rel).is_file()
        extractor_changed = False
        if record_ready and args.extractor_version:
            prior_record = load_json(workspace / record_rel)
            extractor_changed = (
                prior_record.get("extractor", {}).get("version")
                != args.extractor_version
            )
        requires_extraction = (
            args.force or version_changed or extractor_changed or not record_ready
        )
        duplicate_of = by_hash.get(digest)
        if duplicate_of == source_id:
            duplicate_of = None

        entry = {
            "source_id": source_id,
            "path": str(path),
            "sha256": digest,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "previous_sha256": old.get("sha256") if version_changed else None,
            "state": "pending" if requires_extraction else "ready",
            "record": record_rel if record_ready and not requires_extraction else None,
            "expected_record": record_rel,
            "agent_output": incoming_rel,
            "requested_extractor_version": args.extractor_version,
            "duplicate_content_of": duplicate_of,
            "last_scanned_at": utc_now(),
        }
        existing[source_id] = entry
        by_hash.setdefault(digest, source_id)

        if requires_extraction:
            if args.force:
                reason = "forced"
            elif version_changed:
                reason = "changed" if old else "new"
            elif extractor_changed:
                reason = "extractor_changed"
            else:
                reason = "new"
            queue.append(
                {
                    "source_id": source_id,
                    "path": str(path),
                    "sha256": digest,
                    "size": stat.st_size,
                    "state": reason,
                    "previous_sha256": old.get("sha256") if version_changed else None,
                    "requested_extractor_version": args.extractor_version,
                    "agent_output": str(workspace / incoming_rel),
                }
            )

    if not found:
        raise StoreError("No source files were supplied or discovered")

    if args.replace_inventory:
        for source_id, entry in existing.items():
            if source_id not in scanned_ids:
                entry["state"] = "inactive"
                entry["record"] = None
                entry["inactivated_at"] = utc_now()

    manifest["updated_at"] = utc_now()
    manifest["sources"] = sorted(existing.values(), key=lambda item: item["source_id"])
    atomic_json(workspace / MANIFEST, manifest)
    atomic_json(
        workspace / QUEUE,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "items": queue,
        },
    )
    print(
        f"Scanned {sum(1 for _ in manifest['sources'])} active paths; "
        f"{len(queue)} source(s) require extraction"
    )
    print(f"Work queue: {workspace / QUEUE}")


def validate_source_record(
    record: dict[str, Any], manifest_source: dict[str, Any]
) -> None:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise StoreError("Source record has unsupported schema_version")
    source = record.get("source")
    extractor = record.get("extractor")
    claims = record.get("claims")
    if not isinstance(source, dict) or not isinstance(extractor, dict):
        raise StoreError("Source record requires source and extractor objects")
    if not isinstance(claims, list):
        raise StoreError("Source record requires a claims array")
    for key in ("source_id", "path", "sha256"):
        if source.get(key) != manifest_source.get(key):
            raise StoreError(
                f"Source record {key} does not match manifest for "
                f"{manifest_source['source_id']}"
            )
    for key in ("name", "version", "extracted_at"):
        if not extractor.get(key):
            raise StoreError(f"Source record extractor.{key} is required")

    local_ids: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise StoreError(f"Claim {index} is not an object")
        for key in ("local_id", "kind", "values", "evidence"):
            if key not in claim:
                raise StoreError(f"Claim {index} is missing {key}")
        local_id = claim["local_id"]
        if not isinstance(local_id, str) or not local_id:
            raise StoreError(f"Claim {index} has an invalid local_id")
        if local_id in local_ids:
            raise StoreError(f"Duplicate local_id in source record: {local_id}")
        local_ids.add(local_id)
        if not isinstance(claim["values"], dict):
            raise StoreError(f"Claim {local_id} values must be an object")
        if not isinstance(claim["evidence"], dict):
            raise StoreError(f"Claim {local_id} evidence must be an object")


def normalized_record(
    record: dict[str, Any], manifest_source: dict[str, Any]
) -> dict[str, Any]:
    output = dict(record)
    source = dict(record["source"])
    source.update(
        {
            "source_id": manifest_source["source_id"],
            "path": manifest_source["path"],
            "sha256": manifest_source["sha256"],
            "size": manifest_source["size"],
            "mtime_ns": manifest_source["mtime_ns"],
        }
    )
    output["source"] = source
    output.setdefault("warnings", [])
    return output


def stage_incoming(workspace: Path, manifest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for source in manifest.get("sources", []):
        incoming = workspace / source["agent_output"]
        if not incoming.exists():
            continue
        record = load_json(incoming)
        try:
            current_hash = sha256_file(Path(source["path"]))
        except FileNotFoundError:
            warnings.append(f"Source missing during merge: {source['path']}")
            source["state"] = "missing"
            continue
        if current_hash != source["sha256"]:
            warnings.append(
                f"Source changed after scan and must be rescanned: {source['path']}"
            )
            source["state"] = "changed_after_scan"
            continue
        validate_source_record(record, source)
        destination = workspace / source["expected_record"]
        atomic_json(destination, normalized_record(record, source))
        source["record"] = source["expected_record"]
        source["state"] = "ready"
        incoming.unlink()
    return warnings


def build_claims(
    workspace: Path, manifest: dict[str, Any], warnings: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for source in manifest.get("sources", []):
        record_rel = source.get("record")
        if source.get("state") != "ready" or not record_rel:
            pending.append(
                {
                    "source_id": source["source_id"],
                    "path": source["path"],
                    "sha256": source["sha256"],
                    "state": source.get("state", "pending"),
                }
            )
            continue
        record_path = workspace / record_rel
        if not record_path.exists():
            source["state"] = "pending"
            source["record"] = None
            pending.append(
                {
                    "source_id": source["source_id"],
                    "path": source["path"],
                    "sha256": source["sha256"],
                    "state": "missing_record",
                }
            )
            continue
        record = load_json(record_path)
        validate_source_record(record, source)
        doc_type = record["source"].get("document_type", "unknown")
        for claim in record["claims"]:
            item = dict(claim)
            item["claim_id"] = claim_id(
                source["source_id"],
                source["sha256"],
                record["extractor"]["version"],
                claim["local_id"],
            )
            item["provenance"] = {
                "source_id": source["source_id"],
                "source_sha256": source["sha256"],
                "source_path": source["path"],
                "document_type": doc_type,
                "local_id": claim["local_id"],
                "evidence": claim["evidence"],
                "extractor": record["extractor"],
            }
            claims.append(item)
        for warning in record.get("warnings", []):
            warnings.append(f"{source['source_id']}: {warning}")
    claims.sort(key=lambda item: item["claim_id"])
    return claims, pending


def merge_store(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    manifest = require_workspace(workspace)
    warnings = stage_incoming(workspace, manifest)
    claims, pending = build_claims(workspace, manifest, warnings)
    active_ids = {item["claim_id"] for item in claims}

    facts_payload = load_json(
        workspace / FACTS,
        default={"schema_version": SCHEMA_VERSION, "facts": []},
    )
    if facts_payload.get("schema_version") != SCHEMA_VERSION:
        raise StoreError("Unsupported reconciled_facts schema_version")
    facts: list[dict[str, Any]] = []
    for fact in facts_payload.get("facts", []):
        item = dict(fact)
        dependencies = set(item.get("depends_on", []))
        missing = sorted(dependencies - active_ids)
        if missing:
            item["status"] = "STALE"
            item["missing_dependencies"] = missing
        else:
            item.pop("missing_dependencies", None)
        facts.append(item)
    facts.sort(key=lambda item: item.get("fact_id", ""))

    manifest["updated_at"] = utc_now()
    atomic_json(workspace / MANIFEST, manifest)
    atomic_json(
        workspace / CENTRAL,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "sources": manifest.get("sources", []),
            "claims": claims,
            "reconciled_facts": facts,
            "pending_sources": pending,
            "warnings": sorted(set(warnings)),
        },
    )
    stale = sum(1 for fact in facts if fact.get("status") == "STALE")
    print(
        f"Merged {len(claims)} claim(s) from "
        f"{len(manifest.get('sources', [])) - len(pending)} ready source(s)"
    )
    print(f"Pending sources: {len(pending)}; stale facts: {stale}")
    print(f"Central store: {workspace / CENTRAL}")


def validate_facts(payload: dict[str, Any], active_ids: set[str]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise StoreError("Facts file has unsupported schema_version")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise StoreError("Facts file requires a facts array")
    fact_ids: set[str] = set()
    allowed_status = {
        "RECONCILED",
        "PROVISIONAL",
        "ASSUMPTION",
        "UNRESOLVED",
        "STALE",
    }
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise StoreError(f"Fact {index} is not an object")
        for key in (
            "fact_id",
            "kind",
            "values",
            "depends_on",
            "derivation",
            "status",
        ):
            if key not in fact:
                raise StoreError(f"Fact {index} is missing {key}")
        if fact["fact_id"] in fact_ids:
            raise StoreError(f"Duplicate fact_id: {fact['fact_id']}")
        fact_ids.add(fact["fact_id"])
        if fact["status"] not in allowed_status:
            raise StoreError(f"Invalid status for fact {fact['fact_id']}")
        if not isinstance(fact["depends_on"], list):
            raise StoreError(f"depends_on must be an array for {fact['fact_id']}")
        missing = set(fact["depends_on"]) - active_ids
        if missing and fact["status"] != "STALE":
            raise StoreError(
                f"Fact {fact['fact_id']} has unknown dependencies: "
                f"{', '.join(sorted(missing))}"
            )
        if not fact["depends_on"] and fact["status"] != "ASSUMPTION":
            raise StoreError(
                f"Fact {fact['fact_id']} has no source dependencies; "
                "label it ASSUMPTION or add claim IDs"
            )


def set_facts(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    require_workspace(workspace)
    central = load_json(workspace / CENTRAL)
    active_ids = {item["claim_id"] for item in central.get("claims", [])}
    payload = load_json(Path(args.input).expanduser().resolve())
    validate_facts(payload, active_ids)
    atomic_json(workspace / FACTS, payload)
    print(f"Stored {len(payload['facts'])} reconciled fact(s)")
    merge_store(argparse.Namespace(workspace=str(workspace)))


def status(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    require_workspace(workspace)
    central = load_json(workspace / CENTRAL)
    sources = central.get("sources", [])
    ready = sum(1 for item in sources if item.get("state") == "ready")
    facts = central.get("reconciled_facts", [])
    stale = sum(1 for item in facts if item.get("status") == "STALE")
    summary = {
        "workspace": str(workspace),
        "sources_total": len(sources),
        "sources_ready": ready,
        "sources_pending": len(central.get("pending_sources", [])),
        "claims": len(central.get("claims", [])),
        "reconciled_facts": len(facts),
        "stale_facts": stale,
        "warnings": len(central.get("warnings", [])),
        "generated_at": central.get("generated_at"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Maintain an incremental ITR source-extraction store"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a private store")
    init_parser.add_argument("--workspace", required=True)
    init_parser.set_defaults(func=init_workspace)

    scan_parser = subparsers.add_parser(
        "scan", help="Hash sources and queue new or changed files"
    )
    scan_parser.add_argument("--workspace", required=True)
    scan_parser.add_argument("--source", action="append")
    scan_parser.add_argument("--source-dir", action="append")
    scan_parser.add_argument(
        "--extractor-version",
        help="Queue records produced by a different extractor version",
    )
    scan_parser.add_argument(
        "--force", action="store_true", help="Queue every supplied source"
    )
    scan_parser.add_argument(
        "--replace-inventory",
        action="store_true",
        help="Mark previously known but unscanned sources inactive",
    )
    scan_parser.set_defaults(func=scan_sources)

    merge_parser = subparsers.add_parser(
        "merge", help="Stage worker outputs and rebuild the central store"
    )
    merge_parser.add_argument("--workspace", required=True)
    merge_parser.set_defaults(func=merge_store)

    facts_parser = subparsers.add_parser(
        "set-facts", help="Store reconciled facts and validate dependencies"
    )
    facts_parser.add_argument("--workspace", required=True)
    facts_parser.add_argument("--input", required=True)
    facts_parser.set_defaults(func=set_facts)

    status_parser = subparsers.add_parser("status", help="Show store status")
    status_parser.add_argument("--workspace", required=True)
    status_parser.set_defaults(func=status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except StoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
