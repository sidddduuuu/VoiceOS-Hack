from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

from demo import seed


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocols" / "dna-extraction-demo.json"
README_PATH = ROOT / "demo" / "README.md"
SCRIPT_PATH = ROOT / "demo" / "demo-script.md"


class DemoAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol_data = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    @unittest.skipUnless(importlib.util.find_spec("labloop.protocols"), "ticket 01 not merged")
    def test_protocol_loads_through_protocol_engine(self) -> None:
        from labloop.protocols import load_protocol

        protocol = load_protocol(PROTOCOL_PATH)
        self.assertEqual("dna-extraction-demo", protocol.id)
        self.assertEqual("1.0.0", protocol.version)

    def test_protocol_has_required_demo_features(self) -> None:
        self.assertEqual("dna-extraction-demo", self.protocol_data["id"])
        self.assertEqual("1.0.0", self.protocol_data["version"])
        steps = self.protocol_data["steps"]
        self.assertGreaterEqual(len(steps), 6)
        self.assertLessEqual(len(steps), 8)

        setup = next(step for step in steps if step["id"] == "setup-metadata")
        self.assertIn("sample_id", setup["required_fields"])
        self.assertIn("condition.kit_lot", setup["required_fields"])

        measurement = next(step for step in steps if step["id"] == "measure-demo-signal")
        self.assertEqual(
            {"sample_id", "value", "unit", "instrument"},
            set(measurement["required_fields"]),
        )
        self.assertEqual("demo units", measurement["expected_unit"])
        self.assertEqual({"minimum": 10, "maximum": 20}, measurement["expected_range"])
        self.assertTrue(any(step.get("timer_seconds") for step in steps))
        self.assertTrue(any(step.get("irreversible") is True for step in steps))
        self.assertEqual("final-storage-documentation", steps[-1]["id"])
        for step in steps:
            self.assertIn("demo placeholder", step["instruction"].casefold())
            self.assertNotIn("diagnos", step["instruction"].casefold())

    def test_seed_identifiers_are_visibly_synthetic(self) -> None:
        self.assertIn("synthetic", seed.SYNTHETIC_OPERATOR.casefold())
        self.assertTrue(seed.SYNTHETIC_SAMPLE_IDS)
        self.assertTrue(all("synthetic" in value.casefold() for value in seed.SYNTHETIC_SAMPLE_IDS))
        for item in seed.SYNTHETIC_INVENTORY:
            self.assertIn("synthetic", item["id"].casefold())
            self.assertIn("synthetic", item["name"].casefold())

    def test_owned_assets_contain_no_likely_secrets(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PROTOCOL_PATH, README_PATH, SCRIPT_PATH, ROOT / "demo" / "seed.py")
        )
        patterns = (
            r"xox[baprs]-[A-Za-z0-9-]{10,}",
            r"sk-[A-Za-z0-9]{20,}",
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        )
        for pattern in patterns:
            self.assertIsNone(re.search(pattern, text), pattern)

    def test_seed_rejects_external_directory_and_symlink_targets(self) -> None:
        with tempfile.TemporaryDirectory() as external:
            external_db = Path(external) / "external.db"
            with self.assertRaisesRegex(ValueError, "inside"):
                seed.validate_database_path(external_db)

            with tempfile.TemporaryDirectory(dir=ROOT) as local:
                local_path = Path(local)
                with self.assertRaisesRegex(ValueError, "directory"):
                    seed.validate_database_path(local_path)
                link = local_path / "linked.db"
                link.symlink_to(external_db)
                with self.assertRaisesRegex(ValueError, "symlink"):
                    seed.validate_database_path(link)

    def test_seed_reset_is_explicit_and_exact(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            database = Path(temporary) / "demo.db"
            sidecars = (Path(f"{database}-wal"), Path(f"{database}-shm"))
            unrelated = Path(temporary) / "keep.txt"
            for path in (database, *sidecars, unrelated):
                path.write_text("synthetic", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "--reset"):
                seed.prepare_database(database, reset=False)
            self.assertTrue(database.exists())

            seed.prepare_database(database, reset=True)
            self.assertFalse(database.exists())
            self.assertTrue(all(not path.exists() for path in sidecars))
            self.assertTrue(unrelated.exists())

    def test_documentation_covers_required_beats_and_fallback_labels(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8").casefold()
        script = SCRIPT_PATH.read_text(encoding="utf-8").casefold()
        required = (
            "start by voice",
            "current step",
            "normal observation",
            "omit a unit",
            "out-of-range value",
            "ask a supervisor with context",
            "attributed reply",
            "consume inventory",
            "immutable history",
            "close",
        )
        for phrase in required:
            self.assertIn(phrase, script)
        self.assertIn("sixty-second backup", script)
        self.assertIn("pre-demo checklist", script)
        for label in ("live slack", "simulated fallback"):
            self.assertIn(label, script)
            self.assertIn(label, readme)


if __name__ == "__main__":
    unittest.main()
