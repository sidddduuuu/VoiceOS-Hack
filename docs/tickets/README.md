# Parallel implementation tickets

Each ticket is designed for one Conductor workspace created from the foundation
branch after it is merged to `main`.

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
