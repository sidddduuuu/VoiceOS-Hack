# Ticket 18 — Immutable experiment timeline

## Outcome

Build the evidence surface that proves LabLoop preserves every observation,
measurement, checkpoint, deviation, supervisor message, inventory event, and
correction without silently rewriting history.

## Read first

Read the phase-two docs, `AuditEvent` contract, event-store append-only rules, and
the existing timeline renderer.

## Owned files

- `web/sections/timeline.js`
- `web/sections/timeline.css`
- `web/previews/18-timeline.html`
- `tests/test_immutable_timeline.py`

Do not edit storage, APIs, entrypoints, shared design, or other sections.

## Module contract

Export `createTimelineSection(rootElement)` and return
`{render(viewModel), destroy()}`. Sort a copy chronologically with deterministic ID
tie-breaking. Never mutate payloads/events.

## Timeline behavior

- Group events by local calendar date while preserving exact timestamp display and
  machine-readable `datetime` attributes.
- Each event shows kind, source attribution, concise safe summary, sample/step when
  stored, and timestamp.
- Kind has a distinct marker shape/label; do not rely on color alone.
- A correction remains a separate event and visibly points to its exact
  `supersedes_event_id`. The superseded event stays fully visible and receives a
  “Superseded by correction” annotation only when a matching event exists.
- Missing correction targets are labeled “Original record unavailable”; do not hide
  or rewire them.
- JSON-like payload values are summarized defensively with length limits while
  retaining access to important text. Never render raw HTML.

## Visual and motion behavior

Use one continuous ruled record with generous date breaks, inspired by editorial
research listings rather than feed cards. New events may enter with a short
opacity/translate transition. Existing rows do not replay motion every second.
Ticket 19 provides global “seen event ID” helpers/reduced-motion policy if needed.

## Scale and states

Support zero, one, and at least 500 events without recursion or quadratic correction
lookup. Render the most recent 100 initially with a truthful “100 of N shown” note;
ticket 20 may expose progressive reveal only if necessary. Loading/error/empty and
malformed events require safe states.

## Tests

Verify export, non-mutating deterministic ordering, date grouping, correction links
using an O(n) map, preserved superseded rows, missing-target behavior, safe text and
length limits, no innerHTML/fetch/timer, semantic `ol`/`time`, 500-event handling,
and local preview assets.

## Acceptance criteria

- Corrections enhance provenance without replacing the original record.
- Large histories remain responsive and understandable.
- Event content cannot inject markup.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_immutable_timeline -v
python -m http.server 8098 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture empty, corrected, hostile-payload, and 500-event previews. Report the scale
ceiling, truncation language, and correction algorithm.
