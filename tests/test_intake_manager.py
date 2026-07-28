import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = (
    Path(__file__).parents[1] / "prepare-india-tax-return" / "scripts"
)
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "intake_manager.py"
SPEC = importlib.util.spec_from_file_location("intake_manager", SCRIPT)
intake_manager = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = intake_manager
SPEC.loader.exec_module(intake_manager)


def record(document_type, claims=None):
    return {
        "source": {
            "source_id": f"src-{document_type}",
            "sha256": document_type,
            "document_type": document_type,
        },
        "claims": claims or [],
    }


class IntakeManagerTest(unittest.TestCase):
    def test_initial_documents_are_requested_first(self):
        payload = intake_manager.next_requests(
            {"facts": {}}, [record("FORM16_PART_B")]
        )
        self.assertEqual(payload["phase"], "INITIAL_DOCUMENTS")
        ids = {item["request_id"] for item in payload["requests"]}
        self.assertIn("initial-ais", ids)
        self.assertIn("initial-tis", ids)

    def test_foreign_signal_generates_conditional_package(self):
        records = [
            record("FORM16_PART_B"),
            record("AIS_JSON"),
            record("TIS"),
            record(
                "FORM1042S",
                [
                    {
                        "kind": "foreign_tax.1042s",
                        "values": {"federal_tax_withheld_usd": 250},
                    }
                ],
            ),
        ]
        payload = intake_manager.next_requests({"facts": {}}, records)
        self.assertEqual(payload["phase"], "CONDITIONAL_DOCUMENTS")
        ids = {item["request_id"] for item in payload["requests"]}
        self.assertIn("foreign-broker-statements", ids)
        self.assertIn("foreign-tax-form", ids)
        self.assertIn("foreign-trades", ids)

    def test_non_salaried_intake_can_progress_without_form16(self):
        records = [record("AIS_JSON"), record("TIS")]
        state = {"facts": {"salary_income": {"value": False}}}
        payload = intake_manager.next_requests(state, records)
        self.assertEqual(payload["phase"], "CONDITIONAL_DOCUMENTS")
        ids = {item["request_id"] for item in payload["requests"]}
        self.assertNotIn("initial-form16", ids)

    def test_business_income_requests_business_evidence(self):
        records = [record("AIS_JSON"), record("TIS")]
        state = {
            "facts": {
                "salary_income": {"value": False},
                "business_income": {"value": True},
            }
        }
        payload = intake_manager.next_requests(state, records)
        ids = {item["request_id"] for item in payload["requests"]}
        self.assertIn("business-books", ids)
        self.assertIn("business-compliance", ids)

    def test_home_loan_fact_requests_property_evidence(self):
        records = [
            record("FORM16_PART_B"),
            record("AIS_JSON"),
            record("TIS"),
        ]
        state = {
            "facts": {
                "home_loan": {"value": True},
                "property_under_construction": {"value": True},
            }
        }
        payload = intake_manager.next_requests(state, records)
        ids = {item["request_id"] for item in payload["requests"]}
        self.assertIn("home-loan-certificate", ids)
        self.assertIn("property-evidence", ids)
        self.assertIn("completion-evidence", ids)


if __name__ == "__main__":
    unittest.main()
