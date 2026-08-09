"""Load protocols and apply pure experiment-run transitions."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from labloop.contracts import ExpectedRange, ExperimentRun, Protocol, ProtocolStep, RunStatus


_PROTOCOL_KEYS = {"id", "name", "version", "steps"}
_STEP_KEYS = {
    "id",
    "title",
    "instruction",
    "required_fields",
    "expected_unit",
    "expected_range",
    "irreversible",
    "timer_seconds",
}
_RANGE_KEYS = {"minimum", "maximum"}


def _check_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(value.keys() - allowed)
    if unknown:
        raise ValueError(f"{label} has unknown field(s): {', '.join(unknown)}")


def _required_string(value: dict[str, Any], field: str, label: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{label} field '{field}' must be a non-empty string")
    return result


def _optional_string(value: Any, field: str, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} field '{field}' must be a non-empty string or null")
    return value


def _number(value: Any, field: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} field '{field}' must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} field '{field}' must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} field '{field}' must be a finite number")
    return result


def _parse_range(value: Any, label: str) -> ExpectedRange | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{label} field 'expected_range' must be an object or null")
    _check_keys(value, _RANGE_KEYS, f"{label} expected_range")
    minimum = _number(value["minimum"], "minimum", label) if "minimum" in value else None
    maximum = _number(value["maximum"], "maximum", label) if "maximum" in value else None
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f"{label} expected_range minimum exceeds maximum")
    return ExpectedRange(minimum=minimum, maximum=maximum)


def _parse_required_fields(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} field 'required_fields' must be a list of non-empty strings")
    if any(not isinstance(field, str) or not field.strip() for field in value):
        raise ValueError(f"{label} field 'required_fields' must contain non-empty strings")
    return tuple(value)


def _parse_step(value: Any, protocol_id: str, index: int) -> ProtocolStep:
    label = f"protocol '{protocol_id}' step {index}"
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    _check_keys(value, _STEP_KEYS, label)
    step_id = _required_string(value, "id", label)
    label = f"protocol '{protocol_id}' step '{step_id}'"
    irreversible = value.get("irreversible", False)
    if not isinstance(irreversible, bool):
        raise ValueError(f"{label} field 'irreversible' must be a boolean")
    timer = value.get("timer_seconds")
    if timer is not None and (isinstance(timer, bool) or not isinstance(timer, int) or timer < 0):
        raise ValueError(f"{label} field 'timer_seconds' must be a non-negative integer or null")
    return ProtocolStep(
        id=step_id,
        title=_required_string(value, "title", label),
        instruction=_required_string(value, "instruction", label),
        required_fields=_parse_required_fields(value.get("required_fields", []), label),
        expected_unit=_optional_string(value.get("expected_unit"), "expected_unit", label),
        expected_range=_parse_range(value.get("expected_range"), label),
        irreversible=irreversible,
        timer_seconds=timer,
    )


def _parse_protocol(value: Any, source: Path) -> Protocol:
    label = f"protocol in '{source}'"
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    _check_keys(value, _PROTOCOL_KEYS, label)
    protocol_id = _required_string(value, "id", label)
    steps_value = value.get("steps")
    if not isinstance(steps_value, list) or not steps_value:
        raise ValueError(f"protocol '{protocol_id}' field 'steps' must be a non-empty list")
    steps = tuple(_parse_step(step, protocol_id, index) for index, step in enumerate(steps_value))
    seen: set[str] = set()
    for step in steps:
        if step.id in seen:
            raise ValueError(f"protocol '{protocol_id}' has duplicate step ID '{step.id}'")
        seen.add(step.id)
    return Protocol(
        id=protocol_id,
        name=_required_string(value, "name", f"protocol '{protocol_id}'"),
        version=_required_string(value, "version", f"protocol '{protocol_id}'"),
        steps=steps,
    )


def load_protocol(path: str | Path) -> Protocol:
    """Load and validate one protocol JSON file."""
    try:
        source = Path(path)
    except TypeError as exc:
        raise ValueError("protocol path must be a string or Path") from exc
    if not source.is_file():
        raise ValueError(f"protocol file does not exist or is not a file: '{source}'")
    try:
        with source.open(encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load protocol JSON '{source}': {exc}") from exc
    return _parse_protocol(value, source)


def load_protocols(directory: str | Path) -> dict[str, Protocol]:
    """Load direct JSON children in deterministic filename order."""
    try:
        root = Path(directory)
    except TypeError as exc:
        raise ValueError("protocol directory must be a string or Path") from exc
    if not root.is_dir():
        raise ValueError(f"protocol directory does not exist or is not a directory: '{root}'")
    paths = sorted((path for path in root.glob("*.json") if path.is_file()), key=lambda path: path.name)
    if not paths:
        raise ValueError(f"protocol directory contains no '*.json' protocols: '{root}'")
    protocols: dict[str, Protocol] = {}
    for path in paths:
        protocol = load_protocol(path)
        if protocol.id in protocols:
            raise ValueError(f"duplicate protocol ID '{protocol.id}' in directory '{root}'")
        protocols[protocol.id] = protocol
    return protocols


def _validate_protocol_run(protocol: Protocol, run: ExperimentRun) -> None:
    if not isinstance(protocol, Protocol) or not isinstance(run, ExperimentRun):
        raise ValueError("protocol and run must be Protocol and ExperimentRun objects")
    _validate_run_identifiers(run)
    for field in ("id", "version"):
        value = getattr(protocol, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"protocol field '{field}' must be a non-empty string")
    if run.protocol_id != protocol.id:
        raise ValueError(f"run '{run.id}' references protocol '{run.protocol_id}', not '{protocol.id}'")
    if run.protocol_version != protocol.version:
        raise ValueError(
            f"run '{run.id}' references protocol version '{run.protocol_version}', not '{protocol.version}'"
        )


def _validate_run_identifiers(run: ExperimentRun) -> None:
    for field in ("id", "protocol_id", "protocol_version"):
        value = getattr(run, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"run field '{field}' must be a non-empty string")


def _validate_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or not value.endswith("Z"):
        raise ValueError(f"{field} must be a non-empty UTC ISO-8601 timestamp ending in 'Z'")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid UTC ISO-8601 timestamp ending in 'Z'") from exc
    if "T" not in value or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field} must be a valid UTC ISO-8601 timestamp ending in 'Z'")


def current_step(protocol: Protocol, run: ExperimentRun) -> ProtocolStep:
    """Return the active step for a running or paused run."""
    _validate_protocol_run(protocol, run)
    if run.status not in (RunStatus.RUNNING, RunStatus.PAUSED):
        raise ValueError(f"run '{run.id}' must be running or paused to have a current step")
    index = run.current_step_index
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(protocol.steps):
        raise ValueError(f"run '{run.id}' current step index {index!r} is outside protocol '{protocol.id}'")
    return replace(protocol.steps[index])


def advance_run(protocol: Protocol, run: ExperimentRun, completed_step_id: str) -> ExperimentRun:
    """Advance a running run after its exact current step is completed."""
    _validate_protocol_run(protocol, run)
    if run.status != RunStatus.RUNNING:
        raise ValueError(f"run '{run.id}' must be running to advance")
    if not isinstance(completed_step_id, str) or not completed_step_id.strip():
        raise ValueError("completed_step_id must be a non-empty string")
    step = current_step(protocol, run)
    if completed_step_id != step.id:
        raise ValueError(f"run '{run.id}' current step is '{step.id}', not '{completed_step_id}'")
    return replace(run, current_step_index=run.current_step_index + 1)


def start_run(run: ExperimentRun, started_at: str) -> ExperimentRun:
    """Start a newly created run."""
    if not isinstance(run, ExperimentRun):
        raise ValueError("run must be an ExperimentRun object")
    _validate_run_identifiers(run)
    if run.status != RunStatus.CREATED:
        raise ValueError(f"run '{run.id}' must be created to start")
    _validate_timestamp(started_at, "started_at")
    return replace(run, status=RunStatus.RUNNING, started_at=started_at)


def complete_run(protocol: Protocol, run: ExperimentRun, completed_at: str) -> ExperimentRun:
    """Complete a running run after every protocol step was advanced."""
    _validate_protocol_run(protocol, run)
    if run.status != RunStatus.RUNNING:
        raise ValueError(f"run '{run.id}' must be running to complete")
    index = run.current_step_index
    if isinstance(index, bool) or not isinstance(index, int) or index != len(protocol.steps):
        raise ValueError(f"run '{run.id}' cannot complete before every protocol step is advanced")
    _validate_timestamp(completed_at, "completed_at")
    return replace(run, status=RunStatus.COMPLETED, completed_at=completed_at)
