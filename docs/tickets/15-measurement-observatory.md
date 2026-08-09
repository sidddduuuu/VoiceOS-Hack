# Ticket 15 — Measurement observatory

## Outcome

Turn recorded measurements into a high-signal scientific readout that highlights
recency, sample attribution, unit completeness, instruments, and protocol-range
status without chart theater or diagnosis.

## Read first

Read the full-build/reference docs plus `contracts.py`, `validation.py`, and current
measurement event rendering. Use only event payloads returned by the dashboard API.

## Owned files

- `web/sections/measurements.js`
- `web/sections/measurements.css`
- `web/previews/15-measurements.html`
- `tests/test_measurement_observatory.py`

Do not edit APIs, validation rules, entrypoints, shared design, or other sections.

## Module contract

Export `createMeasurementsSection(rootElement)`. Return
`{render(viewModel), destroy()}` and consume measurement/deviation events without
mutating or sorting the original arrays in place.

## Display model

- Latest valid reading receives the largest typographic emphasis with tabular
  numerals and adjacent unit—not a detached hero metric card.
- A compact chronological strip shows up to eight recent readings with sample,
  instrument, and time.
- Missing value/unit/instrument/sample remains visibly marked as “not recorded”.
- Range information appears only when present in the stored event/issue payload.
- Out-of-range data is labeled “outside approved protocol range”; never infer cause,
  remediation, trend, or whether the researcher should continue.
- Preserve the exact recorded numeric/string representation where possible.

## Visualization

Use a restrained horizontal range track only when minimum/maximum/value are all
finite. Clamp the visual marker to the track while labeling the true value outside
the range. For incomplete/unbounded data, show textual comparison instead. Do not
invent axes, averages, sparklines, or a chart dependency.

New readings may enter with opacity/vertical transform; changed values may briefly
pulse once. CSS hooks must work with ticket 19 reduced-motion rules.

## States

Cover loading skeleton, zero readings, one reading, eight-plus readings, incomplete
metadata, out-of-range, malformed/non-finite payload, and disconnected data.

## Tests

Verify exact export, chronological copy without input mutation, safe text insertion,
finite range-track guards, missing metadata labels, non-diagnostic warning wording,
tabular numeric hooks, no canvas/chart/fetch/timer/innerHTML, semantic list/table
structure, and isolated preview assets.

## Acceptance criteria

- A judge can identify latest value, unit, sample, and whether it needs attention
  from several feet away.
- Scientific uncertainty is shown, not repaired or hidden.
- Component remains useful with no expected range.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_measurement_observatory -v
python -m http.server 8095 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture normal, incomplete, and out-of-range previews. Report data assumptions and
non-diagnostic copy used.
