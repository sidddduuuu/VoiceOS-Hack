# Ticket 09 — Read-only live lab dashboard

## Outcome

Build a local, judge-visible dashboard that shows current experiment state and the
immutable timeline while the researcher operates hands-free. It is an observability
surface, not a second control interface.

## Start here

Read the shared spec/contracts and code to `EventStore`/`InventoryStore` documented
APIs. Those modules may not exist yet; mock or defer imports where needed in tests.

## Owned files

- `src/labloop/dashboard.py`
- `tests/test_dashboard.py`
- `web/index.html`
- `web/app.js`
- `web/styles.css`

Do not edit other paths. Do not add React, a bundler, CSS framework, websocket
library, write endpoint, authentication system, or chart dependency.

## Server behavior

Implement `main()` with `http.server.ThreadingHTTPServer` and a focused request
handler. Bind only to `127.0.0.1`. Read:

- `LABLOOP_DB_PATH`, default `./labloop.db`;
- `LABLOOP_DASHBOARD_PORT`, default `8765`, integer 1024–65535.

Serve the three static assets with correct content types and security headers:
`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and
`Cache-Control: no-store`.

Expose read-only JSON:

- `GET /api/runs` — run summaries;
- `GET /api/runs/<run_id>` — full run plus chronological events;
- `GET /api/inventory` — inventory and pending requests;
- `GET /api/health` — `{ "status": "ok" }`.

Only `GET` and `HEAD` are allowed. Return 405 for writes, 404 for unknown resources,
400 for malformed/oversized IDs, and safe JSON 500 responses without tracebacks or
filesystem paths. Apply a small response-size ceiling and JSON-encode all dynamic
content. Prevent path traversal by using an explicit static route mapping rather
than joining arbitrary URL paths.

## Interface requirements

Create a distinctive lab-console UI, not a default template:

- current protocol, operator, run status, and current step are visually dominant;
- sample chips, latest measurements, deviations, supervisor messages, inventory
  warnings, and pending restock requests are visible without editing controls;
- an immutable timeline labels source/type/time and marks corrections without
  hiding superseded records;
- auto-refresh every second with `fetch`, preserve selected run, and show
  disconnected/empty/loading/error states;
- use semantic HTML, keyboard-accessible run selection, visible focus, sufficient
  contrast, and `prefers-reduced-motion`;
- use only system fonts, CSS, and small compositor-only transitions;
- escape all untrusted values by assigning `textContent`, never `innerHTML`.

Keep JavaScript simple: one state object, fetch/render functions, no client router
or component abstraction.

## Tests

Use `unittest`, temporary files, mocked stores, and an ephemeral server port. Cover:

1. health/static/API success responses and content types;
2. run/event serialization of enums, tuples, and nested payloads;
3. unknown/malformed run IDs and store failures return safe errors;
4. POST/PUT/DELETE are rejected;
5. traversal attempts cannot read workspace files;
6. security headers appear on static and JSON responses;
7. no API mutates the mocked stores.

## Acceptance criteria

- The dashboard is useful during the 2–3 minute demo without keyboard input.
- There are no write controls or write routes.
- Dynamic researcher/Slack content cannot inject HTML.
- Only the five owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_dashboard -v
python -m compileall -q src/labloop/dashboard.py tests/test_dashboard.py
git diff --check
git diff --name-only origin/main...HEAD
```

Manually load the dashboard with representative mocked/merged data at narrow and
wide widths. Report the tested URL, states inspected, commands/results, and any
integration data assumption.
