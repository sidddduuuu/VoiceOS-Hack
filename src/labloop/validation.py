"""Pure validation for measurements recorded against protocol steps."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from labloop.contracts import Measurement, ProtocolStep, Severity, ValidationIssue


_QUESTIONS = {
    "sample_id": "Which sample was this for?",
    "value": "What numeric value should I record?",
    "unit": "What unit should I record?",
    "instrument": "Which instrument was used?",
    "captured_at": "When was this measured?",
}


def _missing(value: Any) -> bool:
    return value is None or isinstance(value, str) and not value.strip()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _blocking(field: str, question: str) -> ValidationIssue:
    return ValidationIssue(field=field, question=question, severity=Severity.BLOCKING)


def _approved_range(step: ProtocolStep) -> str:
    expected = step.expected_range
    assert expected is not None
    if expected.minimum is None:
        return f"at most {expected.maximum}"
    if expected.maximum is None:
        return f"at least {expected.minimum}"
    return f"{expected.minimum} to {expected.maximum}"


def _required_issues(
    step: ProtocolStep, measurement: Measurement
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field in step.required_fields:
        if field in _QUESTIONS:
            value = getattr(measurement, field)
            missing = not _finite_number(value) if field == "value" else _missing(value)
            if missing:
                issues.append(_blocking(field, _QUESTIONS[field]))
        elif field.startswith("condition.") and field.removeprefix("condition."):
            name = field.removeprefix("condition.")
            conditions = measurement.conditions
            value = conditions.get(name) if isinstance(conditions, Mapping) else None
            if _missing(value):
                issues.append(_blocking(field, f"What was the {name} condition?"))
        else:
            question = f"The protocol requires unsupported metadata: {field}."
            issues.append(_blocking(field, question))
    return issues


def validate_measurement(step: ProtocolStep, measurement: Measurement) -> list[ValidationIssue]:
    """Return ordered validation issues without changing either input."""
    issues: list[ValidationIssue] = []
    step_mismatch = measurement.step_id != step.id
    if step_mismatch:
        question = "The measurement step does not match the protocol step."
        issues.append(_blocking("step_id", question))
    if _missing(measurement.run_id):
        issues.append(_blocking("run_id", "Which experiment run is this for?"))
    if not step_mismatch and (_missing(step.id) or _missing(measurement.step_id)):
        issues.append(_blocking("step_id", "Which protocol step is this for?"))

    issues.extend(_required_issues(step, measurement))
    if (
        "value" not in step.required_fields
        and measurement.value is not None
        and not _finite_number(measurement.value)
    ):
        issues.append(_blocking("value", _QUESTIONS["value"]))

    unit = measurement.unit
    if step.expected_unit is not None and not _missing(unit):
        actual = unit.strip().casefold() if isinstance(unit, str) else None
        expected = step.expected_unit.strip().casefold()
        if actual != expected:
            issues.append(
                _blocking(
                    "unit",
                    f"Unit {unit} does not match the protocol unit {step.expected_unit}.",
                )
            )

    value = measurement.value
    expected_range = step.expected_range
    if _finite_number(value) and expected_range and not expected_range.contains(value):
        issues.append(
            ValidationIssue(
                field="value",
                question=(
                    f"Recorded value {value} is outside the approved protocol range "
                    f"{_approved_range(step)}."
                ),
                severity=Severity.WARNING,
            )
        )
    return issues
