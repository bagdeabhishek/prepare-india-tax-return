import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "india-itr2-foreign-assets" / "scripts"


class PreprocessSourcesTest(unittest.TestCase):
    def test_queue_preprocessing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "sources"
            workspace = root / "workpaper"
            sources.mkdir()
            (sources / "ais.json").write_text(
                '{"income": {"dividend": 125}}', encoding="utf-8"
            )
            (sources / "interest.csv").write_text(
                "Type,Amount\nInterest,20\n", encoding="utf-8"
            )
            (sources / "prefill.json").write_text(
                json.dumps(
                    {
                        "personalInfo": {"pan": "MASKED"},
                        "form24q": {
                            "incomeDeductions": {
                                "salary": 1000000,
                                "perquisitesValue": 50000,
                                "totalIncomeChargeableUnHP": 925000,
                            }
                        },
                        "insights": {"intrstFrmSavingBank": 500},
                    }
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "source_store.py"),
                    "init",
                    "--workspace",
                    str(workspace),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "source_store.py"),
                    "scan",
                    "--workspace",
                    str(workspace),
                    "--source-dir",
                    str(sources),
                    "--replace-inventory",
                    "--extractor-version",
                    "parser-1.0.0_claims-1",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "preprocess_sources.py"),
                    "--workspace",
                    str(workspace),
                    "--jobs",
                    "2",
                    "--ocr",
                    "never",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("3 complete", result.stdout)
            self.assertIn("Deterministic extraction completed 1", result.stdout)
            queue = json.loads((workspace / "work_queue.json").read_text())
            self.assertTrue(
                all(
                    item["normalization_status"] == "COMPLETE"
                    for item in queue["items"]
                )
            )
            semantic = json.loads(
                (workspace / "semantic_queue.json").read_text()
            )
            self.assertEqual(len(semantic["items"]), 2)
            prefill = next(
                item
                for item in queue["items"]
                if item["path"].endswith("prefill.json")
            )
            self.assertFalse(prefill["agent_required"])
            self.assertEqual(prefill["document_type"], "ITR_PREFILL")

    def test_exact_duplicates_reuse_one_normalization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "sources"
            workspace = root / "workpaper"
            sources.mkdir()
            payload = json.dumps(
                {
                    "personalInfo": {"pan": "MASKED"},
                    "form24q": {
                        "incomeDeductions": {
                            "salary": 1000000,
                            "perquisitesValue": 50000,
                            "totalIncomeChargeableUnHP": 925000,
                        }
                    },
                    "insights": {"intrstFrmSavingBank": 500},
                }
            )
            (sources / "prefill-a.json").write_text(payload, encoding="utf-8")
            (sources / "prefill-b.json").write_text(payload, encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "source_store.py"),
                    "init",
                    "--workspace",
                    str(workspace),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "source_store.py"),
                    "scan",
                    "--workspace",
                    str(workspace),
                    "--source-dir",
                    str(sources),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "preprocess_sources.py"),
                    "--workspace",
                    str(workspace),
                    "--jobs",
                    "2",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Parsed 1 unique content hash(es); reused 1", result.stdout)
            queue = json.loads((workspace / "work_queue.json").read_text())
            self.assertEqual(
                sum(bool(item["duplicate_reused"]) for item in queue["items"]),
                1,
            )
            self.assertTrue(
                all(not item["agent_required"] for item in queue["items"])
            )
            self.assertTrue(
                all(
                    Path(item["normalized_output"]).is_file()
                    for item in queue["items"]
                )
            )


if __name__ == "__main__":
    unittest.main()
