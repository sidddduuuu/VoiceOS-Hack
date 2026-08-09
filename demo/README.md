# LabLoop DNA demo rehearsal kit

Everything seeded here is synthetic. The protocol is a product demonstration,
not laboratory guidance; researchers must follow their institution's approved
protocol.

## Install from a fresh checkout

Run these commands from the workspace root with Python 3.11 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
mkdir -p .context
```

## Seed and launch

Create the local demo database once. A repeat run refuses to overwrite it unless
the explicit `--reset` flag is present.

```sh
python demo/seed.py --db "$PWD/.context/labloop-demo.db"
# Deliberate replacement of this exact database and its -wal/-shm files:
python demo/seed.py --db "$PWD/.context/labloop-demo.db" --reset
```

Start the read-only dashboard in terminal 1:

```sh
LABLOOP_DB_PATH="$PWD/.context/labloop-demo.db" \
  LABLOOP_DASHBOARD_PORT=8765 \
  .venv/bin/python -m labloop.dashboard
```

Open `http://127.0.0.1:8765`, then configure VoiceOS to launch the MCP server.
Print the exact command to paste so the saved command contains no shell variable:

```sh
printf '%s -m labloop.mcp_server\n' "$PWD/.venv/bin/python"
```

In VoiceOS, go to **Apps → Custom → Create**, name the app `LabLoop`, and paste
that printed absolute command. Older VoiceOS builds use **Settings → Integrations
→ Custom Integrations → Add**. Set these variables in the Custom App environment:

```text
LABLOOP_DB_PATH=/absolute/path/to/workspace/.context/labloop-demo.db
LABLOOP_PROTOCOL_DIR=/absolute/path/to/workspace/protocols
SLACK_BOT_TOKEN=replace-with-bot-token
SLACK_CHANNEL_ID=replace-with-supervisor-channel-id
```

The first two variables are required for this rehearsal. Slack variables are
optional and must use real values only in the local VoiceOS configuration, never
in repository files. If launching the MCP server directly for a stdio smoke test:

```sh
LABLOOP_DB_PATH="$PWD/.context/labloop-demo.db" \
  LABLOOP_PROTOCOL_DIR="$PWD/protocols" \
  .venv/bin/python -m labloop.mcp_server
```

For live Slack, the bot needs `chat:write` and `channels:history` for a public
supervisor channel, or `groups:history` instead for a private channel. Invite the
bot to that single rehearsal channel. No Slack permission is needed for the
explicitly simulated fallback.

## Optional wake helper

Use the helper only on macOS after granting Microphone, Speech Recognition, and
Accessibility permissions. Build and run it with the configured VoiceOS shortcut:

```sh
swiftc native/JarvisWake.swift -o .context/labloop-jarvis-wake
.context/labloop-jarvis-wake 49 command shift
```

Stop it with Control-C. Key code `49` and `command,shift` are placeholders; use
the values for the shortcut configured in VoiceOS. The equivalent optional
environment placeholders are:

```text
LABLOOP_VOICEOS_KEYCODE=replace-with-nonnegative-keycode
LABLOOP_VOICEOS_MODIFIERS=replace-with-comma-separated-modifiers
```

## Rehearsal fallbacks

- **LIVE SLACK:** ask and fetch the real reply only when the local bot/channel are
  configured. Attribute the reply to Slack.
- **SIMULATED FALLBACK:** if Slack fails, show the seeded synthetic supervisor
  record and say aloud that it is simulated; never call it live.
- If the wake word fails, use the normal VoiceOS shortcut and continue the same
  script.
- If spoken output fails, read the visible VoiceOS response aloud and keep the
  dashboard on screen. Do not imply speech succeeded.

## Cleanup

Stop the MCP server, dashboard, and wake helper, then remove only files generated
by the commands above:

```sh
rm -f -- "$PWD/.context/labloop-demo.db"
rm -f -- "$PWD/.context/labloop-demo.db-wal"
rm -f -- "$PWD/.context/labloop-demo.db-shm"
rm -f -- "$PWD/.context/labloop-jarvis-wake"
```

The seed contains no Slack credentials and makes no network calls.
