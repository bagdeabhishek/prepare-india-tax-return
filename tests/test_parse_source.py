import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "india-itr2-foreign-assets"
    / "scripts"
    / "parse_source.py"
)
SPEC = importlib.util.spec_from_file_location("parse_source", SCRIPT)
parse_source = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = parse_source
SPEC.loader.exec_module(parse_source)


def write_minimal_xlsx(path):
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Income" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
  Target="worksheets/sheet1.xml"/>
</Relationships>"""
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData>
  <row r="1">
   <c r="A1" t="inlineStr"><is><t>Dividend</t></is></c>
   <c r="B1"><v>123.45</v></c>
  </row>
 </sheetData>
</worksheet>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


class ParseSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.options = parse_source.Options(
            ocr="never", limits=parse_source.Limits()
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_json_paths_and_csv_locations(self):
        capabilities = parse_source.parser_capabilities()
        self.assertTrue(
            capabilities["formats"]["json_csv_text_xml_html_docx_zip"][
                "available"
            ]
        )
        json_path = self.root / "ais.json"
        json_path.write_text(
            json.dumps({"income": [{"kind": "dividend", "amount": 125}]}),
            encoding="utf-8",
        )
        envelope = parse_source.parse_path(json_path, self.options)
        self.assertEqual(envelope["status"], "COMPLETE")
        records = envelope["document"]["units"][0]["records"]
        pointers = {record["json_pointer"] for record in records}
        self.assertIn("/income/0/amount", pointers)

        csv_path = self.root / "statement.csv"
        csv_path.write_text("Type;Amount\nInterest;20\n", encoding="utf-8")
        envelope = parse_source.parse_path(csv_path, self.options)
        self.assertEqual(envelope["status"], "COMPLETE")
        self.assertEqual(envelope["document"]["metadata"]["delimiter"], ";")
        row = envelope["document"]["units"][0]["rows"][1]
        self.assertEqual(row["row"], 2)
        self.assertEqual(row["cells"][1]["value"], "20")

    def test_xlsx_ooxml_fallback(self):
        path = self.root / "statement.xlsx"
        write_minimal_xlsx(path)
        envelope = parse_source.parse_path(path, self.options)
        self.assertIn(envelope["status"], {"COMPLETE", "PARTIAL"})
        sheet = envelope["document"]["units"][0]
        self.assertEqual(sheet["title"], "Income")
        self.assertEqual(sheet["rows"][0]["cells"][0]["value"], "Dividend")

    def test_zip_members_and_unsafe_path(self):
        path = self.root / "bundle.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("inside/data.json", '{"amount": 10}')
            archive.writestr("../unsafe.txt", "do not extract")
        envelope = parse_source.parse_path(path, self.options)
        self.assertEqual(envelope["status"], "PARTIAL")
        self.assertEqual(
            envelope["document"]["members"][0]["member_path"],
            "inside/data.json",
        )
        self.assertTrue(
            any("unsafe archive member" in warning for warning in envelope["warnings"])
        )

    @unittest.skipUnless(
        importlib.util.find_spec("fitz") or shutil.which("pdftotext"),
        "PDF backend unavailable",
    )
    def test_pdf_pages_when_backend_available(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("Synthetic PDF creation requires PyMuPDF")
        path = self.root / "statement.pdf"
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Tax statement amount 250")
        document.save(path)
        document.close()
        envelope = parse_source.parse_path(path, self.options)
        self.assertEqual(envelope["status"], "COMPLETE")
        self.assertIn(
            "Tax statement amount 250",
            envelope["document"]["units"][0]["text"],
        )

    @unittest.skipUnless(
        importlib.util.find_spec("fitz"),
        "Encrypted PDF backend unavailable",
    )
    def test_encrypted_pdf_password_is_not_persisted(self):
        import fitz

        synthetic_password = "synthetic-test-password"
        path = self.root / "encrypted.pdf"
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Encrypted statement")
        document.save(
            path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw=synthetic_password,
            user_pw=synthetic_password,
        )
        document.close()
        options = parse_source.Options(
            password=synthetic_password,
            ocr="never",
            limits=parse_source.Limits(),
        )
        envelope = parse_source.parse_path(path, options)
        self.assertEqual(envelope["status"], "COMPLETE")
        self.assertNotIn(synthetic_password, json.dumps(envelope))

    @unittest.skipUnless(
        importlib.util.find_spec("pyzipper"),
        "AES ZIP backend unavailable",
    )
    def test_encrypted_zip_password_is_not_persisted(self):
        import pyzipper

        synthetic_password = "synthetic-test-password"
        path = self.root / "encrypted.zip"
        with pyzipper.AESZipFile(
            path,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as archive:
            archive.setpassword(synthetic_password.encode("utf-8"))
            archive.writestr("inside.json", '{"amount": 10}')
        options = parse_source.Options(
            password=synthetic_password,
            ocr="never",
            limits=parse_source.Limits(),
        )
        envelope = parse_source.parse_path(path, options)
        self.assertEqual(envelope["status"], "COMPLETE")
        self.assertNotIn(synthetic_password, json.dumps(envelope))


if __name__ == "__main__":
    unittest.main()
