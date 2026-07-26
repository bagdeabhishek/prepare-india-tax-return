#!/usr/bin/env python3
"""Normalize Schedule FA A2/A3 CSVs for the current portal importer.

This implements an operational importer workaround, not tax computation.
Always verify the current portal template and manually inspect imported rows.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


A2 = [
    "Country/Region name",
    "Country Name and Code",
    "Name of financial institution",
    "Address of financial institution",
    "ZIP Code",
    "Account Number",
    "Status",
    "Account opening date",
    "Peak Balance During the Period",
    "Closing balance",
    "Nature of Amount",
    "Amount",
]

A3 = [
    "Country/Region name",
    "Country Name and Code",
    "Name of entity",
    "Address of entity",
    "ZIP Code",
    "Nature of entity",
    "Date of acquiring the interest",
    "Initial value of the investment",
    "Peak value of investment during the Period",
    "Closing balance",
    "Total gross amount paid/credited with respect to the holding during the period",
    "Total gross proceeds from sale or redemption of investment during the period",
]


def plain_ascii(value: str, *, remove_commas: bool = False) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    if remove_commas:
        value = value.replace(",", " ")
    return re.sub(r"\s+", " ", value).strip()


def country_code(value: str) -> str:
    match = re.match(r"\s*(\d+)", value or "")
    if not match:
        raise ValueError(f"country code is not numeric: {value!r}")
    return match.group(1)


def iso_date(value: str) -> str:
    value = (value or "").strip()
    formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d %b %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"unsupported date: {value!r}")


def whole_rupees(value: str) -> str:
    cleaned = re.sub(r"[,\s₹$]", "", value or "")
    if not cleaned:
        return "0"
    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"invalid INR amount: {value!r}") from exc
    return str(int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def normalize_nature_entity(value: str) -> str:
    value = plain_ascii(value).lower()
    if "company" in value or "corporation" in value:
        return "Company"
    if not value:
        raise ValueError("nature of entity is blank")
    return value.title()


def normalize_status(value: str) -> str:
    mapping = {
        "owner": "Owner",
        "beneficial owner": "Beneficial owner",
        "beneficiary": "Beneficiary",
    }
    key = plain_ascii(value).replace("_", " ").lower()
    return mapping.get(key, plain_ascii(value).title())


def normalize_amount_nature(value: str) -> str:
    mapping = {
        "o": "Other income",
        "other": "Other income",
        "other income": "Other income",
        "d": "Dividend",
        "dividend": "Dividend",
        "i": "Interest",
        "interest": "Interest",
    }
    key = plain_ascii(value).lower()
    return mapping.get(key, plain_ascii(value))


def load_rows(path: Path, expected: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        raw = list(reader)
    if not raw:
        raise ValueError("input CSV is empty")
    header = raw[0]
    if len(header) == len(expected) + 1 and header[-1] == "":
        header = header[:-1]
    if header != expected:
        raise ValueError(
            "header does not match the downloaded A2/A3 template after removing "
            "one optional trailing blank column"
        )
    rows: list[dict[str, str]] = []
    for line_number, row in enumerate(raw[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) == len(expected) + 1 and row[-1] == "":
            row = row[:-1]
        if len(row) != len(expected):
            raise ValueError(
                f"line {line_number}: expected {len(expected)} fields, got {len(row)}"
            )
        rows.append(dict(zip(expected, row)))
    if not rows:
        raise ValueError("input CSV contains no data rows")
    return rows


def normalize_a3(row: dict[str, str], serial: int) -> list[str]:
    return [
        str(serial),
        country_code(row[A3[1]]),
        plain_ascii(row[A3[2]], remove_commas=True),
        plain_ascii(row[A3[3]], remove_commas=True),
        plain_ascii(row[A3[4]]),
        normalize_nature_entity(row[A3[5]]),
        iso_date(row[A3[6]]),
        whole_rupees(row[A3[7]]),
        whole_rupees(row[A3[8]]),
        whole_rupees(row[A3[9]]),
        whole_rupees(row[A3[10]]),
        whole_rupees(row[A3[11]]),
    ]


def normalize_a2(row: dict[str, str], serial: int) -> list[str]:
    account = re.sub(r"[^A-Za-z0-9]", "", row[A2[5]])
    return [
        str(serial),
        country_code(row[A2[1]]),
        plain_ascii(row[A2[2]], remove_commas=True),
        plain_ascii(row[A2[3]], remove_commas=True),
        plain_ascii(row[A2[4]]),
        account,
        normalize_status(row[A2[6]]),
        iso_date(row[A2[7]]),
        whole_rupees(row[A2[8]]),
        whole_rupees(row[A2[9]]),
        normalize_amount_nature(row[A2[10]]),
        whole_rupees(row[A2[11]]),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True, choices=("A2", "A3"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    header = A2 if args.table == "A2" else A3
    normalizer = normalize_a2 if args.table == "A2" else normalize_a3
    try:
        source_rows = load_rows(args.input, header)
        output_rows = [normalizer(row, i) for i, row in enumerate(source_rows, 1)]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="ascii") as handle:
            writer = csv.writer(handle, quoting=csv.QUOTE_NONE, escapechar="\\")
            writer.writerow(header)
            writer.writerows(output_rows)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"wrote {len(output_rows)} {args.table} rows with "
        f"{len(header)} fields to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
