# Implementation ticket archive

Tickets 01–10 were used for the parallel MVP build. They remain here as the
implementation record; the components are now integrated.

| Ticket | Component | Primary owned path |
| --- | --- | --- |
| 01 | Protocol and run-state engine | `src/labloop/protocols.py` |
| 02 | SQLite audit/event store | `src/labloop/storage.py` |
| 03 | Measurement validation | `src/labloop/validation.py` |
| 04 | Experiment orchestration service | `src/labloop/service.py` |
| 05 | Inventory and restock requests | `src/labloop/inventory.py` |
| 06 | Slack supervisor loop | `src/labloop/supervisor.py` |
| 07 | macOS wake and speech bridge | `src/labloop/audio.py`, `native/` |
| 08 | VoiceOS MCP adapter | `src/labloop/mcp_server.py` |
| 09 | Read-only live dashboard | `src/labloop/dashboard.py`, `web/` |
| 10 | DNA-extraction demo data and runbook | `protocols/`, `demo/` |

These branches are code-independent by file ownership, not logically unrelated.
Tickets 04, 08, and 09 code against the frozen contracts and may use mocks until
the other modules are merged. The final integration pass resolves wiring only;
ticket branches must not modify shared contracts.

Recommended merge order: `01, 02, 03, 05, 06, 07, 04, 08, 09, 10`.

## Phase two — full visual build

Tickets 11–20 were completed as one integrated pass to avoid temporary module
scaffolding. Their acceptance criteria now live in `web/`,
`src/labloop/dashboard.py`, and `tests/test_full_ui.py`.

Read `docs/full-build-spec.md` and `docs/worldlabs-ui-reference.md` before every
phase-two ticket.

| Ticket | Component | Primary owned path |
| --- | --- | --- |
| 11 | Design tokens and spatial shell | `web/design/tokens.css`, `web/design/shell.css` |
| 12 | Editorial hero and lab apparatus | `web/sections/hero.*`, `web/assets/lab-apparatus.svg` |
| 13 | VoiceOS/LabLoop presence band | `web/sections/voice-presence.*` |
| 14 | Active protocol and sample stage | `web/sections/run-stage.*` |
| 15 | Measurement observatory | `web/sections/measurements.*` |
| 16 | Deviations and supervisor relay | `web/sections/safety-supervisor.*` |
| 17 | Inventory flow | `web/sections/inventory.*` |
| 18 | Immutable experiment timeline | `web/sections/timeline.*` |
| 19 | Motion, responsive, and reduced-motion layer | `web/design/motion.css`, `web/design/responsive.css`, `web/motion.js` |
| 20 | Final UI integration and visual QA | Existing dashboard entry/server files |

The ticket files are retained as design and QA traceability, not as outstanding
workspace tasks.
