# LabLoop

LabLoop is a stateful research copilot for hands-busy laboratory work. VoiceOS
turns spoken observations into MCP tool calls; LabLoop maintains protocol state,
asks for missing metadata, records an append-only audit trail, coordinates with a
supervisor, and prepares inventory restock requests.

This branch contains the shared foundation and ten parallel implementation
tickets. Read [the MVP specification](docs/mvp-spec.md), [the frozen contracts](docs/contracts.md),
and [the ticket index](docs/tickets/README.md) before implementation.

## Foundation check

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Parallel workflow

1. Merge this foundation into `main`.
2. Create one Conductor workspace per ticket from the updated `main`.
3. Give each workspace exactly one file from `docs/tickets/`.
4. Merge completed ticket branches in numeric order.
5. Run a final integration pass after all ten branches are present.
