# Ticket 13 — VoiceOS and LabLoop presence band

## Outcome

Create a prominent, honest voice/activity status band that makes the connection
between spoken work, VoiceOS tool calls, and the experiment record visible during
the demo.

## Read first

Read both phase-two reference documents and the component contract. The current
backend has no microphone telemetry; never represent derived connection state as a
live microphone signal.

## Owned files

- `web/sections/voice-presence.js`
- `web/sections/voice-presence.css`
- `web/previews/13-voice-presence.html`
- `tests/test_voice_presence.py`

Do not edit MCP, audio, dashboard, shared design, or other section files.

## Module contract

Export `createVoicePresenceSection(rootElement)` and return
`{render(viewModel), destroy()}`.

Render five states from `viewModel.voice`: idle, listening, processing, complete,
and error. Each state needs a visible text label, icon/shape change, and non-color
cue. The label provided by the integrator is authoritative; default copy must say
“LabLoop ready”, “Voice command active”, “Recording action”, “Action recorded”, or
“Voice connection needs attention” without claiming audio is stored.

## Visual and motion behavior

- Use one continuous horizontal band rather than a row of status cards.
- Include an original CSS/SVG waveform with 7–11 bars and a compact path showing
  VoiceOS → LabLoop → experiment record.
- Listening uses restrained amplitude; processing travels left-to-right; complete
  resolves once; error becomes still and explicit.
- Animate transform/opacity only. Never infer state from audio, access a microphone,
  retain transcript text, or add a fake command history.
- Provide polite `aria-live` status without repeatedly announcing the one-second
  dashboard refresh.

## Edge cases

Support missing voice data, long localized labels, error text, disconnected API,
and reduced motion. Missing telemetry renders “LabLoop connection state only”.
No state may show a red waveform without an accompanying error label.

## Tests

Verify the exact export/factory contract, all five state labels and non-color cues,
no microphone/Web Audio/fetch/timer APIs, no dynamic `innerHTML`, stable DOM updates,
polite live-region semantics, local preview assets, and reduced-motion hooks.

## Acceptance criteria

- Judges can see when speech is becoming a recorded action.
- Status wording remains honest about derived versus live microphone state.
- Motion is readable from several feet away but not distracting.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_voice_presence -v
python -m http.server 8093 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture all five states plus reduced-motion mode. Report copy/state mapping and
integration expectations.
