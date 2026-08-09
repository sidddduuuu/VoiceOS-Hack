# JarvisWake demo helper

Build the foreground helper with Apple's native frameworks:

```sh
swiftc native/JarvisWake.swift -o /tmp/labloop-jarvis-wake
```

Grant the built executable Microphone and Speech Recognition access when macOS
prompts, then allow it under **System Settings → Privacy & Security →
Accessibility** so it can post the VoiceOS keyboard shortcut.

Pass the VoiceOS shortcut's numeric macOS key code followed by zero or more of
`command`, `control`, `option`, and `shift`. For example, key code 49 is the
space bar:

```sh
/tmp/labloop-jarvis-wake 49 command shift
```

Say “Hey Jarvis” to post that shortcut. The helper prints status only and does
not retain audio or transcripts. Stop it with **Control-C**. If permissions or
wake recognition are unreliable, leave the helper off and activate VoiceOS with
its normal shortcut manually; LabLoop speech output still works independently.
