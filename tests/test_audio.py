import subprocess
import unittest
from unittest.mock import patch

from labloop.audio import speak, trigger_voiceos


class AudioTests(unittest.TestCase):
    @patch("labloop.audio.subprocess.run")
    @patch("labloop.audio.sys.platform", "darwin")
    def test_speak_uses_say_argument_array(self, run):
        speak("Step complete")

        run.assert_called_once_with(
            ["/usr/bin/say", "Step complete"], check=True, timeout=30
        )

    @patch("labloop.audio.subprocess.run")
    @patch("labloop.audio.sys.platform", "darwin")
    def test_trigger_uses_fixed_script_and_normalized_arguments(self, run):
        trigger_voiceos(49, ("Command", "SHIFT"))

        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(arguments[3:], ["--", "49", "command", "shift"])
        self.assertNotIn("49", arguments[2])
        run.assert_called_once_with(arguments, check=True, timeout=30)

    def test_speak_rejects_empty_or_nul_text(self):
        for text in ("", "  \n", "hello\0world"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                speak(text)

    @patch("labloop.audio.subprocess.run")
    @patch("labloop.audio.sys.platform", "linux")
    def test_non_macos_rejected_without_spawning(self, run):
        with self.assertRaisesRegex(RuntimeError, "macOS"):
            speak("hello")
        with self.assertRaisesRegex(RuntimeError, "macOS"):
            trigger_voiceos(49, ("command",))
        run.assert_not_called()

    def test_trigger_rejects_invalid_keycodes_and_modifiers(self):
        for keycode in (-1, True, 1.5, "49"):
            with self.subTest(keycode=keycode), self.assertRaises(ValueError):
                trigger_voiceos(keycode, ())
        for modifiers in (("meta",), ("command", "COMMAND"), (1,)):
            with self.subTest(modifiers=modifiers), self.assertRaises(ValueError):
                trigger_voiceos(49, modifiers)

    @patch("labloop.audio.subprocess.run")
    @patch("labloop.audio.sys.platform", "darwin")
    def test_subprocess_failures_are_safe_runtime_errors(self, run):
        failures = (
            FileNotFoundError(),
            subprocess.TimeoutExpired(["/usr/bin/say"], 30),
            subprocess.CalledProcessError(1, ["/usr/bin/say"]),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                run.side_effect = failure
                with self.assertRaises(RuntimeError) as raised:
                    speak("hello")
                self.assertNotIn("hello", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
