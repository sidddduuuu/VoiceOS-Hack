# Ticket 14 — Active protocol and sample stage

## Outcome

Build the primary operational section: approved protocol identity, current step,
operator, samples, progress, and the native run selector. This is the fastest
glance surface for a hands-busy researcher.

## Read first

Read the phase-two spec/reference, existing API shapes, and current dashboard DOM.
Do not create new backend fields or infer protocol instructions that were not
recorded.

## Owned files

- `web/sections/run-stage.js`
- `web/sections/run-stage.css`
- `web/previews/14-run-stage.html`
- `tests/test_run_stage.py`

Do not edit entrypoints, APIs, shared styles, or other components.

## Module contract

Export `createRunStageSection(rootElement)`. Return
`{render(viewModel), destroy()}`. The component emits a bubbling
`labloop:run-selected` `CustomEvent` with `{detail: {runId}}` only when the native
`select` value changes. It performs no fetch or state mutation.

## Information hierarchy

1. current step number/title/instruction available from run/checkpoint events;
2. approved protocol ID/version and run status;
3. operator and start time;
4. sample count and sample IDs;
5. explicit “read-only live record” explanation;
6. run selector for switching among existing runs.

Do not claim a step title/instruction exists when only an index is available. Use
“Step details not recorded” with the index. Never show generated scientific advice.

## Visual behavior

- Compose a dark continuous stage with one oversized step numeral and a lighter
  sample rail, echoing the reference's transition from open hero to dense product.
- Samples are compact tokens, not cards. Long IDs wrap or truncate with an
  accessible full label.
- Progress uses a semantic ordered path based only on known step/checkpoint events;
  unknown total steps is labeled, not guessed.
- Status uses text plus shape, not color alone.
- Native `select` remains keyboard accessible, at least 44px high, and visibly focused.

## States

Implement loading skeleton, no runs, selected run, paused/completed, malformed
record fallback, and API error. Loading content stays visible as neutral structure;
do not use a central spinner.

## Tests

Verify export/factory names, selector event shape, no direct fetch/persistence,
safe dynamic text, native select labeling, state/status copy, unknown-step handling,
long sample behavior hooks, semantic ordered progress, and local preview assets.

## Acceptance criteria

- Current step is the dominant datum at desktop and mobile sizes.
- No write action is exposed.
- Every displayed instruction is attributable to stored protocol/run data.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_run_stage -v
python -m http.server 8094 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture running, empty, completed, and long-ID states at wide/mobile sizes. Report
the event contract and any absent backend data explicitly.
