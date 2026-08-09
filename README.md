# LabLoop

LabLoop is a stateful research copilot for hands-busy laboratory work. VoiceOS
turns spoken observations into MCP tool calls; LabLoop maintains protocol state,
asks for missing metadata, records an append-only audit trail, coordinates with a
supervisor, and prepares inventory restock requests.

The complete MVP includes the VoiceOS MCP adapter, append-only experiment record,
protocol validation, Slack supervision, inventory requests, macOS wake helper, and
an animated read-only dashboard. Read [the demo guide](demo/README.md) to connect
VoiceOS and rehearse the synthetic DNA extraction flow.

## Quality check

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Launch the dashboard

```bash
PYTHONPATH=src python demo/seed.py --db "$PWD/.context/labloop-demo.db"
LABLOOP_DB_PATH="$PWD/.context/labloop-demo.db" \
LABLOOP_PROTOCOL_DIR="$PWD/protocols" \
PYTHONPATH=src python -m labloop.dashboard
```

Open `http://127.0.0.1:8765`. The dashboard displays live state but cannot write
to the experiment record.
