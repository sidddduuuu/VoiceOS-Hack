# LabLoop MVP specification

## Product promise

LabLoop is a stateful research partner for hands-busy experiments. A researcher
uses VoiceOS to begin an approved protocol, log observations and measurements,
ask what comes next, contact a supervisor, and record material usage. LabLoop
asks for missing metadata, flags deviations, and produces a timestamped record.

## Demo journey

1. The researcher activates VoiceOS and says they are starting the demo DNA
   extraction run.
2. LabLoop confirms the protocol version, operator, kit lot, and six sample IDs.
3. The researcher logs a normal observation.
4. The researcher logs a measurement without a unit; LabLoop asks for it.
5. A completed measurement is outside the protocol's expected range; LabLoop
   flags it without diagnosing the cause.
6. The researcher sends a contextual question to a supervisor in Slack.
7. A supervisor reply is fetched, stored, and read aloud on macOS.
8. Material usage drops inventory below the next-run requirement; LabLoop creates
   a pending restock request, not an order.
9. The dashboard shows the current step, samples, measurements, deviations,
   messages, inventory, and immutable timeline.
10. The run is completed and summarized without modifying historical entries.

## Scientific integrity rules

- Use only the loaded, versioned protocol. Never invent or silently change steps.
- State whether information comes from the protocol, recorded experiment data, or
  a supervisor message.
- Missing sample, unit, instrument, or required condition produces a follow-up.
- Out-of-range values produce a deviation flag, not a scientific diagnosis.
- Store corrections as new events with `supersedes_event_id`.
- Preserve tool arguments as the MVP's raw record. Formal ELN compliance and raw
  audio retention are explicitly outside the hackathon scope.
- Purchases remain pending until a human approves them outside the MVP.

## Architecture

```text
macOS wake bridge -> VoiceOS -> LabLoop MCP server
                                  |
                                  +-> protocol/session service
                                  +-> SQLite event + inventory stores
                                  +-> Slack gateway
                                  +-> native speech output
                                  +-> read-only dashboard
```

The MCP process and dashboard process share one SQLite database. SQLite is the
only shared runtime resource. Each Conductor workspace must use a database path
inside that workspace to avoid cross-workspace interference.

## Configuration

- `LABLOOP_DB_PATH`: SQLite file; defaults to `./labloop.db`.
- `LABLOOP_PROTOCOL_DIR`: protocol JSON directory; defaults to `./protocols`.
- `SLACK_BOT_TOKEN`: optional; Slack tools report a clear configuration error if absent.
- `SLACK_CHANNEL_ID`: optional default supervisor channel.
- `LABLOOP_VOICEOS_KEYCODE`: macOS key code used by the wake bridge.
- `LABLOOP_VOICEOS_MODIFIERS`: comma-separated modifiers for the wake bridge.

Secrets never appear in repository files or logs.

## MVP non-goals

- Autonomous protocol design or modification
- Scientific diagnosis or experimental conclusions
- Instrument control
- Raw-audio storage
- Regulatory or GLP/GMP compliance claims
- Autonomous purchasing
- Mobile or Windows wake-word support
- General-purpose ELN replacement
