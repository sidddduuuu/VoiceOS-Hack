# Ticket 07 — macOS speech and optional “Hey Jarvis” bridge

## Outcome

Provide reliable native speech output and a minimal macOS helper that can trigger
VoiceOS after recognizing the exact wake phrase. VoiceOS remains responsible for
speech understanding and tool selection; this ticket must not build a second
assistant.

## Start here

Read the shared spec and frozen audio contract. Prefer native macOS capabilities.
The wake helper is optional for the demo if microphone permissions or VoiceOS
shortcut discovery are unreliable; `speak` is required.

## Owned files

- `src/labloop/audio.py`
- `tests/test_audio.py`
- `native/JarvisWake.swift`
- `native/README.md`

Do not edit any other file. Do not add Python/audio dependencies, vendor wake-word
models, raw-audio recording, or laboratory command interpretation.

## Python API

Implement exactly:

```python
speak(text: str) -> None
trigger_voiceos(keycode: int, modifiers: tuple[str, ...]) -> None
```

### `speak`

- Reject empty/whitespace text and text containing NUL.
- On non-macOS, raise `RuntimeError` before spawning anything.
- Invoke `/usr/bin/say` with `subprocess.run` argument arrays, never a shell, with
  a 30-second timeout and `check=True`.
- Translate missing executable, timeout, and non-zero exit into safe `RuntimeError`.

### `trigger_voiceos`

- Validate a non-negative integer keycode, excluding booleans.
- Allowed modifiers are only `command`, `control`, `option`, and `shift`; normalize
  case and reject duplicates/unknown values.
- Use `/usr/bin/osascript` with a fixed AppleScript program and values passed as
  arguments. Never concatenate untrusted text into executable AppleScript.
- Require macOS and translate subprocess failures as above.

## Swift wake helper

Implement one file using `Speech`, `AVFoundation`, and `ApplicationServices`:

- request microphone and speech-recognition permission explicitly;
- listen through Apple's speech recognizer;
- normalize recognized text and trigger only when the latest phrase ends with the
  exact words “hey jarvis”, case-insensitive;
- debounce triggers for three seconds;
- post the configured keyboard shortcut with `CGEvent`;
- read keycode/modifiers from command-line arguments with strict validation;
- print status/errors but never transcript contents;
- retain no audio or transcript and make no network calls directly.

Keep it as a foreground demo executable. No launch agent, installer, menu bar UI,
background daemon, configuration framework, or auto-start behavior.

`native/README.md` must document the one-line `swiftc` build command, permissions
required, example invocation, how to stop it, and the fallback of using the normal
VoiceOS shortcut manually.

## Tests

Python tests mock platform detection and `subprocess.run`. Cover valid argument
arrays, empty speech, non-macOS behavior, invalid keycodes/modifiers, timeout, and
process failures. Do not require macOS automation permissions in unit tests.

If `swiftc` is available, type-check/build the helper to a temporary path. Do not
commit a compiled binary.

## Acceptance criteria

- No `shell=True`, transcript logging, raw-audio persistence, or second NLP layer.
- The shortcut is configurable because physical/user VoiceOS setup varies.
- The demo still works via manual VoiceOS activation when the wake helper is off.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_audio -v
python -m compileall -q src/labloop/audio.py tests/test_audio.py
swiftc native/JarvisWake.swift -o /tmp/labloop-jarvis-wake
git diff --check
git diff --name-only origin/main...HEAD
```

If Swift tooling/permissions are unavailable, report that honestly and provide the
Python test evidence. Never claim the wake path was exercised without doing so.
