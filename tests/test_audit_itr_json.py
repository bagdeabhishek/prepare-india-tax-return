import copy
import importlib.util
import sys
import unittest
from decimal import Decimal
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "india-itr2-foreign-assets"
    / "scripts"
    / "audit_itr_json.py"
)
SPEC = importlib.util.spec_from_file_location("audit_itr_json", SCRIPT)
audit_itr_json = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = audit_itr_json
SPEC.loader.exec_module(audit_itr_json)


def valid_itr():
    return {
        "CreationInfo": {"Digest": "before"},
        "Form_ITR2": {"AssessmentYear": "2026"},
        "ScheduleS": {
            "Salaries": [
                {
                    "Salarys": {
                        "Salary": 900000,
                        "ValueOfPerquisites": 50000,
                        "ProfitsinLieuOfSalary": 0,
                        "GrossSalary": 950000,
                    }
                }
            ],
            "TotalGrossSalary": 950000,
            "NetSalary": 950000,
            "DeductionUnderSection16ia": 75000,
            "EntertainmntalwncUs16ii": 0,
            "ProfessionalTaxUs16iii": 0,
            "DeductionUS16": 75000,
            "TotIncUnderHeadSalaries": 875000,
        },
        "ScheduleOS": {
            "IncOthThanOwnRaceHorse": {
                "DividendOthThan22e": 1000,
                "Dividend22e": 0,
                "Dividend22f": 0,
                "DividendGross": 1000,
                "IntrstFrmSavingBank": 500,
                "IntrstFrmTermDeposit": 2500,
                "IntrstFrmIncmTaxRefund": 0,
                "IntrstFrmOthers": 20,
                "InterestGross": 3020,
            },
            "IncChargeable": 4020,
        },
        "ScheduleFSI": {
            "ScheduleFSIDtls": [
                {
                    "CountryCodeExcludingIndia": "2",
                    "TaxIdentificationNo": "TIN",
                    "IncFromSal": {},
                    "IncFromHP": {},
                    "IncCapGain": {},
                    "IncOthSrc": {
                        "IncFrmOutsideInd": 1000,
                        "TaxPaidOutsideInd": 250,
                        "TaxPayableinInd": 300,
                        "TaxReliefinInd": 250,
                    },
                    "TotalCountryWise": {
                        "IncFrmOutsideInd": 1000,
                        "TaxPaidOutsideInd": 250,
                        "TaxPayableinInd": 300,
                        "TaxReliefinInd": 250,
                    },
                }
            ]
        },
        "ScheduleTR1": {
            "ScheduleTR": [
                {
                    "CountryCodeExcludingIndia": "2",
                    "TaxIdentificationNo": "TIN",
                    "TaxPaidOutsideIndia": 250,
                    "TaxReliefOutsideIndia": 250,
                }
            ],
            "TotalTaxPaidOutsideIndia": 250,
            "TotalTaxReliefOutsideIndia": 250,
        },
        "ScheduleIT": {
            "TaxPayment": [{"Amt": 10000}],
            "TotalTaxPayments": 10000,
        },
        "PartB-TI": {
            "Salaries": 875000,
            "IncomeFromHP": 0,
            "CapGain": {"TotalCapGains": 0},
            "IncFromOS": {"TotIncFromOS": 4020},
            "TotalTI": 879020,
            "BalanceAfterSetoffLosses": 879020,
            "BroughtFwdLossesSetoff": 0,
            "GrossTotalIncome": 879020,
            "DeductionsUnderScheduleVIA": 0,
            "TotalIncome": 879020,
        },
        "PartB_TTI": {
            "AssetOutIndiaFlag": "Y",
            "ComputationOfTaxLiability": {
                "TaxRelief": {"TotTaxRelief": 250},
                "NetTaxLiability": 110000,
                "IntrstPay": {"TotalIntrstPay": 1000},
                "AggregateTaxInterestLiability": 111000,
            },
            "TaxPaid": {
                "TaxesPaid": {
                    "AdvanceTax": 0,
                    "SelfAssessmentTax": 10000,
                    "TDS": 101000,
                    "TCS": 0,
                    "TotalTaxesPaid": 111000,
                },
                "BalTaxPayable": 0,
            },
            "Refund": {"RefundDue": 0},
        },
        "ScheduleFA": {"DtlsForeignEquityDebtInterest": [{"NameOfEntity": "EXAMPLE"}]},
        "ScheduleAL": {},
    }


class AuditITRJSONTest(unittest.TestCase):
    def test_valid_return_passes(self):
        self.assertEqual(
            audit_itr_json.Auditor(
                valid_itr(), al_threshold=Decimal(10_000_000)
            ).run(),
            [],
        )

    def test_detects_fsi_tr_mismatch(self):
        itr = valid_itr()
        itr["ScheduleTR1"]["ScheduleTR"][0]["TaxReliefOutsideIndia"] = 200
        findings = audit_itr_json.Auditor(
            itr, al_threshold=Decimal(10_000_000)
        ).run()
        self.assertIn("FSI_TR_RELIEF", {finding.code for finding in findings})

    def test_requires_schedule_al_above_threshold(self):
        itr = valid_itr()
        itr["PartB-TI"]["TotalIncome"] = 10_000_001
        findings = audit_itr_json.Auditor(
            itr, al_threshold=Decimal(10_000_000)
        ).run()
        self.assertIn("SCHEDULE_AL_REQUIRED", {finding.code for finding in findings})

    def test_payment_only_diff_accepts_expected_paths(self):
        before = valid_itr()
        after = copy.deepcopy(before)
        after["CreationInfo"]["Digest"] = "after"
        after["ScheduleIT"]["TaxPayment"][0]["Amt"] = 10020
        after["ScheduleIT"]["TotalTaxPayments"] = 10020
        after["PartB_TTI"]["TaxPaid"]["TaxesPaid"]["SelfAssessmentTax"] = 10020
        after["PartB_TTI"]["TaxPaid"]["TaxesPaid"]["TotalTaxesPaid"] = 111020
        after["PartB_TTI"]["Refund"]["RefundDue"] = 20
        findings = audit_itr_json.compare_returns(
            before, after, payment_only=True
        )
        self.assertNotIn(
            "UNEXPECTED_PAYMENT_DIFF", {finding.code for finding in findings}
        )

    def test_payment_only_diff_rejects_salary_change(self):
        before = valid_itr()
        after = copy.deepcopy(before)
        after["ScheduleS"]["TotalGrossSalary"] = 999999
        findings = audit_itr_json.compare_returns(
            before, after, payment_only=True
        )
        self.assertIn(
            "UNEXPECTED_PAYMENT_DIFF", {finding.code for finding in findings}
        )


if __name__ == "__main__":
    unittest.main()
