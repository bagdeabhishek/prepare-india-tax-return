import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "prepare-india-tax-return" / "scripts"


class RunIntakePipelineTest(unittest.TestCase):
    def test_end_to_end_prefill_bypasses_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workpaper"
            sources = root / "sources"
            sources.mkdir()
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
                    str(SCRIPTS / "intake_manager.py"),
                    "start",
                    "--workspace",
                    str(workspace),
                    "--assessment-year",
                    "2026-27",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_intake_pipeline.py"),
                    "--workspace",
                    str(workspace),
                    "--source-dir",
                    str(sources),
                    "--jobs",
                    "2",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Deterministic processing is complete", result.stdout)
            semantic = json.loads(
                (workspace / "semantic_queue.json").read_text()
            )
            self.assertEqual(semantic["items"], [])
            central = json.loads((workspace / "central_store.json").read_text())
            self.assertGreaterEqual(len(central["claims"]), 3)
            self.assertEqual(central["pending_sources"], [])
            second = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_intake_pipeline.py"),
                    "--workspace",
                    str(workspace),
                    "--source-dir",
                    str(sources),
                    "--jobs",
                    "2",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("0 source(s) require extraction", second.stdout)


if __name__ == "__main__":
    unittest.main()
