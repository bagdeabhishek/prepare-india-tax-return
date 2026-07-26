import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "india-itr2-foreign-assets"
    / "scripts"
    / "source_store.py"
)
SPEC = importlib.util.spec_from_file_location("source_store", SCRIPT)
source_store = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(source_store)


class Args:
    def __init__(self, **values):
        self.__dict__.update(values)


class SourceStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = self.root / "sources"
        self.workspace = self.root / "workpaper"
        self.sources.mkdir()
        self.source_a = self.sources / "statement-a.txt"
        self.source_b = self.sources / "statement-b.txt"
        self.source_a.write_text("amount=100\n", encoding="utf-8")
        self.source_b.write_text("amount=200\n", encoding="utf-8")
        source_store.init_workspace(Args(workspace=str(self.workspace)))

    def tearDown(self):
        self.temp.cleanup()

    def scan(self, extractor_version="1"):
        source_store.scan_sources(
            Args(
                workspace=str(self.workspace),
                source=None,
                source_dir=[str(self.sources)],
                extractor_version=extractor_version,
                force=False,
                replace_inventory=True,
            )
        )
        return json.loads((self.workspace / source_store.QUEUE).read_text())

    def write_incoming(self, item, amount):
        output = Path(item["agent_output"])
        output.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source": {
                        "source_id": item["source_id"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "document_type": "synthetic_statement",
                    },
                    "extractor": {
                        "name": "test",
                        "version": "1",
                        "extracted_at": "2026-01-01T00:00:00+00:00",
                    },
                    "claims": [
                        {
                            "local_id": "amount-1",
                            "kind": "synthetic_amount",
                            "values": {"amount": amount, "currency": "INR"},
                            "evidence": {"line": 1},
                            "confidence": "HIGH",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def merge(self):
        source_store.merge_store(Args(workspace=str(self.workspace)))
        return json.loads((self.workspace / source_store.CENTRAL).read_text())

    def test_incremental_scan_and_selective_invalidation(self):
        queue = self.scan()
        self.assertEqual(len(queue["items"]), 2)
        for item in queue["items"]:
            amount = 100 if item["path"].endswith("statement-a.txt") else 200
            self.write_incoming(item, amount)
        central = self.merge()
        self.assertEqual(len(central["claims"]), 2)
        self.assertEqual(len(central["pending_sources"]), 0)

        claims_by_path = {
            claim["provenance"]["source_path"]: claim["claim_id"]
            for claim in central["claims"]
        }
        facts_input = self.root / "facts-input.json"
        facts_input.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "facts": [
                        {
                            "fact_id": "fact-a",
                            "kind": "synthetic_total",
                            "values": {"amount": 100},
                            "depends_on": [claims_by_path[str(self.source_a.resolve())]],
                            "derivation": "Direct from statement A",
                            "status": "RECONCILED",
                        },
                        {
                            "fact_id": "fact-b",
                            "kind": "synthetic_total",
                            "values": {"amount": 200},
                            "depends_on": [claims_by_path[str(self.source_b.resolve())]],
                            "derivation": "Direct from statement B",
                            "status": "RECONCILED",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        source_store.set_facts(
            Args(workspace=str(self.workspace), input=str(facts_input))
        )

        unchanged_queue = self.scan()
        self.assertEqual(unchanged_queue["items"], [])

        source_store.scan_sources(
            Args(
                workspace=str(self.workspace),
                source=None,
                source_dir=[str(self.sources)],
                extractor_version="2",
                force=False,
                replace_inventory=True,
            )
        )
        extractor_queue = json.loads(
            (self.workspace / source_store.QUEUE).read_text()
        )
        self.assertEqual(len(extractor_queue["items"]), 2)
        self.assertTrue(
            all(
                item["state"] == "extractor_changed"
                for item in extractor_queue["items"]
            )
        )

        for item in extractor_queue["items"]:
            amount = 100 if item["path"].endswith("statement-a.txt") else 200
            output = Path(item["agent_output"])
            self.write_incoming(item, amount)
            record = json.loads(output.read_text())
            record["extractor"]["version"] = "2"
            output.write_text(json.dumps(record), encoding="utf-8")
        central = self.merge()
        facts = {fact["fact_id"]: fact for fact in central["reconciled_facts"]}
        self.assertEqual(facts["fact-a"]["status"], "STALE")
        self.assertEqual(facts["fact-b"]["status"], "STALE")

        # Reconcile against the version-2 claims before testing a file change.
        claims_by_path = {
            claim["provenance"]["source_path"]: claim["claim_id"]
            for claim in central["claims"]
        }
        facts_payload = json.loads(facts_input.read_text())
        facts_payload["facts"][0]["depends_on"] = [
            claims_by_path[str(self.source_a.resolve())]
        ]
        facts_payload["facts"][0]["status"] = "RECONCILED"
        facts_payload["facts"][1]["depends_on"] = [
            claims_by_path[str(self.source_b.resolve())]
        ]
        facts_payload["facts"][1]["status"] = "RECONCILED"
        facts_input.write_text(json.dumps(facts_payload), encoding="utf-8")
        source_store.set_facts(
            Args(workspace=str(self.workspace), input=str(facts_input))
        )

        self.source_a.write_text("amount=150\n", encoding="utf-8")
        changed_queue = self.scan("2")
        self.assertEqual(len(changed_queue["items"]), 1)
        self.assertTrue(
            changed_queue["items"][0]["path"].endswith("statement-a.txt")
        )

        central = self.merge()
        self.assertEqual(len(central["claims"]), 1)
        self.assertEqual(len(central["pending_sources"]), 1)
        facts = {fact["fact_id"]: fact for fact in central["reconciled_facts"]}
        self.assertEqual(facts["fact-a"]["status"], "STALE")
        self.assertEqual(facts["fact-b"]["status"], "RECONCILED")


if __name__ == "__main__":
    unittest.main()
