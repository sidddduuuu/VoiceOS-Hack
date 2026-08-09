"""SQLite persistence for experiment runs and append-only audit events."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .contracts import AuditEvent, EventKind, ExperimentRun, RunStatus


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY CHECK (length(trim(id)) > 0),
    protocol_id TEXT NOT NULL CHECK (length(trim(protocol_id)) > 0),
    protocol_version TEXT NOT NULL CHECK (length(trim(protocol_version)) > 0),
    operator TEXT NOT NULL CHECK (length(trim(operator)) > 0),
    sample_ids TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('created', 'running', 'paused', 'completed')),
    current_step_index INTEGER NOT NULL CHECK (
        typeof(current_step_index) = 'integer' AND current_step_index >= 0
    ),
    started_at TEXT,
    completed_at TEXT
)
"""

_EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY CHECK (length(trim(id)) > 0),
    run_id TEXT NOT NULL CHECK (length(trim(run_id)) > 0),
    kind TEXT NOT NULL CHECK (
        kind IN ('run', 'observation', 'measurement', 'checkpoint',
                 'deviation', 'supervisor', 'inventory', 'system')
    ),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    supersedes_event_id TEXT,
    UNIQUE (id, run_id),
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (supersedes_event_id, run_id) REFERENCES events(id, run_id)
)
"""


def _non_empty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: object, name: str) -> str | None:
    if value is None:
        return None
    text = _non_empty(value, name)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be a UTC ISO-8601 timestamp ending in Z")
    try:
        datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid UTC ISO-8601 timestamp") from exc
    return text


def _json(value: object, name: str) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON-serializable") from exc


class EventStore:
    """Persist current run snapshots and immutable audit events."""

    def __init__(self, path: str | Path):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("database path must be a non-empty string or Path")
        if str(path) == ":memory:":
            raise ValueError("database path must identify a durable file")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as connection:
            connection.execute(_SCHEMA)
            connection.execute(_EVENT_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def save_run(self, run: ExperimentRun) -> None:
        values = self._run_values(run)
        sql = """
            INSERT INTO runs (
                id, protocol_id, protocol_version, operator, sample_ids, status,
                current_step_index, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                protocol_id = excluded.protocol_id,
                protocol_version = excluded.protocol_version,
                operator = excluded.operator,
                sample_ids = excluded.sample_ids,
                status = excluded.status,
                current_step_index = excluded.current_step_index,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at
        """
        try:
            with self._transaction() as connection:
                connection.execute(sql, values)
        except (sqlite3.IntegrityError, sqlite3.DataError) as exc:
            raise ValueError(f"invalid run {run.id!r}: {exc}") from exc

    def get_run(self, run_id: str) -> ExperimentRun | None:
        run_id = _non_empty(run_id, "run_id")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return None if row is None else self._decode_run(row)

    def list_runs(self) -> list[ExperimentRun]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC, id ASC"
            ).fetchall()
        return [self._decode_run(row) for row in rows]

    def append(
        self,
        run_id: str,
        kind: EventKind,
        payload: dict,
        supersedes_event_id: str | None = None,
    ) -> AuditEvent:
        run_id = _non_empty(run_id, "run_id")
        try:
            event_kind = EventKind(kind)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid event kind: {kind!r}") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        payload_json = _json(payload, "payload")
        if supersedes_event_id is not None:
            supersedes_event_id = _non_empty(supersedes_event_id, "supersedes_event_id")

        event = AuditEvent(
            id=str(uuid.uuid4()),
            run_id=run_id,
            kind=event_kind,
            payload=json.loads(payload_json),
            created_at=datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
                "+00:00", "Z"
            ),
            supersedes_event_id=supersedes_event_id,
        )
        try:
            self._insert_event(event, payload_json)
        except (sqlite3.IntegrityError, sqlite3.DataError) as exc:
            raise ValueError(f"could not append event for run {run_id!r}: {exc}") from exc
        return event

    def _insert_event(self, event: AuditEvent, payload_json: str) -> None:
        with self._transaction() as connection:
            if not self._run_exists(connection, event.run_id):
                raise ValueError(f"unknown run_id: {event.run_id!r}")
            if event.supersedes_event_id is not None:
                target = connection.execute(
                    "SELECT 1 FROM events WHERE id = ? AND run_id = ?",
                    (event.supersedes_event_id, event.run_id),
                ).fetchone()
                if target is None:
                    raise ValueError(
                        f"event {event.supersedes_event_id!r} does not belong to "
                        f"run {event.run_id!r}"
                    )
            connection.execute(
                """
                INSERT INTO events (
                    id, run_id, kind, payload, created_at, supersedes_event_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.run_id,
                    event.kind.value,
                    payload_json,
                    event.created_at,
                    event.supersedes_event_id,
                ),
            )

    def list_events(self, run_id: str) -> list[AuditEvent]:
        run_id = _non_empty(run_id, "run_id")
        with closing(self._connect()) as connection:
            if not self._run_exists(connection, run_id):
                raise ValueError(f"unknown run_id: {run_id!r}")
            rows = connection.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY created_at ASC, id ASC",
                (run_id,),
            ).fetchall()
        return [self._decode_event(row) for row in rows]

    @staticmethod
    def _run_exists(connection: sqlite3.Connection, run_id: str) -> bool:
        return connection.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is not None

    @staticmethod
    def _run_values(run: ExperimentRun) -> tuple[object, ...]:
        if not isinstance(run, ExperimentRun):
            raise ValueError("run must be an ExperimentRun")
        run_id = _non_empty(run.id, "run.id")
        protocol_id = _non_empty(run.protocol_id, "run.protocol_id")
        protocol_version = _non_empty(run.protocol_version, "run.protocol_version")
        operator = _non_empty(run.operator, "run.operator")
        if not isinstance(run.sample_ids, tuple):
            raise ValueError("run.sample_ids must be a tuple")
        for index, sample_id in enumerate(run.sample_ids):
            _non_empty(sample_id, f"run.sample_ids[{index}]")
        try:
            status = RunStatus(run.status)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid run status: {run.status!r}") from exc
        if isinstance(run.current_step_index, bool) or not isinstance(run.current_step_index, int):
            raise ValueError("run.current_step_index must be a non-negative integer")
        if run.current_step_index < 0:
            raise ValueError("run.current_step_index must be a non-negative integer")
        return (
            run_id,
            protocol_id,
            protocol_version,
            operator,
            _json(run.sample_ids, "run.sample_ids"),
            status.value,
            run.current_step_index,
            _timestamp(run.started_at, "run.started_at"),
            _timestamp(run.completed_at, "run.completed_at"),
        )

    @classmethod
    def _decode_run(cls, row: sqlite3.Row) -> ExperimentRun:
        run_id = str(row["id"])
        try:
            sample_ids = json.loads(row["sample_ids"])
            if not isinstance(sample_ids, list):
                raise ValueError("sample_ids is not a JSON array")
            run = ExperimentRun(
                id=row["id"],
                protocol_id=row["protocol_id"],
                protocol_version=row["protocol_version"],
                operator=row["operator"],
                sample_ids=tuple(sample_ids),
                status=RunStatus(row["status"]),
                current_step_index=row["current_step_index"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )
            cls._run_values(run)
            return run
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"corrupt stored run {run_id!r}: {exc}") from exc

    @staticmethod
    def _decode_event(row: sqlite3.Row) -> AuditEvent:
        event_id = str(row["id"])
        run_id = str(row["run_id"])
        try:
            payload = json.loads(row["payload"])
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
            created_at = _timestamp(row["created_at"], "created_at")
            if created_at is None:
                raise ValueError("created_at is missing")
            supersedes = row["supersedes_event_id"]
            if supersedes is not None:
                _non_empty(supersedes, "supersedes_event_id")
            return AuditEvent(
                id=_non_empty(row["id"], "event id"),
                run_id=_non_empty(row["run_id"], "event run_id"),
                kind=EventKind(row["kind"]),
                payload=payload,
                created_at=created_at,
                supersedes_event_id=supersedes,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"corrupt stored event {event_id!r} for run {run_id!r}: {exc}"
            ) from exc
