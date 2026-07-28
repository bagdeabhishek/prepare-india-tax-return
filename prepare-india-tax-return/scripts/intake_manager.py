#!/usr/bin/env python3
"""Manage staged, evidence-driven document intake for an Indian ITR workpaper."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from source_store import (
    CENTRAL,
    SCHEMA_VERSION,
    StoreError,
    atomic_json,
    init_workspace,
    load_json,
    require_workspace,
    workspace_path,
)


STATE = "intake_state.json"
REQUESTS = "document_requests.json"
VERIFIED_AL_THRESHOLDS = {"2026-27": Decimal(10_000_000)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


INITIAL_REQUESTS = [
    {
        "request_id": "initial-form16",
        "priority": "REQUIRED_IF_SALARIED",
        "document": "Form 16 Part A and Part B for every employer",
        "accepted": ["PDF", "separate Part A/Part B PDFs", "12BA annexure"],
        "reason": "salary, perquisites, deductions, TDS, and employer reconciliation",
    },
    {
        "request_id": "initial-ais",
        "priority": "REQUIRED",
        "document": "Annual Information Statement (AIS)",
        "accepted": ["decrypted AIS JSON", "AIS PDF"],
        "reason": "payer-level income, securities, TDS/TCS, and activity signals",
    },
    {
        "request_id": "initial-tis",
        "priority": "REQUIRED",
        "document": "Taxpayer Information Summary (TIS)",
        "accepted": ["PDF"],
        "reason": "category totals and processed-value reconciliation",
    },
    {
        "request_id": "initial-prefill",
        "priority": "RECOMMENDED",
        "document": "Fresh official portal prefill JSON",
        "accepted": ["JSON downloaded from the filing portal"],
        "reason": "portal values, Form 24Q, 26AS-derived credits, and filing profile",
    },
    {
        "request_id": "initial-26as",
        "priority": "RECOMMENDED",
        "document": "Form 26AS / tax credit statement",
        "accepted": ["PDF", "text", "spreadsheet"],
        "reason": "final TDS/TCS and tax-payment credit control",
    },
]


def parse_fact(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        raise ValueError("fact must use KEY=VALUE")
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        raise ValueError("fact key is blank")
    lowered = value.lower()
    if lowered in {"yes", "true", "y"}:
        parsed: Any = True
    elif lowered in {"no", "false", "n"}:
        parsed = False
    elif lowered in {"unknown", "unresolved"}:
        parsed = "UNRESOLVED"
    else:
        try:
            parsed = int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value
    return key, parsed


def load_state(workspace: Path) -> dict[str, Any]:
    return load_json(workspace / STATE)


def save_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_json(workspace / STATE, state)


def start(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    if not (workspace / "manifest.json").exists():
        init_workspace(argparse.Namespace(workspace=str(workspace)))
    else:
        require_workspace(workspace)
    state_path = workspace / STATE
    if state_path.exists() and not args.force:
        raise StoreError(
            f"{state_path} already exists; use --force only to restart intake"
        )
    state = {
        "schema_version": SCHEMA_VERSION,
        "assessment_year": args.assessment_year,
        "phase": "INITIAL_DOCUMENTS",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "facts": {},
        "history": [],
    }
    save_state(workspace, state)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": "INITIAL_DOCUMENTS",
        "requests": INITIAL_REQUESTS,
        "questions": [
            "Which income heads apply: salary, house property, capital gains, business/profession, or other sources?",
            "Are there multiple employers or multiple Form 16 sets?",
            "Did you have business/professional income, F&O, intraday trading, or presumptive income?",
            "Are any files password-protected? Provide passwords separately, never in filenames.",
        ],
    }
    atomic_json(workspace / REQUESTS, payload)
    print_requests(payload)
    print(f"\nMachine-readable checklist: {workspace / REQUESTS}")


def record(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    require_workspace(workspace)
    state = load_state(workspace)
    key, value = parse_fact(args.fact)
    state.setdefault("facts", {})[key] = {
        "value": value,
        "basis": args.basis or "taxpayer confirmation",
        "recorded_at": utc_now(),
    }
    state.setdefault("history", []).append(
        {"event": "FACT_RECORDED", "key": key, "at": utc_now()}
    )
    save_state(workspace, state)
    print(f"Recorded {key}={value!r}")


def fact_value(state: dict[str, Any], key: str, default: Any = None) -> Any:
    item = state.get("facts", {}).get(key)
    if isinstance(item, dict):
        return item.get("value", default)
    return default


def available_records(workspace: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for root in ("deterministic-records", "source-records"):
        directory = workspace / root
        if not directory.exists():
            continue
        for path in directory.rglob("*.json"):
            try:
                payload = load_json(path)
            except StoreError:
                continue
            source = payload.get("source", {})
            key = (str(source.get("source_id")), str(source.get("sha256")))
            if key in seen:
                continue
            seen.add(key)
            records.append(payload)
    central_path = workspace / CENTRAL
    if central_path.exists():
        central = load_json(central_path)
        # Claims are already represented by source records; central is used only
        # when a manually extracted record is absent from the deterministic tree.
        known_sources = {key[0] for key in seen}
        for source in central.get("sources", []):
            if source.get("source_id") not in known_sources:
                records.append(
                    {
                        "source": {
                            "source_id": source.get("source_id"),
                            "sha256": source.get("sha256"),
                            "document_type": "UNKNOWN",
                        },
                        "claims": [],
                    }
                )
    return records


def claim_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for record in records
        for item in record.get("claims", [])
        if isinstance(item, dict)
    ]


def numeric_claim(claims: list[dict[str, Any]], fields: set[str]) -> Decimal:
    total = Decimal(0)
    for item in claims:
        for key, raw in item.get("values", {}).items():
            if key not in fields:
                continue
            try:
                total += Decimal(str(raw).replace(",", ""))
            except (InvalidOperation, ValueError):
                pass
    return total


def request(
    request_id: str,
    document: str,
    reason: str,
    *,
    priority: str = "REQUIRED_IF_APPLICABLE",
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "priority": priority,
        "document": document,
        "reason": reason,
    }


def next_requests(
    state: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    document_types = {
        str(record.get("source", {}).get("document_type", "UNKNOWN"))
        for record in records
    }
    claims = claim_entries(records)
    requests: list[dict[str, Any]] = []
    questions: list[str] = []

    has_form16 = bool(
        document_types & {"FORM16", "FORM16_PART_A", "FORM16_PART_B"}
    )
    has_ais = bool(document_types & {"AIS", "AIS_JSON"})
    has_encrypted_ais = "AIS_ENCRYPTED_EXPORT" in document_types
    has_tis = "TIS" in document_types
    has_prefill = "ITR_PREFILL" in document_types
    salary_income = fact_value(state, "salary_income")

    if not has_form16 and salary_income is not False:
        requests.append(INITIAL_REQUESTS[0])
        if salary_income is None:
            questions.append(
                "Did you receive salary or pension reported through an employer "
                "during the financial year?"
            )
    if not has_ais:
        requests.append(INITIAL_REQUESTS[1])
        if has_encrypted_ais:
            requests[-1] = dict(requests[-1])
            requests[-1]["reason"] = (
                "the supplied AIS JSON is encrypted; provide a decrypted export "
                "or AIS PDF"
            )
    if not has_tis:
        requests.append(INITIAL_REQUESTS[2])
    if not has_prefill:
        requests.append(INITIAL_REQUESTS[3])

    initial_complete = has_ais and has_tis and (
        has_form16 or salary_income is False
    )
    if not initial_complete:
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": "INITIAL_DOCUMENTS",
            "requests": requests,
            "questions": questions,
            "observed_document_types": sorted(document_types),
        }

    perquisites = numeric_claim(claims, {"perquisites", "total_perquisites"})
    capital_gains = numeric_claim(claims, {"capital_gains"})
    interest = numeric_claim(
        claims, {"savings_interest", "term_deposit_interest"}
    )
    foreign_tax = numeric_claim(
        claims, {"foreign_tax_paid", "federal_tax_withheld_usd"}
    )
    total_income = numeric_claim(claims, {"total_income"})

    equity_comp = fact_value(state, "equity_compensation")
    foreign_holdings = fact_value(state, "foreign_holdings")
    actual_sales = fact_value(state, "capital_asset_sales")
    home_loan = fact_value(state, "home_loan")
    under_construction = fact_value(state, "property_under_construction")
    business_income = fact_value(state, "business_income")
    brought_forward_losses = fact_value(state, "brought_forward_losses")

    if business_income is None:
        questions.append(
            "Did you have business/professional income, F&O, intraday trading, "
            "or presumptive income during the financial year?"
        )
    if business_income is True:
        requests.extend(
            [
                request(
                    "business-books",
                    "Business/professional profit and loss account, balance sheet, ledgers, and bank statements",
                    "determine ITR-3/ITR-4 eligibility and support business-income schedules",
                ),
                request(
                    "business-compliance",
                    "GST returns, TDS records, presumptive-income working, and tax-audit report if applicable",
                    "reconcile turnover/receipts and identify audit or presumptive-filing conditions",
                ),
            ]
        )

    if perquisites > 0 and equity_comp is None:
        questions.append(
            "Form 16 shows perquisites. Did any amount arise from RSUs, ESPP, "
            "foreign shares, or another employee-equity plan?"
        )
    if equity_comp is True or perquisites > 0:
        if "FORM12BA" not in document_types:
            requests.append(
                request(
                    "salary-form12ba",
                    "Form 12BA / employer perquisite annexure",
                    "reconcile the nature and taxable value of salary perquisites",
                )
            )
        requests.append(
            request(
                "equity-vest-plan",
                "RSU/ESPP vest reports, grant/plan statements, and payroll equity details",
                "construct acquisition lots and distinguish payroll withholding",
            )
        )

    foreign_signal = (
        foreign_holdings is True
        or foreign_tax > 0
        or "FORM1042S" in document_types
        or any(
            item.get("values", {}).get("category") == "foreign_remittance"
            for item in claims
        )
    )
    if foreign_holdings is None and not foreign_signal:
        questions.append(
            "At any time in the relevant periods, did you hold a foreign bank, "
            "brokerage/custodial account, foreign shares, or receive foreign income?"
        )
    if foreign_signal:
        requests.extend(
            [
                request(
                    "foreign-broker-statements",
                    "Foreign broker/custodian statements covering both Apr–Mar and Jan–Dec",
                    "income schedules use the financial year while Schedule FA uses the calendar year",
                ),
                request(
                    "foreign-tax-form",
                    "Form 1042-S and any 1099-DIV/withholding statement",
                    "reconcile gross foreign income, withholding, FSI/TR, and Form 67",
                ),
                request(
                    "foreign-trades",
                    "Foreign trade confirmations and complete acquisition-lot history",
                    "calculate capital gains and A3 acquisition/proceeds values",
                ),
                request(
                    "foreign-account-profile",
                    "Account profile/opening evidence and 31 Dec/31 Mar balances",
                    "support Schedule FA A1/A2 and Schedule AL dates/balances",
                ),
            ]
        )

    if capital_gains > 0 or actual_sales is True:
        requests.append(
            request(
                "capital-gains-detail",
                "Broker capital-gains report, contract notes, and purchase-cost history",
                "verify actual disposals, holding period, cost, proceeds, and special-rate classification",
            )
        )
    elif actual_sales is None:
        questions.append(
            "Were any shares, mutual funds, property, virtual assets, or other "
            "capital assets actually sold or transferred during the financial year?"
        )

    if (capital_gains > 0 or business_income is True) and brought_forward_losses is None:
        questions.append(
            "Are there brought-forward or unabsorbed losses from an earlier return?"
        )
    if brought_forward_losses is True:
        requests.append(
            request(
                "prior-return-losses",
                "Prior-year ITR acknowledgement, computation, and Schedule CFL/loss details",
                "verify eligible brought-forward losses and continuity of the selected ITR form",
            )
        )

    if interest > 0:
        requests.append(
            request(
                "bank-interest",
                "Bank interest certificates plus 31 March statements for savings accounts and deposits",
                "reconcile Schedule OS interest and Schedule AL bank balances",
            )
        )

    if home_loan is None:
        questions.append(
            "Did you own, purchase, construct, or have a loan against any house property?"
        )
    if home_loan is True:
        requests.extend(
            [
                request(
                    "home-loan-certificate",
                    "Annual home-loan interest certificate and full loan statement",
                    "separate interest, principal, and 31 March outstanding principal",
                ),
                request(
                    "property-evidence",
                    "Sale agreement/title, builder invoices, payment ledger, and ownership shares",
                    "support HP treatment and Schedule AL historical cost",
                ),
            ]
        )
        if under_construction is True or under_construction is None:
            requests.append(
                request(
                    "completion-evidence",
                    "Completion/possession certificate or current construction-status evidence",
                    "determine whether current interest is claimable or must remain in the pre-construction ledger",
                )
            )

    al_threshold = VERIFIED_AL_THRESHOLDS.get(
        str(state.get("assessment_year", ""))
    )
    if al_threshold is not None and total_income > al_threshold:
        requests.append(
            request(
                "schedule-al-evidence",
                "31 March bank/FD balances, share lots at cost, asset costs, and related liabilities",
                "Schedule AL is triggered at the verified AY 2026-27 threshold; reverify for other AYs",
            )
        )
    elif al_threshold is None and total_income > 0:
        questions.append(
            "The assessment year has no bundled Schedule AL threshold. Verify "
            "the current official ITR instructions before deciding AL applicability."
        )

    unique: dict[str, dict[str, Any]] = {
        item["request_id"]: item for item in requests
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "CONDITIONAL_DOCUMENTS",
        "requests": list(unique.values()),
        "questions": questions,
        "observed_document_types": sorted(document_types),
        "signals": {
            "perquisites": str(perquisites),
            "capital_gains": str(capital_gains),
            "interest": str(interest),
            "foreign_tax": str(foreign_tax),
            "total_income": str(total_income),
        },
    }


def assess(args: argparse.Namespace) -> None:
    workspace = workspace_path(args.workspace)
    require_workspace(workspace)
    state = load_state(workspace)
    payload = next_requests(state, available_records(workspace))
    atomic_json(workspace / REQUESTS, payload)
    state["phase"] = payload["phase"]
    state.setdefault("history", []).append(
        {"event": "REQUESTS_REASSESSED", "at": utc_now()}
    )
    save_state(workspace, state)
    print_requests(payload)
    print(f"\nMachine-readable requests: {workspace / REQUESTS}")


def print_requests(payload: dict[str, Any]) -> None:
    print(f"Phase: {payload['phase']}")
    requests = payload.get("requests", [])
    if requests:
        print("\nDocuments:")
        for index, item in enumerate(requests, start=1):
            print(
                f"{index}. [{item['priority']}] {item['document']} — "
                f"{item['reason']}"
            )
    else:
        print("\nNo additional document request was generated.")
    questions = payload.get("questions", [])
    if questions:
        print("\nQuestions:")
        for index, question in enumerate(questions, start=1):
            print(f"{index}. {question}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage Indian ITR document intake and conditional follow-ups"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser(
        "start", help="Initialize intake and print the primary checklist"
    )
    start_parser.add_argument("--workspace", required=True)
    start_parser.add_argument("--assessment-year", required=True)
    start_parser.add_argument("--force", action="store_true")
    start_parser.set_defaults(func=start)

    record_parser = subparsers.add_parser(
        "record", help="Record a taxpayer-confirmed decision or fact"
    )
    record_parser.add_argument("--workspace", required=True)
    record_parser.add_argument("--fact", required=True)
    record_parser.add_argument("--basis")
    record_parser.set_defaults(func=record)

    assess_parser = subparsers.add_parser(
        "assess", help="Generate the next document requests from extracted evidence"
    )
    assess_parser.add_argument("--workspace", required=True)
    assess_parser.set_defaults(func=assess)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (StoreError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
