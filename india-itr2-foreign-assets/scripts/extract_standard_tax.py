#!/usr/bin/env python3
"""Deterministically extract claims from recurring tax-document layouts.

This module consumes the normalized envelope produced by parse_source.py. It
deliberately extracts only stable, labelled fields. Ambiguous or unsupported
documents remain in the semantic-agent queue instead of being guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from parse_source import atomic_json


EXTRACTOR_NAME = "itr-standard-tax-extractor"
EXTRACTOR_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read normalized envelope {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("normalized envelope root must be an object")
    return payload


def json_records(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for unit in envelope.get("document", {}).get("units", []):
        if unit.get("kind") == "json_leaves":
            records.extend(unit.get("records", []))
    return records


def json_pointer_map(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        str(record.get("json_pointer")): record.get("value")
        for record in json_records(envelope)
        if record.get("json_pointer")
    }


def page_texts(envelope: dict[str, Any]) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    for index, unit in enumerate(
        envelope.get("document", {}).get("units", []), start=1
    ):
        text = unit.get("text")
        if not isinstance(text, str):
            continue
        page = unit.get("locator", {}).get("page", index)
        pages.append((int(page), text))
    return pages


def normalized_text(envelope: dict[str, Any]) -> str:
    return "\n".join(text for _, text in page_texts(envelope))


def decimal_value(raw: Any) -> int | float | str:
    if isinstance(raw, (int, float)):
        return raw
    cleaned = re.sub(r"[₹$,\s]", "", str(raw or ""))
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return str(raw)
    if value == value.to_integral():
        return int(value)
    return float(value)


def claim(
    local_id: str,
    kind: str,
    values: dict[str, Any],
    *,
    evidence: dict[str, Any],
    confidence: str = "HIGH",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    item = {
        "local_id": local_id,
        "kind": kind,
        "values": values,
        "evidence": evidence,
        "confidence": confidence,
    }
    if notes:
        item["notes"] = notes
    return item


def json_claim(
    local_id: str,
    kind: str,
    pointer: str,
    value: Any,
    *,
    field: str,
) -> dict[str, Any]:
    return claim(
        local_id,
        kind,
        {field: value},
        evidence={"json_pointer": pointer},
    )


def pointer_value(
    pointers: dict[str, Any], pointer: str
) -> tuple[str, Any] | None:
    if pointer in pointers:
        return pointer, pointers[pointer]
    lowered = pointer.lower()
    for actual, value in pointers.items():
        if actual.lower() == lowered:
            return actual, value
    return None


def extract_prefill(pointers: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        (
            "/form24q/incomeDeductions/salary",
            "salary.form24q",
            "salary",
        ),
        (
            "/form24q/incomeDeductions/perquisitesValue",
            "salary.form24q",
            "perquisites",
        ),
        (
            "/form24q/incomeDeductions/profitsInSalary",
            "salary.form24q",
            "profit_in_lieu",
        ),
        (
            "/form24q/incomeDeductions/deductionUs16Ia",
            "salary.form24q",
            "standard_deduction",
        ),
        (
            "/form24q/incomeDeductions/professionalTaxUs16Iii",
            "salary.form24q",
            "professional_tax",
        ),
        (
            "/form24q/incomeDeductions/totalIncomeChargeableUnHP",
            "salary.form24q",
            "income_chargeable_salary",
        ),
        (
            "/insights/intrstFrmSavingBank",
            "income.interest",
            "savings_interest",
        ),
        (
            "/insights/intrstFrmTermDeposit",
            "income.interest",
            "term_deposit_interest",
        ),
    ]
    claims: list[dict[str, Any]] = []
    for pointer, kind, field in fields:
        found = pointer_value(pointers, pointer)
        if found is None:
            continue
        actual, value = found
        claims.append(
            json_claim(
                f"prefill-{len(claims) + 1}",
                kind,
                actual,
                value,
                field=field,
            )
        )

    tds_prefix = "/form26as/tdsOnSalaries/tdsOnSalary/"
    tds_fields = (
        "totalTDSSal",
        "taxDeducted",
        "incomeChargeableSal",
        "employerOrDeductorOrCollectDetlName",
        "tan",
    )
    grouped: dict[str, dict[str, tuple[str, Any]]] = {}
    for pointer, value in pointers.items():
        if not pointer.lower().startswith(tds_prefix.lower()):
            continue
        suffix = pointer[len(tds_prefix) :]
        parts = suffix.split("/")
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        field = parts[-1]
        if field.lower() not in {item.lower() for item in tds_fields}:
            continue
        grouped.setdefault(parts[0], {})[field] = (pointer, value)
    for index, row in sorted(grouped.items(), key=lambda item: int(item[0])):
        values = {field: value for field, (_, value) in row.items()}
        evidence = {"json_pointers": sorted(pointer for pointer, _ in row.values())}
        claims.append(
            claim(
                f"prefill-tds-salary-{index}",
                "tax.tds.salary",
                values,
                evidence=evidence,
            )
        )
    return claims


def extract_itr_export(pointers: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        ("/ITR/ITR2/Form_ITR2/AssessmentYear", "filing.profile", "assessment_year"),
        (
            "/ITR/ITR2/ScheduleS/TotalGrossSalary",
            "salary.return_total",
            "gross_salary",
        ),
        (
            "/ITR/ITR2/ScheduleS/TotIncUnderHeadSalaries",
            "salary.return_total",
            "taxable_salary",
        ),
        (
            "/ITR/ITR2/ScheduleOS/IncChargeable",
            "income.other_sources.return_total",
            "other_sources",
        ),
        (
            "/ITR/ITR2/PartB-TI/CapGain/TotalCapGains",
            "income.capital_gains.return_total",
            "capital_gains",
        ),
        (
            "/ITR/ITR2/PartB-TI/TotalIncome",
            "return.total_income",
            "total_income",
        ),
        (
            "/ITR/ITR2/ScheduleTR1/TotalTaxPaidOutsideIndia",
            "foreign_tax.return_total",
            "foreign_tax_paid",
        ),
        (
            "/ITR/ITR2/ScheduleTR1/TotalTaxReliefOutsideIndia",
            "foreign_tax.return_total",
            "foreign_tax_relief",
        ),
        (
            "/ITR/ITR2/ScheduleIT/TotalTaxPayments",
            "tax.self_assessment",
            "schedule_it_total",
        ),
    ]
    claims: list[dict[str, Any]] = []
    for pointer, kind, field in fields:
        found = pointer_value(pointers, pointer)
        if found is not None:
            actual, value = found
            claims.append(
                json_claim(
                    f"itr-export-{len(claims) + 1}",
                    kind,
                    actual,
                    value,
                    field=field,
                )
            )
    return claims


AIS_FIELD_NAMES = {
    "informationcode",
    "informationdescription",
    "informationvalue",
    "reportedvalue",
    "modifiedvalue",
    "processedvalue",
    "derivedvalue",
    "acceptedvalue",
    "amount",
    "amountdescription",
    "source",
    "informationsource",
}


def array_row_prefix(pointer: str) -> str | None:
    parts = pointer.strip("/").split("/")
    numeric_positions = [index for index, part in enumerate(parts) if part.isdigit()]
    if not numeric_positions:
        return None
    position = numeric_positions[-1]
    return "/" + "/".join(parts[: position + 1])


def extract_ais_json(pointers: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, tuple[str, Any]]] = {}
    for pointer, value in pointers.items():
        field = pointer.rsplit("/", 1)[-1].lower()
        if field not in AIS_FIELD_NAMES:
            continue
        prefix = array_row_prefix(pointer)
        if prefix is None:
            continue
        grouped.setdefault(prefix, {})[field] = (pointer, value)

    claims: list[dict[str, Any]] = []
    amount_fields = {
        "informationvalue",
        "reportedvalue",
        "modifiedvalue",
        "processedvalue",
        "derivedvalue",
        "acceptedvalue",
        "amount",
    }
    descriptor_fields = {
        "informationcode",
        "informationdescription",
        "amountdescription",
    }
    for prefix, row in sorted(grouped.items()):
        if not (set(row) & amount_fields) or not (set(row) & descriptor_fields):
            continue
        values = {field: value for field, (_, value) in row.items()}
        evidence = {"json_pointers": sorted(pointer for pointer, _ in row.values())}
        claims.append(
            claim(
                f"ais-row-{len(claims) + 1}",
                "ais.information",
                values,
                evidence=evidence,
                confidence="HIGH",
                notes=[
                    "AIS is a reconciliation input; verify against source documents"
                ],
            )
        )
    return claims


AMOUNT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:₹|Rs\.?|INR)?\s*"
    r"(-?\d+(?:,\d{2,3})*(?:\.\d{1,2})?)"
)


def labelled_amount(
    pages: list[tuple[int, str]], patterns: Iterable[str]
) -> tuple[int, str, Any] | None:
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for page, text in pages:
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        for index, line in enumerate(lines):
            for pattern in compiled:
                match = pattern.search(line)
                if not match:
                    continue
                windows = [line[match.end() :]]
                windows.extend(lines[index + 1 : index + 3])
                for window in windows:
                    amounts = AMOUNT_PATTERN.findall(window)
                    if amounts:
                        return page, line, decimal_value(amounts[-1])
    return None


def extract_form16(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    pages = page_texts(envelope)
    fields = [
        (
            "salary",
            "salary.form16",
            (
                r"Salary\s+as\s+per\s+provisions\s+contained\s+in\s+section\s+17\(1\)",
                r"Salary\s+as\s+per\s+section\s+17\(1\)",
            ),
        ),
        (
            "perquisites",
            "salary.form16",
            (r"Value\s+of\s+perquisites\s+under\s+section\s+17\(2\)",),
        ),
        (
            "profit_in_lieu",
            "salary.form16",
            (r"Profits?\s+in\s+lieu\s+of\s+salary\s+under\s+section\s+17\(3\)",),
        ),
        (
            "gross_salary",
            "salary.form16",
            (r"\bGross\s+Salary\b",),
        ),
        (
            "exempt_allowances",
            "salary.form16",
            (r"Total\s+amount\s+of\s+any\s+exemption\s+claimed\s+under\s+section\s+10",),
        ),
        (
            "standard_deduction",
            "salary.form16",
            (r"Standard\s+deduction\s+under\s+section\s+16\(ia\)",),
        ),
        (
            "professional_tax",
            "salary.form16",
            (
                r"Tax\s+on\s+employment\s+under\s+section\s+16\(iii\)",
                r"Professional\s+tax",
            ),
        ),
        (
            "income_chargeable_salary",
            "salary.form16",
            (r"Income\s+chargeable\s+under\s+the\s+head\s+[\"']?Salaries",),
        ),
        (
            "tax_deducted",
            "tax.tds.salary",
            (
                r"Total\s+amount\s+of\s+tax\s+deducted",
                r"Tax\s+Deducted\s+at\s+Source",
            ),
        ),
    ]
    claims: list[dict[str, Any]] = []
    for field, kind, patterns in fields:
        found = labelled_amount(pages, patterns)
        if found is None:
            continue
        page, label, amount = found
        claims.append(
            claim(
                f"form16-{field}",
                kind,
                {field: amount},
                evidence={"page": page, "label": label},
                confidence="HIGH",
            )
        )
    return claims


def extract_12ba(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    found = labelled_amount(
        page_texts(envelope),
        (
            r"Total\s+value\s+of\s+perquisites",
            r"Total\s+value\s+of\s+perquisite",
        ),
    )
    if found is None:
        return []
    page, label, amount = found
    return [
        claim(
            "form12ba-total-perquisites",
            "salary.perquisites.form12ba",
            {"total_perquisites": amount},
            evidence={"page": page, "label": label},
        )
    ]


def extract_tis(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    pages = page_texts(envelope)
    categories = [
        ("salary", r"\bSalary\b"),
        ("dividend", r"\bDividend\b"),
        ("interest_savings", r"Interest\s+from\s+savings"),
        ("interest_deposit", r"Interest\s+from\s+deposit"),
        ("securities_sale", r"Sale\s+of\s+securities"),
        ("foreign_remittance", r"Foreign\s+remittance"),
        ("property", r"(?:Purchase|Sale)\s+of\s+immovable\s+property"),
    ]
    claims: list[dict[str, Any]] = []
    for category, pattern in categories:
        found = labelled_amount(pages, (pattern,))
        if found is None:
            continue
        page, label, amount = found
        claims.append(
            claim(
                f"tis-{category}",
                "tis.category",
                {"category": category, "processed_value": amount},
                evidence={"page": page, "label": label},
                confidence="MEDIUM",
                notes=[
                    "TIS is a reconciliation signal; verify against AIS and source documents"
                ],
            )
        )
    return claims


def extract_ais_pdf(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    claims = extract_tis(envelope)
    for item in claims:
        item["local_id"] = item["local_id"].replace("tis-", "ais-")
        item["kind"] = "ais.category"
        item["notes"] = [
            "AIS is a reconciliation input; verify against source documents"
        ]
    return claims


def extract_26as(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    pages = page_texts(envelope)
    fields = [
        (
            "tds_total",
            (
                r"Total\s+Tax\s+Deducted",
                r"Total\s+TDS",
            ),
        ),
        (
            "tcs_total",
            (
                r"Total\s+Tax\s+Collected",
                r"Total\s+TCS",
            ),
        ),
    ]
    claims: list[dict[str, Any]] = []
    for field, patterns in fields:
        found = labelled_amount(pages, patterns)
        if found is None:
            continue
        page, label, amount = found
        claims.append(
            claim(
                f"26as-{field}",
                "tax.credit.26as",
                {field: amount},
                evidence={"page": page, "label": label},
                confidence="MEDIUM",
                notes=["Reconcile deductor-level rows before claiming credit"],
            )
        )
    return claims


def extract_1042s(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    pages = page_texts(envelope)
    fields = [
        ("income_code", (r"\b1\s+Income\s+code\b",)),
        ("gross_income_usd", (r"\b2\s+Gross\s+income\b",)),
        ("withholding_rate_percent", (r"\b3b\s+Tax\s+rate\b",)),
        (
            "federal_tax_withheld_usd",
            (r"\b10\s+Total\s+withholding\s+credit\b", r"\b10\s+Federal\s+tax"),
        ),
    ]
    claims: list[dict[str, Any]] = []
    for field, patterns in fields:
        found = labelled_amount(pages, patterns)
        if found is None:
            continue
        page, label, amount = found
        claims.append(
            claim(
                f"1042s-{field}",
                "foreign_tax.1042s",
                {field: amount},
                evidence={"page": page, "label": label},
                confidence="HIGH",
            )
        )
    return claims


def detect_document(envelope: dict[str, Any]) -> str:
    source_name = Path(envelope.get("source", {}).get("path", "")).name.lower()
    document = envelope.get("document", {})
    format_name = document.get("format")
    pointers = json_pointer_map(envelope)
    pointer_names = {pointer.lower() for pointer in pointers}
    if format_name == "json":
        if (
            "_ais" in source_name
            and not pointer_names
            and envelope.get("status") == "FAILED"
        ):
            return "AIS_ENCRYPTED_EXPORT"
        if any(pointer.startswith("/itr/itr2/") for pointer in pointer_names):
            return "ITR2_OFFICIAL_EXPORT"
        prefill_markers = {
            "/personalinfo/pan",
            "/form24q/incomedeductions/salary",
            "/form26as/tdsonsalaries/tdsonsalary/0/tan",
        }
        if pointer_names & prefill_markers:
            return "ITR_PREFILL"
        if "_ais" in source_name or any(
            pointer.startswith("/ais/") for pointer in pointer_names
        ):
            return "AIS_JSON"

    text = normalized_text(envelope)
    lowered = text.lower()
    if "form no. 12ba" in lowered or "form no 12ba" in lowered:
        return "FORM12BA"
    if "form no. 16" in lowered or "form no 16" in lowered:
        if "part b (annexure)" in lowered or "part b annexure" in lowered:
            return "FORM16_PART_B"
        if re.search(r"\bpart\s+a\b", lowered):
            return "FORM16_PART_A"
        return "FORM16"
    if "taxpayer information summary" in lowered or "_tis" in source_name:
        return "TIS"
    if (
        "foreign person's u.s. source income subject to withholding" in lowered
        or "form 1042-s" in lowered
        or "1042-s" in source_name
    ):
        return "FORM1042S"
    if (
        "form no. 26as" in lowered
        or "tax credit statement" in lowered
        or "26as" in source_name
    ):
        return "FORM26AS"
    if "_ais" in source_name:
        if re.fullmatch(r"[0-9a-fA-F]+", text.strip() or ""):
            return "AIS_ENCRYPTED_EXPORT"
        return "AIS"
    return "UNKNOWN"


def extract_standard_record(
    envelope: dict[str, Any],
    *,
    source_id: str,
) -> tuple[dict[str, Any], bool]:
    document_type = detect_document(envelope)
    pointers = json_pointer_map(envelope)
    claims: list[dict[str, Any]] = []
    warnings = list(envelope.get("warnings", []))

    if document_type == "ITR_PREFILL":
        claims = extract_prefill(pointers)
    elif document_type == "ITR2_OFFICIAL_EXPORT":
        claims = extract_itr_export(pointers)
    elif document_type in {"FORM16", "FORM16_PART_A", "FORM16_PART_B"}:
        claims = extract_form16(envelope)
    elif document_type == "FORM12BA":
        claims = extract_12ba(envelope)
    elif document_type == "TIS":
        claims = extract_tis(envelope)
    elif document_type == "AIS_JSON":
        claims = extract_ais_json(pointers)
    elif document_type == "AIS":
        claims = extract_ais_pdf(envelope)
    elif document_type == "FORM26AS":
        claims = extract_26as(envelope)
    elif document_type == "FORM1042S":
        claims = extract_1042s(envelope)
    elif document_type == "AIS_ENCRYPTED_EXPORT":
        warnings.append(
            "AIS export appears encrypted; decrypt with the official AIS utility "
            "or provide the AIS PDF before semantic extraction"
        )
    stable_types = {
        "ITR_PREFILL",
        "ITR2_OFFICIAL_EXPORT",
        "FORM16",
        "FORM16_PART_A",
        "FORM16_PART_B",
        "FORM12BA",
        "TIS",
        "AIS",
        "AIS_JSON",
        "FORM26AS",
        "FORM1042S",
    }
    fields = {
        key
        for item in claims
        for key in item.get("values", {})
    }
    minimum_complete = {
        "ITR_PREFILL": len(claims) >= 3,
        "ITR2_OFFICIAL_EXPORT": len(claims) >= 3,
        "FORM16": "tax_deducted" in fields,
        "FORM16_PART_A": "tax_deducted" in fields,
        "FORM16_PART_B": {
            "gross_salary",
            "income_chargeable_salary",
        }.issubset(fields),
        "FORM12BA": "total_perquisites" in fields,
        "TIS": bool(claims),
        "AIS": bool(claims),
        "AIS_JSON": bool(claims),
        "FORM26AS": bool(claims),
        "FORM1042S": {
            "gross_income_usd",
            "federal_tax_withheld_usd",
        }.issubset(fields),
    }
    handled = bool(
        document_type in stable_types
        and minimum_complete.get(document_type)
        and envelope.get("status") == "COMPLETE"
    )
    if document_type in stable_types and not claims:
        warnings.append(
            f"{document_type} was recognized but no stable labelled fields were extracted"
        )
    user_action_required = document_type == "AIS_ENCRYPTED_EXPORT"
    needs_semantic_agent = not handled and not user_action_required

    source = envelope.get("source", {})
    record = {
        "schema_version": "1.0",
        "source": {
            "source_id": source_id,
            "path": source.get("path"),
            "sha256": source.get("sha256"),
            "document_type": document_type,
            "normalized_document": {
                "path": None,
                "source_sha256": source.get("sha256"),
                "parser_version": envelope.get("parser", {}).get("version"),
                "status": envelope.get("status"),
            },
        },
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": EXTRACTOR_VERSION,
            "extracted_at": utc_now(),
        },
        "claims": claims,
        "warnings": sorted(set(warnings)),
        "automation": {
            "handled_without_agent": handled,
            "needs_semantic_agent": needs_semantic_agent,
            "user_action_required": user_action_required,
            "claim_count": len(claims),
        },
    }
    return record, handled


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract stable claims from a normalized tax document"
    )
    parser.add_argument("--normalized", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        envelope = load_json(args.normalized)
        record, handled = extract_standard_record(
            envelope, source_id=args.source_id
        )
        record["source"]["normalized_document"]["path"] = str(
            args.normalized.resolve()
        )
        atomic_json(args.output, record)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"{record['source']['document_type']}: "
        f"{len(record['claims'])} deterministic claim(s); "
        f"agent={'no' if handled else 'required'}"
    )
    return 0 if handled else 3


if __name__ == "__main__":
    raise SystemExit(main())
