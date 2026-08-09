"""Frozen, dependency-free data contracts shared by parallel MVP tickets."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class EventKind(StrEnum):
    RUN = "run"
    OBSERVATION = "observation"
    MEASUREMENT = "measurement"
    CHECKPOINT = "checkpoint"
    DEVIATION = "deviation"
    SUPERVISOR = "supervisor"
    INVENTORY = "inventory"
    SYSTEM = "system"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class ExpectedRange:
    minimum: float | None = None
    maximum: float | None = None

    def contains(self, value: float) -> bool:
        return (self.minimum is None or value >= self.minimum) and (
            self.maximum is None or value <= self.maximum
        )


@dataclass(frozen=True, slots=True)
class ProtocolStep:
    id: str
    title: str
    instruction: str
    required_fields: tuple[str, ...] = ()
    expected_unit: str | None = None
    expected_range: ExpectedRange | None = None
    irreversible: bool = False
    timer_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class Protocol:
    id: str
    name: str
    version: str
    steps: tuple[ProtocolStep, ...]


@dataclass(frozen=True, slots=True)
class ExperimentRun:
    id: str
    protocol_id: str
    protocol_version: str
    operator: str
    sample_ids: tuple[str, ...]
    status: RunStatus = RunStatus.CREATED
    current_step_index: int = 0
    started_at: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True, slots=True)
class Measurement:
    run_id: str
    step_id: str
    sample_id: str | None
    value: float | None
    unit: str | None
    instrument: str | None
    conditions: dict[str, Any] = field(default_factory=dict)
    captured_at: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    question: str
    severity: Severity


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    run_id: str
    kind: EventKind
    payload: dict[str, Any]
    created_at: str
    supersedes_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryItem:
    id: str
    name: str
    quantity: float
    unit: str
    reorder_threshold: float
    preferred_order_quantity: float


@dataclass(frozen=True, slots=True)
class PurchaseRequest:
    id: str
    item_id: str
    quantity: float
    unit: str
    status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SupervisorMessage:
    id: str
    run_id: str
    channel: str
    text: str
    direction: str
    created_at: str
    thread_id: str | None = None
