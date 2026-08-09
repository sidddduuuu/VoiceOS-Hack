from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from dataclasses import replace
from unittest.mock import Mock, call, patch

from labloop.contracts import (
    AuditEvent,
    EventKind,
    ExperimentRun,
    Measurement,
    Protocol,
    ProtocolStep,
    RunStatus,
    Severity,
    ValidationIssue,
)


def _install_missing_dependency_stubs() -> None:
    modules = {
        "labloop.protocols": (
            "advance_run",
            "complete_run",
            "current_step",
            "load_protocols",
            "start_run",
        ),
        "labloop.storage": ("EventStore",),
        "labloop.validation": ("validate_measurement",),
    }
    for name, attributes in modules.items():
        if importlib.util.find_spec(name) is None:
            module = types.ModuleType(name)
            for attribute in attributes:
                setattr(module, attribute, object())
            sys.modules[name] = module


_install_missing_dependency_stubs()

import labloop.service as service_module  # noqa: E402


class LabLoopServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.step = ProtocolStep("step-1", "Measure", "Record the value")
        self.protocol = Protocol("demo", "Demo", "1", (self.step,))
        self.run = ExperimentRun(
            id="run-1",
            protocol_id="demo",
            protocol_version="1",
            operator="Ada",
            sample_ids=("sample-1", "sample-2"),
            status=RunStatus.RUNNING,
            started_at="2026-08-09T12:00:00Z",
        )
        self.store = Mock()
        self.store.get_run.return_value = self.run
        self.event_number = 0
        self.store.append.side_effect = self._append_event

        patches = (
            patch.object(service_module, "load_protocols", return_value={"demo": self.protocol}),
            patch.object(service_module, "EventStore", return_value=self.store),
            patch.object(service_module, "validate_measurement", return_value=[]),
            patch.object(service_module, "start_run", side_effect=self._start_run),
            patch.object(service_module, "current_step", return_value=self.step),
            patch.object(service_module, "advance_run", side_effect=self._advance_run),
            patch.object(service_module, "complete_run", side_effect=self._complete_run),
        )
        (
            self.load_protocols,
            self.event_store,
            self.validate_measurement,
            self.start_run,
            self.current_step,
            self.advance_run,
            self.complete_run,
        ) = (patcher.start() for patcher in patches)
        for patcher in patches:
            self.addCleanup(patcher.stop)
        self.service = service_module.LabLoopService("labloop.db", "protocols")

    def _append_event(
        self,
        run_id: str,
        kind: EventKind,
        payload: dict,
        supersedes_event_id: str | None = None,
    ) -> AuditEvent:
        self.event_number += 1
        return AuditEvent(
            id=f"event-{self.event_number}",
            run_id=run_id,
            kind=kind,
            payload=payload,
            created_at="2026-08-09T12:00:01Z",
            supersedes_event_id=supersedes_event_id,
        )

    @staticmethod
    def _start_run(run: ExperimentRun, timestamp: str) -> ExperimentRun:
        return replace(run, status=RunStatus.RUNNING, started_at=timestamp)

    @staticmethod
    def _advance_run(
        protocol: Protocol, run: ExperimentRun, step_id: str
    ) -> ExperimentRun:
        return replace(run, current_step_index=run.current_step_index + 1)

    @staticmethod
    def _complete_run(
        protocol: Protocol, run: ExperimentRun, timestamp: str
    ) -> ExperimentRun:
        return replace(run, status=RunStatus.COMPLETED, completed_at=timestamp)

    def test_begin_validates_inputs_and_emits_run_event(self) -> None:
        invalid_calls = (
            ("unknown", "Ada", ["sample-1"]),
            ("demo", " ", ["sample-1"]),
            ("demo", "Ada", []),
            ("demo", "Ada", [" "]),
            ("demo", "Ada", ["sample-1", " sample-1 "]),
        )
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.service.begin_experiment(*arguments)
        self.store.save_run.assert_not_called()

        run = self.service.begin_experiment(
            " demo ", " Ada ", [" sample-1 ", "sample-2"], "2026-08-09T12:00:00Z"
        )

        self.assertEqual(run.operator, "Ada")
        self.assertEqual(run.sample_ids, ("sample-1", "sample-2"))
        self.assertEqual(run.status, RunStatus.RUNNING)
        self.load_protocols.assert_called_once_with("protocols")
        self.event_store.assert_called_once_with("labloop.db")
        self.assertEqual(
            self.store.method_calls,
            [
                call.save_run(run),
                call.append(
                    run.id,
                    EventKind.RUN,
                    {
                        "protocol_id": "demo",
                        "protocol_version": "1",
                        "operator": "Ada",
                        "sample_ids": ["sample-1", "sample-2"],
                    },
                ),
            ],
        )

    def test_constructor_fails_before_store_when_no_protocols_load(self) -> None:
        self.load_protocols.return_value = {}
        self.event_store.reset_mock()

        with self.assertRaisesRegex(ValueError, "no usable protocols"):
            service_module.LabLoopService("other.db", "empty")

        self.event_store.assert_not_called()

    def test_current_step_requires_the_run_protocol_version(self) -> None:
        self.assertIs(self.service.get_current_step("run-1"), self.step)
        self.current_step.assert_called_once_with(self.protocol, self.run)

        self.current_step.reset_mock()
        self.store.get_run.return_value = replace(self.run, protocol_version="0")
        with self.assertRaisesRegex(ValueError, "version '0'.*not loaded"):
            self.service.get_current_step("run-1")
        self.current_step.assert_not_called()

    def test_observations_reject_unknown_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.service.record_observation("run-1", "Clear solution", "unknown")
        self.store.append.assert_not_called()

        event = self.service.record_observation(
            "run-1", " Clear solution ", " sample-1 "
        )
        self.assertEqual(event.kind, EventKind.OBSERVATION)
        self.store.append.assert_called_once_with(
            "run-1",
            EventKind.OBSERVATION,
            {
                "note": "Clear solution",
                "sample_id": "sample-1",
                "source": "researcher",
            },
        )

    def test_measurement_records_raw_input_and_one_deviation(self) -> None:
        measurement = Measurement(
            run_id="run-1",
            step_id="step-1",
            sample_id="sample-1",
            value=12.5,
            unit="ng/uL",
            instrument="NanoDrop",
            conditions={"temperature_c": 22},
            captured_at="2026-08-09T12:01:00Z",
        )
        issues = [
            ValidationIssue("value", "Value is outside the protocol range.", Severity.WARNING),
            ValidationIssue("unit", "What unit should I record?", Severity.BLOCKING),
        ]
        self.validate_measurement.return_value = issues

        event, returned_issues = self.service.record_measurement(measurement)

        self.assertEqual(returned_issues, issues)
        self.validate_measurement.assert_called_once_with(self.step, measurement)
        self.assertEqual(
            self.store.append.call_args_list,
            [
                call(
                    "run-1",
                    EventKind.MEASUREMENT,
                    {
                        "run_id": "run-1",
                        "step_id": "step-1",
                        "sample_id": "sample-1",
                        "value": 12.5,
                        "unit": "ng/uL",
                        "instrument": "NanoDrop",
                        "conditions": {"temperature_c": 22},
                        "captured_at": "2026-08-09T12:01:00Z",
                    },
                ),
                call(
                    "run-1",
                    EventKind.DEVIATION,
                    {
                        "measurement_event_id": event.id,
                        "issues": [
                            {
                                "field": "value",
                                "question": "Value is outside the protocol range.",
                                "severity": "warning",
                            },
                            {
                                "field": "unit",
                                "question": "What unit should I record?",
                                "severity": "blocking",
                            },
                        ],
                    },
                ),
            ],
        )

    def test_measurement_without_issues_has_no_deviation(self) -> None:
        measurement = Measurement("run-1", "step-1", None, 0, "g", None)

        event, issues = self.service.record_measurement(measurement)

        self.assertEqual(issues, [])
        self.assertEqual(event.kind, EventKind.MEASUREMENT)
        self.store.append.assert_called_once()
        self.assertEqual(self.store.append.call_args.args[1], EventKind.MEASUREMENT)

    def test_measurement_boundary_rejects_bad_sample_value_and_conditions(self) -> None:
        invalid_measurements = (
            Measurement("run-1", "step-1", "unknown", 1, "g", None),
            Measurement("run-1", "step-1", None, math.inf, "g", None),
            Measurement("run-1", "step-1", None, True, "g", None),
            Measurement("run-1", "step-1", None, 1, 5, None),  # type: ignore[arg-type]
            Measurement("run-1", "step-1", None, 1, "g", None, {"bad": object()}),
        )
        for measurement in invalid_measurements:
            with self.subTest(measurement=measurement), self.assertRaises(ValueError):
                self.service.record_measurement(measurement)
        self.store.append.assert_not_called()

    def test_checkpoint_and_completion_save_before_returning(self) -> None:
        self.store.reset_mock()
        self.store.get_run.return_value = self.run
        checkpointed = self.service.complete_checkpoint("run-1", "step-1")
        self.assertEqual(checkpointed.current_step_index, 1)
        self.assertEqual(
            self.store.method_calls,
            [
                call.get_run("run-1"),
                call.save_run(checkpointed),
                call.append(
                    "run-1",
                    EventKind.CHECKPOINT,
                    {"completed_step_id": "step-1", "next_step_index": 1},
                ),
            ],
        )

        ready = replace(self.run, current_step_index=1)
        self.store.reset_mock()
        self.store.get_run.return_value = ready
        finished = self.service.finish_experiment(
            "run-1", "2026-08-09T13:00:00Z"
        )
        self.assertEqual(finished.status, RunStatus.COMPLETED)
        self.assertEqual(
            self.store.method_calls,
            [
                call.get_run("run-1"),
                call.save_run(finished),
                call.append(
                    "run-1",
                    EventKind.RUN,
                    {"status": "completed", "completed_at": "2026-08-09T13:00:00Z"},
                ),
            ],
        )

    def test_correction_appends_same_kind_and_supersedes(self) -> None:
        target = AuditEvent(
            "event-old",
            "run-1",
            EventKind.OBSERVATION,
            {"note": "old"},
            "2026-08-09T12:00:00Z",
        )
        self.store.list_events.return_value = [target]
        replacement = {"note": "corrected", "correction_reason": "transcription"}

        event = self.service.correct_event("run-1", "event-old", replacement)

        self.assertEqual(event.supersedes_event_id, "event-old")
        self.store.append.assert_called_once_with(
            "run-1",
            EventKind.OBSERVATION,
            replacement,
            supersedes_event_id="event-old",
        )
        for invalid in ({}, [], {"bad": object()}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.service.correct_event("run-1", "event-old", invalid)  # type: ignore[arg-type]

        self.store.list_events.return_value = []
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.service.correct_event("run-1", "other-event", {"note": "x"})

    def test_downstream_write_failures_propagate_without_success(self) -> None:
        self.store.save_run.side_effect = OSError("disk unavailable")
        with self.assertRaisesRegex(OSError, "disk unavailable"):
            self.service.begin_experiment("demo", "Ada", ["sample-1"])
        self.store.append.assert_not_called()

        self.store.save_run.side_effect = None
        self.store.append.side_effect = OSError("event write failed")
        with self.assertRaisesRegex(OSError, "event write failed"):
            self.service.begin_experiment("demo", "Ada", ["sample-1"])
        self.assertEqual(self.store.save_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
