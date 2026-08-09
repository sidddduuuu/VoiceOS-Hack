import json
import sqlite3
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from labloop.contracts import EventKind, ExperimentRun, RunStatus
from labloop.storage import EventStore


class EventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "nested" / "labloop.db"
        self.store = EventStore(self.path)
        self.run = ExperimentRun(
            id="run-1",
            protocol_id="dna-extraction",
            protocol_version="1.2",
            operator="Ada",
            sample_ids=("sample-1", "sample-2"),
            status=RunStatus.RUNNING,
            current_step_index=3,
            started_at="2026-08-09T12:00:00Z",
            completed_at=None,
        )

    def test_initializes_schema_and_round_trips_every_run_field(self) -> None:
        self.store.save_run(self.run)
        second_store = EventStore(self.path)

        self.assertEqual(self.store.get_run(self.run.id), self.run)
        self.assertEqual(second_store.get_run(self.run.id), self.run)
        second_run = replace(self.run, id="run-from-second-store")
        second_store.save_run(second_run)
        self.assertEqual(self.store.get_run(second_run.id), second_run)
        with sqlite3.connect(self.path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = ?", ("table",)
                )
            }
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        with closing(self.store._connect()) as connection:
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(tables, {"runs", "events"})
        self.assertEqual(journal_mode, "wal")
        self.assertEqual(foreign_keys, 1)

    def test_save_updates_snapshot_without_duplicate(self) -> None:
        self.store.save_run(self.run)
        updated = replace(
            self.run,
            status=RunStatus.COMPLETED,
            current_step_index=4,
            completed_at="2026-08-09T13:00:00Z",
        )

        self.store.save_run(updated)

        self.assertEqual(self.store.get_run(self.run.id), updated)
        self.assertEqual(len(self.store.list_runs()), 1)

    def test_list_ordering_and_unknown_run_behavior(self) -> None:
        runs = (
            replace(self.run, id="b", started_at="2026-08-09T13:00:00Z"),
            replace(self.run, id="a", started_at="2026-08-09T13:00:00Z"),
            replace(self.run, id="newest", started_at="2026-08-09T14:00:00Z"),
            replace(self.run, id="not-started", started_at=None),
        )
        for run in runs:
            self.store.save_run(run)

        self.assertEqual(
            [run.id for run in self.store.list_runs()],
            ["newest", "a", "b", "not-started"],
        )
        self.assertIsNone(self.store.get_run("missing"))
        with self.assertRaisesRegex(ValueError, "unknown run_id"):
            self.store.list_events("missing")

    def test_append_and_list_round_trip_nested_payload(self) -> None:
        self.store.save_run(self.run)
        payload = {
            "sample": "sample-1",
            "values": [1.5, 2.0],
            "conditions": {"cold": True, "note": None},
        }

        event = self.store.append(self.run.id, EventKind.MEASUREMENT, payload)

        self.assertEqual(self.store.list_events(self.run.id), [event])
        self.assertEqual(event.payload, payload)
        self.assertTrue(event.created_at.endswith("Z"))
        with sqlite3.connect(self.path) as connection:
            stored_payload = connection.execute(
                "SELECT payload FROM events WHERE id = ?", (event.id,)
            ).fetchone()[0]
        self.assertEqual(json.loads(stored_payload), payload)

    def test_correction_must_reference_event_in_same_run(self) -> None:
        second_run = replace(self.run, id="run-2")
        self.store.save_run(self.run)
        self.store.save_run(second_run)
        original = self.store.append(self.run.id, EventKind.OBSERVATION, {"note": "first"})
        other = self.store.append(second_run.id, EventKind.OBSERVATION, {"note": "other"})

        correction = self.store.append(
            self.run.id,
            EventKind.OBSERVATION,
            {"note": "corrected"},
            supersedes_event_id=original.id,
        )

        self.assertEqual(correction.supersedes_event_id, original.id)
        self.assertEqual(len(self.store.list_events(self.run.id)), 2)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.store.append(
                self.run.id,
                EventKind.OBSERVATION,
                {"note": "bad correction"},
                supersedes_event_id=other.id,
            )

    def test_rejects_non_json_unknown_run_and_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "database path"):
            EventStore("")
        with self.assertRaisesRegex(ValueError, "run.id"):
            self.store.save_run(replace(self.run, id=""))
        with self.assertRaisesRegex(ValueError, "run.operator"):
            self.store.save_run(replace(self.run, operator=""))
        with self.assertRaisesRegex(ValueError, "invalid run status"):
            self.store.save_run(replace(self.run, status="unknown"))
        with self.assertRaisesRegex(ValueError, "current_step_index"):
            self.store.save_run(replace(self.run, current_step_index=-1))
        with self.assertRaisesRegex(ValueError, "payload must be a dict"):
            self.store.append("missing", EventKind.SYSTEM, [])
        with self.assertRaisesRegex(ValueError, "payload must be JSON-serializable"):
            self.store.append("missing", EventKind.SYSTEM, {"bad": object()})
        with self.assertRaisesRegex(ValueError, "unknown run_id"):
            self.store.append("missing", EventKind.SYSTEM, {})
        with self.assertRaisesRegex(ValueError, "invalid event kind"):
            self.store.append("missing", "not-a-kind", {})

        self.store.save_run(self.run)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE runs SET sample_ids = ? WHERE id = ?", ("not-json", self.run.id)
            )
        with self.assertRaisesRegex(ValueError, "corrupt stored run 'run-1'"):
            self.store.get_run(self.run.id)

    def test_failed_append_leaves_no_partial_row(self) -> None:
        self.store.save_run(self.run)
        original = self.store.append(self.run.id, EventKind.SYSTEM, {"ok": True})

        with self.assertRaises(ValueError):
            self.store.append(
                self.run.id,
                EventKind.SYSTEM,
                {"ok": False},
                supersedes_event_id="missing-event",
            )

        self.assertEqual(self.store.list_events(self.run.id), [original])


if __name__ == "__main__":
    unittest.main()
