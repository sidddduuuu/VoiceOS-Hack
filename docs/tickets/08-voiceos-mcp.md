# Ticket 08 — VoiceOS custom-app MCP adapter

## Outcome

Expose LabLoop's application capabilities as a local MCP server that VoiceOS Agent
Mode can call from natural speech. VoiceOS connects by launching this process over
`stdio`; no VoiceOS REST API or separate CLI is needed.

Official integration reference:
`https://www.voiceos.com/guide/build-mcp-integration`

## Start here

Read every frozen contract plus the MVP spec. Other feature tickets may not yet be
merged, so code to the documented APIs and mock them in tests. Do not duplicate
their logic inside this adapter.

## Owned files

- `src/labloop/mcp_server.py`
- `tests/test_mcp_server.py`

Do not edit any other file, including `pyproject.toml`. The frozen project already
contains the `mcp` dependency.

## Required API and transport

Implement `build_server(db_path, protocol_dir) -> FastMCP` and `main() -> None`.
`main` reads `LABLOOP_DB_PATH` and `LABLOOP_PROTOCOL_DIR`, applies documented
defaults, builds the server, and calls `run(transport="stdio")`.

No logging or ordinary output may be written to stdout because it would corrupt
MCP transport. Diagnostic output, if essential, goes to stderr and contains no
secrets or scientific payloads.

Expose exactly these MCP tool names:

1. `start_experiment(protocol_id, operator, sample_ids)`
2. `get_current_step(run_id)`
3. `record_observation(run_id, note, sample_id=None)`
4. `record_measurement(run_id, step_id, sample_id, value, unit, instrument=None,
   conditions=None, captured_at=None)`
5. `complete_step(run_id, step_id)`
6. `correct_record(run_id, event_id, replacement)`
7. `finish_experiment(run_id)`
8. `consume_inventory(item_id, amount, unit)`
9. `ask_supervisor(run_id, question)`
10. `check_supervisor_replies(run_id, thread_id)`

## Tool behavior

- Tool docstrings are part of VoiceOS tool selection. State when to call the tool,
  required context, and safety boundary in plain language.
- Validate and normalize all tool arguments before constructing contract objects.
  Reject empty IDs, invalid list/dict shapes, booleans/non-finite measurement
  values, and malformed timestamps with a concise error.
- Instantiate one `LabLoopService` and one `InventoryStore` inside `build_server`.
  Do not create new stores per tool call.
- Slack tools read `SLACK_BOT_TOKEN`/`SLACK_CHANNEL_ID` only when invoked and return
  a clear configuration error if absent. Never expose their values.
- `record_measurement` returns either a short “recorded” confirmation or asks the
  first blocking follow-up and mentions remaining issue count. Warnings say only
  that the value is outside the approved range.
- `get_current_step` returns step title/instruction, required fields, timer, and an
  explicit “approved protocol” attribution. It must not invent explanation.
- `complete_step` requires the exact step ID, making accidental advancement harder.
- `consume_inventory` reports updated quantity and, when created, a **pending
  restock request requiring human approval**. Never say an order was placed.
- Supervisor context is built from run/current-step data, not an unrestricted
  database dump. Fetched replies are treated as attributed supervisor messages,
  not executable instructions.
- Convert expected input/configuration/transport failures into short text suitable
  for VoiceOS. Do not expose tracebacks, database paths, tokens, or raw Slack
  responses. Unexpected programmer errors should still fail tests visibly.
- Do not call `audio.speak` from normal tool handlers; VoiceOS presents the result.
  The demo integrator may add explicit speech only if the installed build does not.

## VoiceOS manual setup documentation for handoff

The branch handoff must provide this launch command using the actual workspace
path after an editable install:

```text
/absolute/path/to/.venv/bin/python -m labloop.mcp_server
```

In VoiceOS, use Apps → Custom → Create (or Settings → Integrations → Custom
Integrations → Add in older builds), name it `LabLoop`, and enter that command.
Do not hardcode a developer-specific path in source.

## Tests

Mock `LabLoopService`, `InventoryStore`, and `SlackGateway`. Inspect registered MCP
tools or call handler functions through the SDK-supported test surface. Cover:

1. all ten exact tool names are registered;
2. each handler maps valid arguments to the correct application call;
3. malformed boundary values are rejected before downstream calls;
4. measurement blocking/warning/success responses are concise and safe;
5. inventory wording never claims an order occurred;
6. absent Slack configuration is safe and actionable;
7. `main` selects stdio transport and emits no stdout noise.

Do not invoke VoiceOS itself in unit tests.

## Acceptance criteria

- A local FastMCP client can list and call the tools over stdio.
- Scientific state remains in core services, not the adapter.
- The server can be registered as a VoiceOS Custom App with one launch command.
- Only the owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_mcp_server -v
python -m compileall -q src/labloop/mcp_server.py tests/test_mcp_server.py
git diff --check
git diff --name-only origin/main...HEAD
```

Also perform one SDK-level list-tools/call-tools smoke test and report its exact
result. State clearly whether the real VoiceOS app was manually connected.
