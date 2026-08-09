# Ticket 04 — Experiment orchestration service

## Outcome

Compose the frozen protocol, event-store, and validation APIs into one application
service. This is the stateful core used later by VoiceOS; it owns workflow, not I/O
channels such as Slack, speech, inventory, or HTTP.

## Start here

Read all shared docs and contracts. Tickets 01–03 may not yet be merged in your
workspace, so implement against their documented APIs and use mocks in tests.
Do not copy their implementations.

## Owned files

- `src/labloop/service.py`
- `tests/test_service.py`

Do not edit other paths or add adapters/dependencies.

## Required API

Implement `LabLoopService` exactly as declared in `docs/contracts.md`.

At construction, load protocols once with `load_protocols` and create one
`EventStore`. Fail fast when there are no usable protocols. Keep these as simple
instance attributes; no dependency-injection framework is needed.

## Workflow rules

### Begin

- Validate a known protocol, non-empty operator, and at least one unique non-empty
  sample ID. Preserve sample order after trimming.
- Generate a UUID run with the loaded protocol version, start it immediately using
  the supplied/default UTC time, save it, and append a `RUN` event containing the
  protocol ID/version, operator, and sample IDs.
- If persistence fails, do not return a run that was not stored.

### Read

- `get_run` raises `ValueError` for unknown/empty IDs.
- `get_current_step` resolves the run's exact protocol version and delegates to
  the protocol engine. It must never silently substitute a newer version.

### Record

- Observations require a non-empty note. Optional sample IDs must belong to the
  run. Store an `OBSERVATION` event with explicit source `researcher`.
- Measurements must belong to a known running run, its current step, and a known
  optional sample. Delegate validation. Append the raw `MEASUREMENT` event even
  when issues exist, then append one `DEVIATION` event containing all issues if
  any issue is returned. Preserve all supplied fields, including conditions.
- Do not automatically advance a step after logging data.

### Checkpoint and completion

- `complete_checkpoint` delegates the transition, saves the new run, then appends
  a `CHECKPOINT` event with the completed step ID and next step index.
- `finish_experiment` delegates completion, saves, and appends a `RUN` completion
  event. It cannot infer uncompleted steps.

### Correction

- Confirm the target event belongs to the run. Reject empty/non-dict/non-JSON
  replacement payloads.
- Append an event of the same kind with `supersedes_event_id`; never overwrite.
- Include `correction_reason` only if supplied in the replacement data. Do not
  invent a reason or change the original event.

Use one small `_utc_now()` helper and explicit conversion helpers only where
needed. Do not add a unit-of-work abstraction. The SQLite methods already provide
transactional individual writes; document the MVP's multi-write ceiling.

## Tests

Patch `labloop.service.load_protocols`, `EventStore`, and
`validate_measurement` with `unittest.mock`. Cover:

1. begin validates inputs and emits the correct run event;
2. current-step lookup honors exact protocol version;
3. observations reject unknown samples;
4. measurements store raw input and one consolidated deviation event;
5. no validation issues means no deviation event;
6. checkpoints and completion save before returning;
7. corrections append and supersede without update/delete;
8. downstream failures propagate clearly and no success value is returned.

## Acceptance criteria

- The service contains no Slack, HTTP, subprocess, speech, inventory, or MCP code.
- All state transitions go through ticket 01 APIs and all records through ticket 02.
- User-provided data is validated at this boundary.
- Only the owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_service -v
python -m compileall -q src/labloop/service.py tests/test_service.py
git diff --check
git diff --name-only origin/main...HEAD
```

Report mocked dependencies, event payload shapes, verification results, and the
known lack of a cross-method multi-write transaction for this MVP.
