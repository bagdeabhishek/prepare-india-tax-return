import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = (
    Path(__file__).parents[1] / "india-itr2-foreign-assets" / "scripts"
)
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "extract_standard_tax.py"
SPEC = importlib.util.spec_from_file_location("extract_standard_tax", SCRIPT)
extract_standard_tax = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = extract_standard_tax
SPEC.loader.exec_module(extract_standard_tax)


def envelope(units, *, format_name, path="document.pdf"):
    return {
        "schema_version": "1.0",
        "parser": {
            "name": "itr-generic-source-parser",
            "version": "1.0.0",
            "parsed_at": "2026-01-01T00:00:00+00:00",
        },
        "source": {
            "path": path,
            "sha256": "a" * 64,
            "size": 1,
            "extension": Path(path).suffix,
        },
        "status": "COMPLETE",
        "document": {
            "format": format_name,
            "backend": "synthetic",
            "units": units,
            "members": [],
            "metadata": {},
        },
        "warnings": [],
    }


def json_envelope(records, path="prefill.json"):
    return envelope(
        [
            {
                "unit_id": "json-leaves-1",
                "kind": "json_leaves",
                "locator": {"json_pointer": "/"},
                "records": [
                    {
                        "json_pointer": pointer,
                        "value": value,
                        "value_type": type(value).__name__,
                    }
                    for pointer, value in records.items()
                ],
            }
        ],
        format_name="json",
        path=path,
    )


class StandardTaxExtractorTest(unittest.TestCase):
    def test_prefill_is_fully_automated(self):
        source = json_envelope(
            {
                "/personalInfo/pan": "MASKED",
                "/form24q/incomeDeductions/salary": 1000000,
                "/form24q/incomeDeductions/perquisitesValue": 50000,
                "/form24q/incomeDeductions/totalIncomeChargeableUnHP": 925000,
                "/insights/intrstFrmSavingBank": 500,
            }
        )
        record, handled = extract_standard_tax.extract_standard_record(
            source, source_id="src-test"
        )
        self.assertTrue(handled)
        self.assertEqual(record["source"]["document_type"], "ITR_PREFILL")
        self.assertGreaterEqual(len(record["claims"]), 4)

    def test_form16_part_b_requires_control_fields(self):
        text = """
FORM NO. 16
PART B (Annexure)
Salary as per section 17(1)
900000
Value of perquisites under section 17(2)
100000
Gross Salary
1000000
Income chargeable under the head "Salaries"
925000
"""
        source = envelope(
            [
                {
                    "unit_id": "page-1",
                    "kind": "page",
                    "locator": {"page": 1},
                    "text": text,
                    "blocks": [],
                }
            ],
            format_name="pdf",
            path="Form16-PartB.pdf",
        )
        record, handled = extract_standard_tax.extract_standard_record(
            source, source_id="src-form16"
        )
        self.assertTrue(handled)
        values = {
            key: value
            for item in record["claims"]
            for key, value in item["values"].items()
        }
        self.assertEqual(values["gross_salary"], 1000000)
        self.assertEqual(values["income_chargeable_salary"], 925000)

    def test_ais_json_rows_are_grouped_by_source_row(self):
        source = json_envelope(
            {
                "/annualInformation/0/informationCode": "TDS-192",
                "/annualInformation/0/informationDescription": "Salary",
                "/annualInformation/0/reportedValue": 1000000,
                "/annualInformation/0/processedValue": 1000000,
                "/annualInformation/1/informationCode": "SFT-015",
                "/annualInformation/1/informationDescription": "Dividend",
                "/annualInformation/1/reportedValue": 2000,
            },
            path="MASKED_AIS_2026.json",
        )
        record, handled = extract_standard_tax.extract_standard_record(
            source, source_id="src-ais"
        )
        self.assertTrue(handled)
        self.assertEqual(record["source"]["document_type"], "AIS_JSON")
        self.assertEqual(len(record["claims"]), 2)

    def test_unknown_document_stays_in_agent_queue(self):
        source = envelope(
            [
                {
                    "unit_id": "text-1",
                    "kind": "text",
                    "locator": {"line": 1},
                    "text": "Unrecognized broker narrative",
                }
            ],
            format_name="text",
            path="statement.txt",
        )
        record, handled = extract_standard_tax.extract_standard_record(
            source, source_id="src-unknown"
        )
        self.assertFalse(handled)
        self.assertTrue(record["automation"]["needs_semantic_agent"])

    def test_failed_ais_json_is_labelled_as_encrypted_export(self):
        source = json_envelope({}, path="MASKED_AIS_2026.json")
        source["status"] = "FAILED"
        source["warnings"] = ["invalid JSON"]
        record, handled = extract_standard_tax.extract_standard_record(
            source, source_id="src-encrypted-ais"
        )
        self.assertFalse(handled)
        self.assertEqual(
            record["source"]["document_type"], "AIS_ENCRYPTED_EXPORT"
        )
        self.assertFalse(record["automation"]["needs_semantic_agent"])
        self.assertTrue(record["automation"]["user_action_required"])
        self.assertTrue(
            any("official AIS utility" in warning for warning in record["warnings"])
        )


if __name__ == "__main__":
    unittest.main()
