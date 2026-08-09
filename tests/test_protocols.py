import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from labloop.contracts import ExpectedRange, ExperimentRun, ProtocolStep, RunStatus
from labloop.protocols import (
    advance_run,
    complete_run,
    current_step,
    load_protocol,
    load_protocols,
    start_run,
)


def protocol_data(protocol_id="dna", step_ids=("lyse", "bind")):
    return {
        "id": protocol_id,
        "name": "DNA extraction",
        "version": "1.0",
        "steps": [
            {
                "id": step_id,
                "title": step_id.title(),
                "instruction": f"Perform {step_id}",
                "required_fields": ["sample_id"],
                "expected_unit": "µL",
                "expected_range": {"minimum": 1, "maximum": 2.5},
                "irreversible": False,
                "timer_seconds": 0,
            }
            for step_id in step_ids
        ],
    }


def write_json(directory, filename, value):
    path = Path(directory, filename)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def make_run(**changes):
    values = {
        "id": "run-1",
        "protocol_id": "dna",
        "protocol_version": "1.0",
        "operator": "Ada",
        "sample_ids": ("sample-1",),
    }
    values.update(changes)
    return ExperimentRun(**values)


class ProtocolLoadingTests(unittest.TestCase):
    def test_valid_protocol_becomes_frozen_contract_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            protocol = load_protocol(write_json(directory, "dna.json", protocol_data()))

        self.assertEqual((protocol.id, protocol.name, protocol.version), ("dna", "DNA extraction", "1.0"))
        self.assertIsInstance(protocol.steps[0], ProtocolStep)
        self.assertEqual(protocol.steps[0].required_fields, ("sample_id",))
        self.assertEqual(protocol.steps[0].expected_range, ExpectedRange(1.0, 2.5))
        with self.assertRaises(FrozenInstanceError):
            protocol.steps[0].title = "Changed"

    def test_directory_loading_is_sorted_and_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            write_json(directory, "z.json", protocol_data("z"))
            write_json(directory, "a.json", protocol_data("a"))
            Path(directory, "nested").mkdir()
            write_json(Path(directory, "nested"), "ignored.json", protocol_data("ignored"))
            self.assertEqual(list(load_protocols(directory)), ["a", "z"])
            write_json(directory, "duplicate.json", protocol_data("a"))
            with self.assertRaisesRegex(ValueError, "duplicate protocol ID 'a'"):
                load_protocols(directory)

    def test_malformed_json_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "bad.json")
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "could not load protocol JSON"):
                load_protocol(path)

    def test_invalid_step_shapes_fail(self):
        cases = {
            "duplicate step": protocol_data(step_ids=("same", "same")),
            "invalid range": protocol_data(),
            "unknown field": protocol_data(),
        }
        cases["invalid range"]["steps"][0]["expected_range"] = {"minimum": 3, "maximum": 2}
        cases["unknown field"]["steps"][0]["instrution"] = "typo"
        patterns = {
            "duplicate step": "duplicate step ID 'same'",
            "invalid range": "minimum exceeds maximum",
            "unknown field": "unknown field.*instrution",
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, value in cases.items():
                with self.subTest(name=name):
                    path = write_json(directory, f"{name}.json", value)
                    with self.assertRaisesRegex(ValueError, patterns[name]):
                        load_protocol(path)

    def test_external_values_are_validated(self):
        mutations = [
            (lambda data: data.update(name=""), "field 'name'"),
            (lambda data: data.update(steps=[]), "non-empty list"),
            (lambda data: data["steps"][0].update(timer_seconds=True), "timer_seconds"),
            (lambda data: data["steps"][0].update(expected_range={"minimum": float("inf")}), "finite number"),
            (lambda data: data["steps"][0].update(irreversible=1), "irreversible"),
            (lambda data: data["steps"][0].update(required_fields=[""]), "required_fields"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for index, (mutate, pattern) in enumerate(mutations):
                data = protocol_data()
                mutate(data)
                with self.subTest(pattern=pattern):
                    with self.assertRaisesRegex(ValueError, pattern):
                        load_protocol(write_json(directory, f"{index}.json", data))

    def test_missing_or_empty_directory_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, r"no '\*\.json' protocols"):
                load_protocols(directory)
            with self.assertRaisesRegex(ValueError, "does not exist"):
                load_protocols(Path(directory, "missing"))


class RunTransitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.protocol = load_protocol(write_json(self.directory.name, "dna.json", protocol_data()))

    def test_happy_path_returns_new_runs_without_mutation(self):
        created = make_run()
        running = start_run(created, "2026-08-09T10:00:00Z")
        step = current_step(self.protocol, running)
        self.assertEqual(step.id, "lyse")
        self.assertIsNot(step, self.protocol.steps[0])
        after_lyse = advance_run(self.protocol, running, "lyse")
        after_bind = advance_run(self.protocol, after_lyse, "bind")
        completed = complete_run(self.protocol, after_bind, "2026-08-09T10:30:00Z")

        self.assertEqual(created.status, RunStatus.CREATED)
        self.assertIsNone(created.started_at)
        self.assertEqual(running.current_step_index, 0)
        self.assertEqual(after_lyse.current_step_index, 1)
        self.assertEqual(completed.status, RunStatus.COMPLETED)
        self.assertEqual(completed.completed_at, "2026-08-09T10:30:00Z")

    def test_wrong_protocol_or_version_fails(self):
        for run, pattern in [
            (make_run(protocol_id="other", status=RunStatus.RUNNING), "references protocol 'other'"),
            (make_run(protocol_version="2.0", status=RunStatus.RUNNING), "references protocol version '2.0'"),
        ]:
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(ValueError, pattern):
                    current_step(self.protocol, run)

    def test_illegal_transitions_fail(self):
        created = make_run()
        running = start_run(created, "2026-08-09T10:00:00Z")
        with self.assertRaisesRegex(ValueError, "current step is 'lyse'"):
            advance_run(self.protocol, running, "bind")
        with self.assertRaisesRegex(ValueError, "before every protocol step"):
            complete_run(self.protocol, running, "2026-08-09T10:30:00Z")

        final_step = advance_run(self.protocol, advance_run(self.protocol, running, "lyse"), "bind")
        with self.assertRaisesRegex(ValueError, "outside protocol"):
            current_step(self.protocol, final_step)
        completed = complete_run(self.protocol, final_step, "2026-08-09T10:30:00Z")
        for operation in (
            lambda: start_run(completed, "2026-08-09T11:00:00Z"),
            lambda: advance_run(self.protocol, completed, "bind"),
            lambda: complete_run(self.protocol, completed, "2026-08-09T11:00:00Z"),
        ):
            with self.assertRaises(ValueError):
                operation()

    def test_timestamps_must_be_utc_iso_8601(self):
        for timestamp in ("", "2026-08-09", "2026-08-09T10:00:00+01:00", "not-a-dateZ"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(ValueError, "UTC ISO-8601"):
                    start_run(make_run(), timestamp)


if __name__ == "__main__":
    unittest.main()
