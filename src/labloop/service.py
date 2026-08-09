"""Application workflow for experiments.

Each storage write is transactional, but a save followed by an event append is
not atomic across both writes in this MVP.
"""

from __future__ import annotations

import copy
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import (
    AuditEvent,
    EventKind,
    ExperimentRun,
    Measurement,
    Protocol,
    ProtocolStep,
    RunStatus,
    ValidationIssue,
)
from .protocols import advance_run, complete_run, current_step, load_protocols, start_run
from .storage import EventStore
from .validation import validate_measurement


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _json_payload(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{field} must be a non-empty JSON object")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON-serializable") from exc
    return copy.deepcopy(value)


class LabLoopService:
    def __init__(self, db_path: str | Path, protocol_dir: str | Path):
        self.protocols = load_protocols(protocol_dir)
        if not self.protocols:
            raise ValueError("protocol directory contains no usable protocols")
        self.store = EventStore(db_path)

    def begin_experiment(
        self,
        protocol_id: str,
        operator: str,
        sample_ids: list[str],
        started_at: str | None = None,
    ) -> ExperimentRun:
        protocol_key = _required_text(protocol_id, "protocol_id").strip()
        protocol = self.protocols.get(protocol_key)
        if protocol is None:
            raise ValueError(f"unknown protocol: {protocol_key}")
        operator_name = _required_text(operator, "operator").strip()
        samples = self._validate_samples(sample_ids)
        run = start_run(
            ExperimentRun(
                id=str(uuid.uuid4()),
                protocol_id=protocol.id,
                protocol_version=protocol.version,
                operator=operator_name,
                sample_ids=samples,
            ),
            started_at if started_at is not None else _utc_now(),
        )
        self.store.save_run(run)
        self.store.append(
            run.id,
            EventKind.RUN,
            {
                "protocol_id": protocol.id,
                "protocol_version": protocol.version,
                "operator": operator_name,
                "sample_ids": list(samples),
            },
        )
        return run

    def get_run(self, run_id: str) -> ExperimentRun:
        run_key = _required_text(run_id, "run_id")
        run = self.store.get_run(run_key)
        if run is None:
            raise ValueError(f"unknown run: {run_key}")
        return run

    def get_current_step(self, run_id: str) -> ProtocolStep:
        run = self.get_run(run_id)
        return current_step(self._protocol_for(run), run)

    def record_observation(
        self, run_id: str, note: str, sample_id: str | None = None
    ) -> AuditEvent:
        run = self.get_run(run_id)
        clean_note = _required_text(note, "note").strip()
        clean_sample = None
        if sample_id is not None:
            clean_sample = _required_text(sample_id, "sample_id").strip()
            if clean_sample not in run.sample_ids:
                raise ValueError(f"sample {clean_sample!r} does not belong to run {run.id}")
        return self.store.append(
            run.id,
            EventKind.OBSERVATION,
            {"note": clean_note, "sample_id": clean_sample, "source": "researcher"},
        )

    def record_measurement(
        self, measurement: Measurement
    ) -> tuple[AuditEvent, list[ValidationIssue]]:
        if not isinstance(measurement, Measurement):
            raise ValueError("measurement must be a Measurement")
        run = self.get_run(measurement.run_id)
        if run.status != RunStatus.RUNNING:
            raise ValueError(f"run {run.id} is not running")
        step = current_step(self._protocol_for(run), run)
        if measurement.step_id != step.id:
            raise ValueError(
                f"measurement step {measurement.step_id!r} is not current step {step.id!r}"
            )
        self._validate_measurement_input(run, measurement)
        issues = validate_measurement(step, measurement)
        event = self.store.append(
            run.id, EventKind.MEASUREMENT, self._measurement_payload(measurement)
        )
        if issues:
            self.store.append(
                run.id,
                EventKind.DEVIATION,
                {
                    "measurement_event_id": event.id,
                    "issues": [
                        {
                            "field": issue.field,
                            "question": issue.question,
                            "severity": issue.severity.value,
                        }
                        for issue in issues
                    ],
                },
            )
        return event, issues

    def complete_checkpoint(self, run_id: str, step_id: str) -> ExperimentRun:
        run = self.get_run(run_id)
        completed_step_id = _required_text(step_id, "step_id")
        updated = advance_run(self._protocol_for(run), run, completed_step_id)
        self.store.save_run(updated)
        self.store.append(
            run.id,
            EventKind.CHECKPOINT,
            {
                "completed_step_id": completed_step_id,
                "next_step_index": updated.current_step_index,
            },
        )
        return updated

    def correct_event(
        self, run_id: str, event_id: str, replacement: dict
    ) -> AuditEvent:
        run = self.get_run(run_id)
        event_key = _required_text(event_id, "event_id")
        payload = _json_payload(replacement, "replacement")
        target = next(
            (event for event in self.store.list_events(run.id) if event.id == event_key),
            None,
        )
        if target is None:
            raise ValueError(f"event {event_key!r} does not belong to run {run.id}")
        return self.store.append(
            run.id,
            target.kind,
            payload,
            supersedes_event_id=target.id,
        )

    def finish_experiment(
        self, run_id: str, completed_at: str | None = None
    ) -> ExperimentRun:
        run = self.get_run(run_id)
        updated = complete_run(
            self._protocol_for(run),
            run,
            completed_at if completed_at is not None else _utc_now(),
        )
        self.store.save_run(updated)
        self.store.append(
            run.id,
            EventKind.RUN,
            {"status": updated.status.value, "completed_at": updated.completed_at},
        )
        return updated

    @staticmethod
    def _validate_samples(sample_ids: object) -> tuple[str, ...]:
        if not isinstance(sample_ids, list) or not sample_ids:
            raise ValueError("sample_ids must be a non-empty list")
        samples = tuple(_required_text(value, "sample_id").strip() for value in sample_ids)
        if len(set(samples)) != len(samples):
            raise ValueError("sample_ids must be unique")
        return samples

    def _protocol_for(self, run: ExperimentRun) -> Protocol:
        protocol = self.protocols.get(run.protocol_id)
        if protocol is None or protocol.version != run.protocol_version:
            raise ValueError(
                f"protocol {run.protocol_id!r} version {run.protocol_version!r} is not loaded"
            )
        return protocol

    @staticmethod
    def _validate_measurement_input(run: ExperimentRun, measurement: Measurement) -> None:
        _required_text(measurement.run_id, "measurement.run_id")
        _required_text(measurement.step_id, "measurement.step_id")
        if measurement.sample_id is not None:
            sample = _required_text(measurement.sample_id, "measurement.sample_id")
            if sample not in run.sample_ids:
                raise ValueError(f"sample {sample!r} does not belong to run {run.id}")
        if measurement.value is not None and (
            isinstance(measurement.value, bool)
            or not isinstance(measurement.value, (int, float))
            or not math.isfinite(measurement.value)
        ):
            raise ValueError("measurement.value must be a finite number or null")
        for field in ("unit", "instrument", "captured_at"):
            value = getattr(measurement, field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"measurement.{field} must be a string or null")
        if not isinstance(measurement.conditions, dict):
            raise ValueError("measurement.conditions must be an object")

    @staticmethod
    def _measurement_payload(measurement: Measurement) -> dict[str, Any]:
        payload = {
            "run_id": measurement.run_id,
            "step_id": measurement.step_id,
            "sample_id": measurement.sample_id,
            "value": measurement.value,
            "unit": measurement.unit,
            "instrument": measurement.instrument,
            "conditions": copy.deepcopy(measurement.conditions),
            "captured_at": measurement.captured_at,
        }
        try:
            json.dumps(payload, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("measurement must be JSON-serializable") from exc
        return payload
