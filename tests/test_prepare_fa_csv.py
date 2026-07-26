import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).parents[1]
    / "india-itr2-foreign-assets"
    / "scripts"
    / "prepare_fa_csv.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_fa_csv", SCRIPT)
prepare_fa_csv = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = prepare_fa_csv
SPEC.loader.exec_module(prepare_fa_csv)


class PrepareFACSVTest(unittest.TestCase):
    def a3_row(self):
        values = [
            "United States of America",
            "2-UNITED STATES OF AMERICA",
            "Example, Incorporated (exm)",
            "100 Main Street, New York, NY",
            "12345678",
            "LISTED COMPANY",
            "05-Sep-2024",
            "₹1,234.40",
            "2,000",
            "1,500",
            "100",
            "0",
        ]
        return dict(zip(prepare_fa_csv.A3, values))

    def test_a3_operational_portal_format(self):
        output = prepare_fa_csv.normalize_a3(self.a3_row(), 1)
        self.assertEqual(len(output), 12)
        self.assertEqual(output[0], "1")
        self.assertEqual(output[1], "2")
        self.assertEqual(output[2], "Example Incorporated (EXM)")
        self.assertNotIn(",", output[3])
        self.assertEqual(output[4], "12345678")
        self.assertEqual(output[5], "Company")
        self.assertEqual(output[6], "2024-09-05")
        self.assertEqual(output[7], "1234")

    def test_zip_code_over_eight_characters_is_rejected(self):
        row = self.a3_row()
        row[prepare_fa_csv.A3[4]] = "123456789"
        with self.assertRaisesRegex(ValueError, "8 characters"):
            prepare_fa_csv.normalize_a3(row, 1)

    def test_generated_csv_has_twelve_unquoted_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "a3-working.csv"
            output = root / "Schedule_FA_A3_PORTAL_READY.csv"
            test_output = root / "Schedule_FA_A3_IMPORT_TEST_ONE_ROW.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(prepare_fa_csv.A3)
                row = self.a3_row()
                writer.writerow([row[column] for column in prepare_fa_csv.A3])
            with patch.object(
                sys,
                "argv",
                [
                    "prepare_fa_csv.py",
                    "--table",
                    "A3",
                    "--input",
                    str(source),
                    "--output",
                    str(output),
                    "--test-output",
                    str(test_output),
                ],
            ):
                self.assertEqual(prepare_fa_csv.main(), 0)
            lines = output.read_text(encoding="ascii").splitlines()
            self.assertEqual(lines[1].count(","), 11)
            self.assertNotIn('"', lines[1])
            with output.open(newline="", encoding="ascii") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(len(rows[1]), 12)
            with test_output.open(newline="", encoding="ascii") as handle:
                test_rows = list(csv.reader(handle))
            self.assertEqual(len(test_rows), 2)
            self.assertEqual(test_rows[1], rows[1])


if __name__ == "__main__":
    unittest.main()
