# Ticket 01 — Protocol and run-state engine

## Outcome

Implement the pure, dependency-free engine that loads versioned protocol JSON and
moves immutable experiment runs through protocol steps. This ticket does not
store anything or interpret scientific results.

## Start here

Read `AGENTS.md`, `docs/mvp-spec.md`, `docs/contracts.md`, and
`src/labloop/contracts.py`. Treat those files as frozen. Implement only this
ticket and leave integration concerns in the handoff.

## Owned files

- `src/labloop/protocols.py`
- `tests/test_protocols.py`

Do not edit any other path. In particular, do not add example protocols, database
code, CLI code, dependencies, or new shared models.

## Required API

Implement exactly the functions declared under `labloop.protocols` in
`docs/contracts.md`:

```python
load_protocol(path: str | Path) -> Protocol
load_protocols(directory: str | Path) -> dict[str, Protocol]
current_step(protocol: Protocol, run: ExperimentRun) -> ProtocolStep
advance_run(protocol: Protocol, run: ExperimentRun, completed_step_id: str) -> ExperimentRun
start_run(run: ExperimentRun, started_at: str) -> ExperimentRun
complete_run(protocol: Protocol, run: ExperimentRun, completed_at: str) -> ExperimentRun
```

## Protocol JSON shape

Accept one JSON object with `id`, `name`, `version`, and a non-empty `steps` list.
Every step requires `id`, `title`, and `instruction`; it may include
`required_fields`, `expected_unit`, `expected_range`, `irreversible`, and
`timer_seconds`. An expected range is an object with optional numeric `minimum`
and `maximum` fields.

Reject with an actionable `ValueError`:

- missing, empty, or wrongly typed required fields;
- duplicate step IDs or duplicate protocol IDs in a directory;
- an empty step list;
- unknown step keys that would otherwise hide a typo;
- booleans where a number is expected, non-finite numbers, negative timers, or
  a range whose minimum exceeds its maximum;
- a missing/non-directory protocol directory, malformed JSON, or a directory
  containing no `*.json` protocols.

`load_protocols` reads only direct `*.json` children, in sorted filename order,
and returns a mapping keyed by protocol ID.

## State-transition rules

- All functions return new dataclass instances; never mutate inputs.
- A run must reference the supplied protocol ID and version.
- `start_run` accepts only `CREATED`, a non-empty UTC timestamp, and returns
  `RUNNING` without changing the step index.
- `current_step` accepts a running or paused run whose index exists.
- `advance_run` accepts only `RUNNING`, requires the current step ID exactly, and
  increments by one. It must not silently complete the run after the final step.
- `complete_run` accepts only `RUNNING`, only after every step has been advanced,
  and returns `COMPLETED` with the supplied timestamp.
- Completed runs cannot be restarted, advanced, or completed twice.

Use `dataclasses.replace`; do not create a state-machine class.

## Tests

Use `unittest` and `tempfile`. Cover at minimum:

1. a valid protocol is converted to frozen contract objects;
2. directory loading is deterministic;
3. malformed JSON, duplicate steps, invalid range, and unknown keys fail;
4. the happy path start → current step → advance → complete works;
5. wrong protocol/version, wrong completed step, premature completion, and a
   transition from a completed run fail;
6. the original `ExperimentRun` remains unchanged.

## Acceptance criteria

- Public behavior matches the frozen API and raises `ValueError`, not incidental
  `KeyError`, `IndexError`, or `TypeError`, for invalid external data.
- Error messages identify the protocol, step, or field that failed.
- No filesystem writes occur.
- The diff contains only the two owned files.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_protocols -v
python -m compileall -q src/labloop/protocols.py tests/test_protocols.py
git diff --check
git diff --name-only origin/main...HEAD
```

In the handoff, list the validations implemented, commands and results, and any
contract ambiguity. Do not modify a frozen file to resolve ambiguity.
