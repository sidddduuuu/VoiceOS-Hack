"""Native macOS speech and VoiceOS shortcut helpers."""

from __future__ import annotations

import subprocess
import sys


_VOICEOS_SCRIPT = """\
on run argv
    set requestedKeyCode to item 1 of argv as integer
    set requestedModifiers to {}
    tell application "System Events"
        if (count of argv) > 1 then
            repeat with argumentIndex from 2 to count of argv
                set modifierName to item argumentIndex of argv
                if modifierName is "command" then
                    set end of requestedModifiers to command down
                else if modifierName is "control" then
                    set end of requestedModifiers to control down
                else if modifierName is "option" then
                    set end of requestedModifiers to option down
                else if modifierName is "shift" then
                    set end of requestedModifiers to shift down
                end if
            end repeat
        end if
        key code requestedKeyCode using requestedModifiers
    end tell
end run
"""
_ALLOWED_MODIFIERS = {"command", "control", "option", "shift"}


def _run(command: list[str]) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("macOS is required")
    try:
        subprocess.run(command, check=True, timeout=30)
    except FileNotFoundError:
        raise RuntimeError("required macOS executable is unavailable") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("macOS command timed out") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("macOS command failed") from None


def speak(text: str) -> None:
    """Speak non-empty text with the native macOS speech synthesizer."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if "\0" in text:
        raise ValueError("text must not contain NUL")
    _run(["/usr/bin/say", text])


def trigger_voiceos(keycode: int, modifiers: tuple[str, ...]) -> None:
    """Post the configured VoiceOS keyboard shortcut through System Events."""
    if isinstance(keycode, bool) or not isinstance(keycode, int) or keycode < 0:
        raise ValueError("keycode must be a non-negative integer")

    normalized: list[str] = []
    for modifier in modifiers:
        if not isinstance(modifier, str) or modifier.lower() not in _ALLOWED_MODIFIERS:
            raise ValueError("unknown modifier")
        value = modifier.lower()
        if value in normalized:
            raise ValueError("duplicate modifier")
        normalized.append(value)

    _run(
        [
            "/usr/bin/osascript",
            "-e",
            _VOICEOS_SCRIPT,
            "--",
            str(keycode),
            *normalized,
        ]
    )
