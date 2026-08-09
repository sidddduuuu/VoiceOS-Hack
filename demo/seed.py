"""Seed clearly synthetic, local-only data for the LabLoop demo."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

from labloop.contracts import EventKind, InventoryItem, Measurement


WORKSPACE = Path(__file__).resolve().parents[1]
SYNTHETIC_OPERATOR = "Synthetic Demo Operator"
SYNTHETIC_SAMPLE_IDS = tuple(f"SYNTHETIC-SAMPLE-{number:02d}" for number in range(1, 7))
SYNTHETIC_INVENTORY = (
    {
        "id": "synthetic-demo-reagent",
        "name": "Synthetic Demo Reagent",
        "quantity": 12.0,
        "unit": "demo units",
        "reorder_threshold": 10.0,
        "preferred_order_quantity": 25.0,
    },
)


def validate_database_path(raw_path: str | Path, workspace: Path = WORKSPACE) -> Path:
    """Return a safe database path contained by the workspace."""
    workspace = workspace.resolve(strict=True)
    candidate = Path(os.path.abspath(os.fspath(raw_path)))
    try:
        relative = candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("database path must be inside the current workspace") from exc

    current = workspace
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("database path must not contain symlinks")

    try:
        candidate.resolve(strict=False).relative_to(workspace)
    except ValueError as exc:
        raise ValueError("database path must resolve inside the current workspace") from exc
    if candidate.exists() and not candidate.is_file():
        raise ValueError("database path must not be a directory")
    return candidate


def prepare_database(database: Path, reset: bool) -> None:
    """Refuse replacement by default; otherwise remove only SQLite's exact files."""
    paths = (database, Path(f"{database}-wal"), Path(f"{database}-shm"))
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"refusing symlink: {path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"refusing non-file SQLite path: {path}")
    if database.exists() and not reset:
        raise ValueError("database already exists; pass --reset to replace it")
    if reset:
        for path in paths:
            if path.exists():
                path.unlink()


def _record_step(service: Any, run_id: str, step_id: str) -> Any:
    if step_id == "setup-metadata":
        service.record_measurement(
            Measurement(
                run_id=run_id,
                step_id=step_id,
                sample_id=SYNTHETIC_SAMPLE_IDS[0],
                value=None,
                unit=None,
                instrument=None,
                conditions={
                    "kit_lot": "SYNTHETIC-KIT-LOT-001",
                    "data_classification": "synthetic",
                },
                captured_at="2026-01-15T12:00:05Z",
            )
        )
    elif step_id == "record-observation":
        return service.record_observation(
            run_id,
            "Synthetic observation: the demo record appears normal.",
            SYNTHETIC_SAMPLE_IDS[0],
        )
    elif step_id == "measure-demo-signal":
        service.record_measurement(
            Measurement(
                run_id=run_id,
                step_id=step_id,
                sample_id=SYNTHETIC_SAMPLE_IDS[0],
                value=15.0,
                unit="demo units",
                instrument="SYNTHETIC-INSTRUMENT-01",
                conditions={"data_classification": "synthetic"},
                captured_at="2026-01-15T12:00:20Z",
            )
        )
    return None


def _seed_historical_run(service: Any, protocol: Any, events: Any) -> str:
    run = service.begin_experiment(
        protocol.id,
        SYNTHETIC_OPERATOR,
        list(SYNTHETIC_SAMPLE_IDS),
        "2026-01-15T12:00:00Z",
    )
    observation = None
    for step in protocol.steps:
        observation = _record_step(service, run.id, step.id) or observation
        service.complete_checkpoint(run.id, step.id)
    if observation is not None:
        service.correct_event(
            run.id,
            observation.id,
            {
                "note": "Synthetic corrected observation: the demo record appears clear.",
                "sample_id": SYNTHETIC_SAMPLE_IDS[0],
                "source": "researcher",
                "correction_reason": "Synthetic transcription correction",
            },
        )
    service.finish_experiment(run.id, "2026-01-15T12:03:00Z")
    events.append(
        run.id,
        EventKind.SUPERVISOR,
        {
            "source": "synthetic fallback supervisor",
            "direction": "inbound",
            "channel": "synthetic-demo-supervision",
            "thread_id": "synthetic-demo-thread",
            "text": "Synthetic fallback reply: follow the institution's approved protocol.",
        },
    )
    return run.id


def seed_database(database: Path, reset: bool = False) -> dict[str, int]:
    """Seed inventory and one completed synthetic run through public APIs."""
    database = validate_database_path(database)
    if database.exists() and not reset:
        raise ValueError("database already exists; pass --reset to replace it")
    try:
        from labloop.inventory import InventoryStore
        from labloop.protocols import load_protocol
        from labloop.service import LabLoopService
        from labloop.storage import EventStore
    except ImportError as exc:
        raise RuntimeError("seed requires merged LabLoop tickets 01, 02, 04, and 05") from exc

    prepare_database(database, reset)
    inventory = InventoryStore(database)
    for values in SYNTHETIC_INVENTORY:
        inventory.upsert_item(InventoryItem(**values))
    protocol_path = WORKSPACE / "protocols" / "dna-extraction-demo.json"
    protocol = load_protocol(protocol_path)
    events = EventStore(database)
    run_id = _seed_historical_run(
        LabLoopService(database, protocol_path.parent), protocol, events
    )
    return {
        "runs": len(events.list_runs()),
        "events": len(events.list_events(run_id)),
        "inventory_items": len(inventory.list_items()),
        "pending_requests": len(inventory.list_purchase_requests("pending")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="target SQLite path")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="replace the exact database and SQLite sidecars",
    )
    args = parser.parse_args(argv)
    try:
        database = validate_database_path(args.db)
        counts = seed_database(database, args.reset)
    except (RuntimeError, ValueError, OSError) as exc:
        parser.exit(2, f"seed error: {exc}\n")

    print(f"workspace: {WORKSPACE}")
    print(f"database: {database}")
    print("records: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
