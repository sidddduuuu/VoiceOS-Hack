# Ticket 05 — Inventory tracking and restock requests

## Outcome

Implement local inventory consumption and safe restock-request creation. The MVP
may draft a pending request; it must never place or approve an order.

## Start here

Read the shared spec, contracts, repository instructions, and dataclasses. This
ticket owns a separate SQLite-backed component that may share the same database
file with `EventStore` but not its tables.

## Owned files

- `src/labloop/inventory.py`
- `tests/test_inventory.py`

Do not edit anything else. Do not implement vendor APIs, payments, email, Slack,
purchase approval, or a generic database layer.

## Required API

Implement `InventoryStore` exactly as declared in `docs/contracts.md`.

Create `inventory_items` and `purchase_requests` tables with parameterized SQL,
foreign keys, WAL mode, a busy timeout, and explicit transactions. Open a
connection per operation. Encode no values with pickle.

## Validation and behavior

- Reject empty IDs/names/units, booleans or non-finite quantities, negative item
  quantity or reorder threshold, and non-positive preferred order quantity.
- `upsert_item` inserts or updates the complete current item snapshot.
- `get_item` returns `None` when absent. `list_items` sorts case-insensitively by
  name and then ID.
- `consume` requires a known item, positive finite amount, and a unit matching
  after trimming/case-folding. Do not convert units.
- Consumption and any request creation occur in one transaction. Reject usage
  that would make inventory negative.
- If quantity changes from above the reorder threshold to at/below it, create one
  `pending` request for `preferred_order_quantity`.
- If the item is already at/below threshold and has no pending request, consumption
  may create one pending request.
- Never create a second pending request for the same item. A non-pending historical
  request does not prevent a new threshold-triggered pending request.
- `list_purchase_requests(None)` returns all; a provided status must be a non-empty
  string. Sort newest first then ID.
- The public API exposes no approve, send, purchase, update-status, or delete method.

Generate UUIDs and UTC `Z` timestamps internally. Translate expected integrity
failures to `ValueError`; do not swallow operational failures.

## Tests

Use a temporary SQLite file. Cover:

1. item insert/update and complete round-trip;
2. deterministic list ordering;
3. normal consumption without a request;
4. exact threshold crossing creates one correctly sized pending request;
5. repeated consumption does not duplicate a pending request;
6. unit mismatch, non-positive/non-finite amount, unknown item, and negative stock fail;
7. a failed transaction leaves both item quantity and requests unchanged;
8. status filtering works and SQL injection-like strings are harmless values.

## Acceptance criteria

- No external purchase is possible through this component.
- Quantity update and request creation are atomic.
- Inputs and SQL are safe at their boundaries.
- Only the two owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_inventory -v
python -m compileall -q src/labloop/inventory.py tests/test_inventory.py
git diff --check
git diff --name-only origin/main...HEAD
```

Report the threshold policy, transaction behavior, commands/results, and any
schema choice relevant to integration.
