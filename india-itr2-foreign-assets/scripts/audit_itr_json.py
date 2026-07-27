#!/usr/bin/env python3
"""Audit an official ITR-2 utility export and compare filing checkpoints.

The auditor is intentionally read-only. It validates cross-schedule arithmetic
that is stable enough to check mechanically and reports JSON paths, not taxpayer
identifiers. It does not replace the official utility's validation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def number(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    if isinstance(value, bool):
        return Decimal(int(value))
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def load_return(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        document = json.load(handle)
    try:
        itr = document["ITR"]["ITR2"]
    except (KeyError, TypeError) as exc:
        raise ValueError("expected an official ITR-2 JSON at /ITR/ITR2") from exc
    if not isinstance(itr, dict):
        raise ValueError("/ITR/ITR2 is not an object")
    return itr


class Auditor:
    def __init__(
        self,
        itr: dict[str, Any],
        *,
        tolerance: Decimal = Decimal(10),
        al_threshold: Decimal | None = None,
    ) -> None:
        self.itr = itr
        self.tolerance = tolerance
        self.al_threshold = al_threshold
        self.findings: list[Finding] = []

    def error(self, code: str, message: str) -> None:
        self.findings.append(Finding("ERROR", code, message))

    def warn(self, code: str, message: str) -> None:
        self.findings.append(Finding("WARN", code, message))

    def equal(
        self,
        code: str,
        label: str,
        actual: Any,
        expected: Any,
        *,
        tolerance: Decimal = Decimal(0),
    ) -> None:
        try:
            actual_number = number(actual)
            expected_number = number(expected)
        except ValueError as exc:
            self.error(code, f"{label}: {exc}")
            return
        difference = abs(actual_number - expected_number)
        if difference > tolerance:
            self.error(
                code,
                f"{label}: actual {actual_number} does not equal expected "
                f"{expected_number} (difference {difference})",
            )

    def run(self) -> list[Finding]:
        self.check_salary()
        self.check_other_sources()
        self.check_fsi_tr()
        self.check_part_b_ti()
        self.check_tax_paid()
        self.check_foreign_asset_flag()
        self.check_schedule_al()
        return self.findings

    def check_salary(self) -> None:
        schedule = self.itr.get("ScheduleS", {})
        salaries = schedule.get("Salaries", []) or []
        employer_gross = Decimal(0)
        for index, employer in enumerate(salaries, start=1):
            values = employer.get("Salarys", {})
            expected = sum(
                (
                    number(values.get("Salary")),
                    number(values.get("ValueOfPerquisites")),
                    number(values.get("ProfitsinLieuOfSalary")),
                ),
                Decimal(0),
            )
            self.equal(
                "SALARY_EMPLOYER_GROSS",
                f"ScheduleS employer {index} GrossSalary",
                values.get("GrossSalary"),
                expected,
            )
            employer_gross += number(values.get("GrossSalary"))
        self.equal(
            "SALARY_TOTAL_GROSS",
            "ScheduleS TotalGrossSalary",
            schedule.get("TotalGrossSalary"),
            employer_gross,
        )
        expected_deduction = sum(
            (
                number(schedule.get("DeductionUnderSection16ia")),
                number(schedule.get("EntertainmntalwncUs16ii")),
                number(schedule.get("ProfessionalTaxUs16iii")),
            ),
            Decimal(0),
        )
        self.equal(
            "SALARY_SECTION16",
            "ScheduleS DeductionUS16",
            schedule.get("DeductionUS16"),
            expected_deduction,
        )
        expected_taxable = (
            number(schedule.get("NetSalary")) - number(schedule.get("DeductionUS16"))
        )
        self.equal(
            "SALARY_TAXABLE",
            "ScheduleS TotIncUnderHeadSalaries",
            schedule.get("TotIncUnderHeadSalaries"),
            expected_taxable,
        )

    def check_other_sources(self) -> None:
        schedule = self.itr.get("ScheduleOS", {})
        ordinary = schedule.get("IncOthThanOwnRaceHorse", {})
        dividend_components = sum(
            (
                number(ordinary.get("DividendOthThan22e")),
                number(ordinary.get("Dividend22e")),
                number(ordinary.get("Dividend22f")),
            ),
            Decimal(0),
        )
        self.equal(
            "OS_DIVIDEND",
            "ScheduleOS DividendGross",
            ordinary.get("DividendGross"),
            dividend_components,
        )
        interest_components = sum(
            (
                number(ordinary.get("IntrstFrmSavingBank")),
                number(ordinary.get("IntrstFrmTermDeposit")),
                number(ordinary.get("IntrstFrmIncmTaxRefund")),
                number(ordinary.get("IntrstFrmOthers")),
            ),
            Decimal(0),
        )
        self.equal(
            "OS_INTEREST",
            "ScheduleOS InterestGross",
            ordinary.get("InterestGross"),
            interest_components,
        )
        part_b_os = self.itr.get("PartB-TI", {}).get("IncFromOS", {})
        self.equal(
            "OS_TO_PART_B",
            "PartB-TI income from other sources",
            part_b_os.get("TotIncFromOS"),
            schedule.get("IncChargeable"),
            tolerance=self.tolerance,
        )

    @staticmethod
    def _foreign_key(row: dict[str, Any]) -> tuple[str, str]:
        return (
            str(row.get("CountryCodeExcludingIndia", "")),
            str(row.get("TaxIdentificationNo", "")),
        )

    def check_fsi_tr(self) -> None:
        fsi_rows = self.itr.get("ScheduleFSI", {}).get("ScheduleFSIDtls", []) or []
        fsi_by_key: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
        heads = ("IncFromSal", "IncFromHP", "IncCapGain", "IncOthSrc")
        for index, row in enumerate(fsi_rows, start=1):
            income = sum(
                (number(row.get(head, {}).get("IncFrmOutsideInd")) for head in heads),
                Decimal(0),
            )
            tax = sum(
                (number(row.get(head, {}).get("TaxPaidOutsideInd")) for head in heads),
                Decimal(0),
            )
            indian_tax = sum(
                (number(row.get(head, {}).get("TaxPayableinInd")) for head in heads),
                Decimal(0),
            )
            relief = sum(
                (number(row.get(head, {}).get("TaxReliefinInd")) for head in heads),
                Decimal(0),
            )
            total = row.get("TotalCountryWise", {})
            self.equal(
                "FSI_INCOME_TOTAL",
                f"ScheduleFSI row {index} country income",
                total.get("IncFrmOutsideInd"),
                income,
            )
            self.equal(
                "FSI_TAX_TOTAL",
                f"ScheduleFSI row {index} foreign tax",
                total.get("TaxPaidOutsideInd"),
                tax,
            )
            self.equal(
                "FSI_INDIAN_TAX_TOTAL",
                f"ScheduleFSI row {index} Indian tax",
                total.get("TaxPayableinInd"),
                indian_tax,
            )
            self.equal(
                "FSI_RELIEF_TOTAL",
                f"ScheduleFSI row {index} relief",
                total.get("TaxReliefinInd"),
                relief,
            )
            fsi_by_key[self._foreign_key(row)] = (
                number(total.get("TaxPaidOutsideInd")),
                number(total.get("TaxReliefinInd")),
            )

        tr = self.itr.get("ScheduleTR1", {})
        tr_rows = tr.get("ScheduleTR", []) or []
        total_tax = Decimal(0)
        total_relief = Decimal(0)
        for index, row in enumerate(tr_rows, start=1):
            key = self._foreign_key(row)
            tax = number(row.get("TaxPaidOutsideIndia"))
            relief = number(row.get("TaxReliefOutsideIndia"))
            total_tax += tax
            total_relief += relief
            if key not in fsi_by_key:
                self.error(
                    "TR_WITHOUT_FSI",
                    f"ScheduleTR row {index} has no matching FSI country/TIN row",
                )
                continue
            self.equal(
                "FSI_TR_TAX",
                f"FSI/TR foreign tax for row {index}",
                tax,
                fsi_by_key[key][0],
            )
            self.equal(
                "FSI_TR_RELIEF",
                f"FSI/TR relief for row {index}",
                relief,
                fsi_by_key[key][1],
            )
        self.equal(
            "TR_TAX_TOTAL",
            "ScheduleTR total foreign tax",
            tr.get("TotalTaxPaidOutsideIndia"),
            total_tax,
        )
        self.equal(
            "TR_RELIEF_TOTAL",
            "ScheduleTR total relief",
            tr.get("TotalTaxReliefOutsideIndia"),
            total_relief,
        )
        tti_relief = (
            self.itr.get("PartB_TTI", {})
            .get("ComputationOfTaxLiability", {})
            .get("TaxRelief", {})
            .get("TotTaxRelief")
        )
        self.equal(
            "TR_TO_TTI",
            "PartB-TTI total tax relief",
            tti_relief,
            tr.get("TotalTaxReliefOutsideIndia"),
        )

    def check_part_b_ti(self) -> None:
        part = self.itr.get("PartB-TI", {})
        os_total = part.get("IncFromOS", {}).get("TotIncFromOS")
        cg_total = part.get("CapGain", {}).get("TotalCapGains")
        head_total = sum(
            (
                number(part.get("Salaries")),
                number(part.get("IncomeFromHP")),
                number(cg_total),
                number(os_total),
            ),
            Decimal(0),
        )
        self.equal(
            "PART_B_HEAD_TOTAL",
            "PartB-TI TotalTI",
            part.get("TotalTI"),
            head_total,
            tolerance=self.tolerance,
        )
        expected_gti = (
            number(part.get("BalanceAfterSetoffLosses"))
            - number(part.get("BroughtFwdLossesSetoff"))
        )
        self.equal(
            "PART_B_GTI",
            "PartB-TI GrossTotalIncome",
            part.get("GrossTotalIncome"),
            expected_gti,
            tolerance=self.tolerance,
        )
        expected_total_income = (
            number(part.get("GrossTotalIncome"))
            - number(part.get("DeductionsUnderScheduleVIA"))
        )
        self.equal(
            "PART_B_TOTAL_INCOME",
            "PartB-TI TotalIncome",
            part.get("TotalIncome"),
            expected_total_income,
            tolerance=self.tolerance,
        )

    def check_tax_paid(self) -> None:
        schedule_it = self.itr.get("ScheduleIT", {})
        payments = schedule_it.get("TaxPayment", []) or []
        payment_total = sum(
            (number(row.get("Amt")) for row in payments), Decimal(0)
        )
        self.equal(
            "SCHEDULE_IT_TOTAL",
            "ScheduleIT TotalTaxPayments",
            schedule_it.get("TotalTaxPayments"),
            payment_total,
        )
        tti = self.itr.get("PartB_TTI", {})
        taxes = tti.get("TaxPaid", {}).get("TaxesPaid", {})
        tax_components = sum(
            (
                number(taxes.get("AdvanceTax")),
                number(taxes.get("SelfAssessmentTax")),
                number(taxes.get("TDS")),
                number(taxes.get("TCS")),
            ),
            Decimal(0),
        )
        self.equal(
            "TAXES_PAID_TOTAL",
            "PartB-TTI TotalTaxesPaid",
            taxes.get("TotalTaxesPaid"),
            tax_components,
        )
        self.equal(
            "IT_TO_TTI",
            "ScheduleIT to advance/self-assessment tax",
            payment_total,
            number(taxes.get("AdvanceTax"))
            + number(taxes.get("SelfAssessmentTax")),
        )
        computation = tti.get("ComputationOfTaxLiability", {})
        expected_aggregate = (
            number(computation.get("NetTaxLiability"))
            + number(computation.get("IntrstPay", {}).get("TotalIntrstPay"))
        )
        self.equal(
            "TTI_AGGREGATE",
            "PartB-TTI aggregate liability",
            computation.get("AggregateTaxInterestLiability"),
            expected_aggregate,
            tolerance=self.tolerance,
        )
        liability = number(computation.get("AggregateTaxInterestLiability"))
        paid = number(taxes.get("TotalTaxesPaid"))
        expected_payable = max(liability - paid, Decimal(0))
        expected_refund = max(paid - liability, Decimal(0))
        self.equal(
            "TTI_PAYABLE",
            "PartB-TTI balance payable",
            tti.get("TaxPaid", {}).get("BalTaxPayable"),
            expected_payable,
            tolerance=self.tolerance,
        )
        self.equal(
            "TTI_REFUND",
            "PartB-TTI refund",
            tti.get("Refund", {}).get("RefundDue"),
            expected_refund,
            tolerance=self.tolerance,
        )

    def check_foreign_asset_flag(self) -> None:
        schedule = self.itr.get("ScheduleFA", {})
        populated = any(
            isinstance(value, list) and bool(value) for value in schedule.values()
        )
        if not populated:
            return
        flag = str(self.itr.get("PartB_TTI", {}).get("AssetOutIndiaFlag", "")).lower()
        if flag not in {"y", "yes", "true", "1"}:
            self.error(
                "FOREIGN_ASSET_FLAG",
                "ScheduleFA is populated but PartB-TTI foreign asset/income flag "
                "is not Yes",
            )

    def check_schedule_al(self) -> None:
        if self.al_threshold is None:
            self.warn(
                "SCHEDULE_AL_THRESHOLD_UNVERIFIED",
                "Schedule AL applicability was not tested because no verified "
                "threshold was configured for this assessment year",
            )
            return
        total_income = number(self.itr.get("PartB-TI", {}).get("TotalIncome"))
        if total_income <= self.al_threshold:
            return
        schedule = self.itr.get("ScheduleAL", {})
        immovable = schedule.get("ImmovableDetails", []) or []
        movable = schedule.get("MovableAsset", {}) or {}
        has_movable = any(number(value) != 0 for value in movable.values())
        if not immovable and not has_movable:
            self.error(
                "SCHEDULE_AL_REQUIRED",
                f"Total income exceeds the configured Schedule AL threshold "
                f"({self.al_threshold}) but ScheduleAL has no assets",
            )


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    output: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            output.update(flatten(child, f"{prefix}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.update(flatten(child, f"{prefix}/{index}"))
    else:
        output[prefix] = value
    return output


PAYMENT_ONLY_PATTERNS = (
    re.compile(r"^/CreationInfo/Digest$"),
    re.compile(r"^/ScheduleIT(?:/.*)?$"),
    re.compile(
        r"^/PartB_TTI/TaxPaid/TaxesPaid/"
        r"(?:SelfAssessmentTax|TotalTaxesPaid)$"
    ),
    re.compile(r"^/PartB_TTI/TaxPaid/BalTaxPayable$"),
    re.compile(r"^/PartB_TTI/Refund/RefundDue$"),
)

VERIFIED_AL_THRESHOLDS = {
    # AY 2026-27 official ITR-2 manual and validation rule 456.
    "2026": Decimal(10_000_000),
}


def compare_returns(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    payment_only: bool,
) -> list[Finding]:
    before = flatten(previous)
    after = flatten(current)
    changed = [
        path
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    ]
    findings: list[Finding] = []
    if not changed:
        findings.append(Finding("WARN", "NO_JSON_CHANGES", "the exports are identical"))
        return findings
    if payment_only:
        unexpected = [
            path
            for path in changed
            if not any(pattern.match(path) for pattern in PAYMENT_ONLY_PATTERNS)
        ]
        for path in unexpected:
            findings.append(
                Finding(
                    "ERROR",
                    "UNEXPECTED_PAYMENT_DIFF",
                    f"payment-only comparison changed unrelated path: {path}",
                )
            )
    findings.append(
        Finding(
            "INFO",
            "JSON_DIFF_COUNT",
            f"{len(changed)} leaf paths changed",
        )
    )
    return findings


def print_findings(findings: list[Finding]) -> None:
    if not findings:
        print("PASS: no cross-schedule inconsistencies found")
        return
    for finding in findings:
        print(f"{finding.severity}: {finding.code}: {finding.message}")
    errors = sum(finding.severity == "ERROR" for finding in findings)
    warnings = sum(finding.severity == "WARN" for finding in findings)
    print(f"SUMMARY: {errors} error(s), {warnings} warning(s)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit of an official ITR-2 utility JSON export"
    )
    parser.add_argument("json", type=Path, help="current official ITR-2 export")
    parser.add_argument(
        "--compare",
        type=Path,
        help="previous official export to compare with the current export",
    )
    parser.add_argument(
        "--expect-payment-only",
        action="store_true",
        help="fail if comparison changes anything beyond challan/payment fields",
    )
    parser.add_argument(
        "--rounding-tolerance",
        type=Decimal,
        default=Decimal(10),
        help="maximum accepted statutory rounding difference (default: 10)",
    )
    parser.add_argument(
        "--al-threshold",
        type=Decimal,
        help="verified AY-specific Schedule AL threshold; overrides known values",
    )
    args = parser.parse_args()
    try:
        current = load_return(args.json)
        assessment_year = str(
            current.get("Form_ITR2", {}).get("AssessmentYear", "")
        )
        al_threshold = args.al_threshold
        if al_threshold is None:
            al_threshold = VERIFIED_AL_THRESHOLDS.get(assessment_year)
        findings = Auditor(
            current,
            tolerance=args.rounding_tolerance,
            al_threshold=al_threshold,
        ).run()
        if args.compare:
            previous = load_return(args.compare)
            findings.extend(
                compare_returns(
                    previous,
                    current,
                    payment_only=args.expect_payment_only,
                )
            )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print_findings(findings)
    return 1 if any(item.severity == "ERROR" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
