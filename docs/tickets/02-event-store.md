# Ticket 02 — SQLite experiment audit store

## Outcome

Build the durable local store for experiment runs and append-only audit events.
The database is the source of truth shared later by the MCP server and dashboard.

## Start here

Read `AGENTS.md`, `docs/mvp-spec.md`, `docs/contracts.md`, and
`src/labloop/contracts.py`. Implement the frozen `EventStore` contract only.

## Owned files

- `src/labloop/storage.py`
- `tests/test_storage.py`

Do not edit other files. Do not implement protocol logic, inventory, migrations,
an ORM, a repository interface, or a web endpoint.

## Required API

Implement `EventStore` exactly as declared in `docs/contracts.md`.

The constructor accepts a string or `Path`, rejects an empty path, creates parent
directories when needed, opens connections per operation, and initializes two
tables with `CREATE TABLE IF NOT EXISTS`:

- `runs`: one row per `ExperimentRun`, with sample IDs encoded as JSON;
- `events`: one immutable row per `AuditEvent`, with payload encoded as JSON and
  an optional `supersedes_event_id` self-reference.

Use SQLite foreign keys, parameterized SQL, explicit transactions, and row
factories. Enable WAL mode and a five-second busy timeout on each connection.
This MVP needs no migration framework or global connection pool.

## Behavioral requirements

- `save_run` validates non-empty identifiers and operator, valid enum/status,
  non-negative integer step index, and JSON-serializable values. Insert or update
  the current run snapshot atomically.
- `get_run` returns `None` for an unknown ID and reconstructs immutable tuples and
  enums. Corrupt stored data raises `ValueError` with the run ID.
- `list_runs` is ordered newest-started first, then by ID for determinism.
- `append` rejects an unknown run, empty identifiers, non-dict or non-JSON payload,
  and invalid event kind. It generates UUID and UTC `Z` timestamp internally.
- When `supersedes_event_id` is supplied, the target must exist in the same run.
- `list_events` rejects an unknown run and returns chronological creation order,
  breaking ties by event ID.
- There is no event update/delete API. Do not add one.
- Never interpolate values into SQL or swallow `sqlite3` exceptions. Translate
  expected integrity/data errors to actionable `ValueError`; preserve unexpected
  operational errors.

Add useful database constraints for non-empty IDs and non-negative step indexes.
Use foreign keys to prevent orphaned events. Do not store Python repr strings or
pickle.

## Tests

Use `unittest.TemporaryDirectory`. Cover:

1. schema initialization and round-trip of every `ExperimentRun` field;
2. save updates the run snapshot without creating duplicates;
3. list ordering and unknown-run behavior;
4. event append/list round-trip for nested JSON payloads;
5. correction references an event in the same run and rejects cross-run targets;
6. non-serializable payload, unknown run, and invalid path/input failures;
7. a failed append leaves no partial row.

## Acceptance criteria

- Two `EventStore` instances can read/write the same file sequentially.
- Scientific events are append-only through the public API.
- All SQL values are parameterized and all writes are transactional.
- No secrets, researcher data, or generated `.db` file is committed.
- The diff contains only the two owned files.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_storage -v
python -m compileall -q src/labloop/storage.py tests/test_storage.py
git diff --check
git diff --name-only origin/main...HEAD
```

Report schema choices, verification results, and any concurrency ceiling. Do not
add a connection pool unless a measured integration failure requires it.
