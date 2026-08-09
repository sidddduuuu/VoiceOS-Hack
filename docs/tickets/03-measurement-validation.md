# Ticket 03 — Measurement validation and follow-up questions

## Outcome

Implement the deterministic safety layer that checks a spoken measurement against
the current protocol step and returns precise follow-up questions or a deviation
warning. It must never diagnose an experiment.

## Start here

Read `AGENTS.md`, `docs/mvp-spec.md`, `docs/contracts.md`, and the contract
dataclasses. This is a pure-function ticket.

## Owned files

- `src/labloop/validation.py`
- `tests/test_validation.py`

Do not edit any other file. Do not call an LLM, database, Slack, VoiceOS, or the
network. Do not introduce a rule framework.

## Required API

```python
validate_measurement(
    step: ProtocolStep,
    measurement: Measurement,
) -> list[ValidationIssue]
```

Return a newly allocated list. Never mutate `step`, `measurement`, or its
`conditions` mapping.

## Validation behavior

Validate required fields in the order listed by `step.required_fields`, followed
by unit compatibility and range checks. Supported field names are:

- `sample_id`, `value`, `unit`, `instrument`, `captured_at` from the measurement;
- `condition.<name>` for keys inside `measurement.conditions`.

An empty/whitespace string counts as missing. `None` counts as missing. Numeric
zero is present. A value must be a finite `int`/`float`, excluding booleans.

For each missing required field, return a `BLOCKING` issue whose `field` contains
the contract field name and whose `question` is short enough to be spoken, for
example “Which sample was this for?” or “What unit should I record?”. Unknown
required-field names produce a `BLOCKING` issue explaining that the protocol
requires unsupported metadata; do not silently ignore them.

If `step.expected_unit` exists and a non-empty unit differs after trimming and
case-folding, return a `BLOCKING` issue. Do not perform unit conversion.

If a finite value and `expected_range` exist, return one `WARNING` issue when the
value falls outside the inclusive range. State the recorded value and approved
range; say only that it is outside the protocol range. Never suggest a cause,
remedy, protocol modification, or whether to continue.

If `measurement.step_id != step.id`, return a `BLOCKING` `step_id` issue before
all other issues. Empty run/step identifiers also produce blocking issues.

## Tests

Cover:

1. a complete in-range measurement returns no issues;
2. each supported missing field produces one blocking follow-up in stable order;
3. zero is accepted, while NaN, infinity, and booleans are rejected;
4. condition fields are detected without changing the input mapping;
5. matching units are case-insensitive but incompatible units block;
6. minimum and maximum bounds are inclusive;
7. an out-of-range value warns without diagnostic/remediation language;
8. step mismatch and unsupported required fields block.

## Acceptance criteria

- Output is deterministic and suitable for direct speech.
- Missing metadata and deviations remain distinct: blocking vs warning.
- No scientific inference appears in code or messages.
- Only the two owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_validation -v
python -m compileall -q src/labloop/validation.py tests/test_validation.py
git diff --check
git diff --name-only origin/main...HEAD
```

Report exact rule ordering and test results. Flag unsupported metadata names in
the handoff rather than expanding shared contracts.
