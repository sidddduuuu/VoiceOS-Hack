# Ticket 17 — Inventory flow and pending restock visualization

## Outcome

Visualize reagent/material levels as part of the laboratory process and make the
human-approval boundary unmistakable when inventory crosses a threshold.

## Read first

Read the full-build/reference docs, inventory contracts/store behavior, and current
dashboard API shape. The product creates pending requests; it never places orders.

## Owned files

- `web/sections/inventory.js`
- `web/sections/inventory.css`
- `web/previews/17-inventory.html`
- `tests/test_inventory_flow.py`

Do not edit inventory Python, APIs, entrypoints, shared design, or other sections.

## Module contract

Export `createInventorySection(rootElement)`. Return
`{render(viewModel), destroy()}` and read only `viewModel.inventory`.

## Display behavior

- Show each item name, current quantity/unit, reorder threshold, and whether one
  pending request exists.
- Use a physical reservoir/flow metaphor: a simple vertical or horizontal fill
  track with tick marks for current level and threshold. It must remain legible as
  text when CSS is unavailable.
- Compute percentages only when values are finite and a meaningful scale can be
  derived. Never divide by zero or imply capacity when none is stored.
- At/below threshold uses “Below next-run threshold”. A request uses exactly
  “Pending request — human approval required”. Never say ordered, purchased,
  approved, on the way, or restocked.
- Associate requests by exact `item_id`; ignore malformed/unmatched requests safely.
- Preserve units without conversion.

## Visual and motion behavior

Use a continuous lab-supply rail with varied row lengths, not equal inventory cards.
On a newly low item, the reservoir marker may settle with transform/opacity and the
pending request badge may resolve once. No looping alarm, flashing red, or animated
width/height. Ticket 19 owns final reduced-motion behavior.

## States

Cover no inventory, sufficient stock, exactly threshold, below threshold without a
request, pending request, malformed/non-finite quantity, long names/units, and API
error. Malformed numbers show “Quantity unavailable”; never coerce to zero.

## Tests

Verify factory/export contract, exact approval wording and prohibited purchase
claims, finite math guards, item/request association, safe text insertion, no fetch/
timer/innerHTML, no width/height animation, semantic meter/text fallback, and local
preview assets.

## Acceptance criteria

- Inventory status is understandable without color or animation.
- The UI cannot imply autonomous purchasing.
- Unknown units/data are shown honestly.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_inventory_flow -v
python -m http.server 8097 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture sufficient, threshold, pending, and malformed states. Report wording and
percentage rules exactly.
