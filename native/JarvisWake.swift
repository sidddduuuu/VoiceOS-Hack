import ApplicationServices
import AVFoundation
import Foundation
import Speech

private let allowedModifiers: [String: CGEventFlags] = [
    "command": .maskCommand,
    "control": .maskControl,
    "option": .maskAlternate,
    "shift": .maskShift,
]

private struct Shortcut {
    let keycode: CGKeyCode
    let flags: CGEventFlags
}

private func parseShortcut(_ arguments: [String]) throws -> Shortcut {
    guard let rawKeycode = arguments.first,
          !rawKeycode.isEmpty,
          rawKeycode.allSatisfy(\.isNumber),
          let keycode = UInt16(rawKeycode) else {
        throw WakeError.usage
    }

    var names = Set<String>()
    var flags = CGEventFlags()
    for rawModifier in arguments.dropFirst() {
        let name = rawModifier.lowercased()
        guard let flag = allowedModifiers[name], names.insert(name).inserted else {
            throw WakeError.usage
        }
        flags.insert(flag)
    }
    return Shortcut(keycode: keycode, flags: flags)
}

private enum WakeError: Error {
    case usage
    case unavailable(String)
}

private final class WakeListener {
    private let shortcut: Shortcut
    private let audioEngine = AVAudioEngine()
    private let recognizer = SFSpeechRecognizer()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var lastTrigger = Date.distantPast

    init(shortcut: Shortcut) {
        self.shortcut = shortcut
    }

    func start() throws {
        guard let recognizer, recognizer.isAvailable else {
            throw WakeError.unavailable("Speech recognition is unavailable.")
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        self.request = request

        let input = audioEngine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, when in
            request.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            if let result {
                self?.consider(result.bestTranscription.formattedString)
            }
            if error != nil {
                print("Speech recognition stopped with an error.")
            }
        }
        print("Listening for the wake phrase. Press Control-C to stop.")
    }

    private func consider(_ transcript: String) {
        let words = transcript.lowercased().split { !$0.isLetter && !$0.isNumber }
        guard words.suffix(2).elementsEqual(["hey", "jarvis"]) else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self, Date().timeIntervalSince(lastTrigger) >= 3 else { return }
            lastTrigger = Date()
            postShortcut()
        }
    }

    private func postShortcut() {
        guard let down = CGEvent(
            keyboardEventSource: nil,
            virtualKey: shortcut.keycode,
            keyDown: true
        ), let up = CGEvent(
            keyboardEventSource: nil,
            virtualKey: shortcut.keycode,
            keyDown: false
        ) else {
            print("Could not create keyboard events.")
            return
        }
        down.flags = shortcut.flags
        up.flags = shortcut.flags
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
        print("Wake phrase recognized; VoiceOS shortcut triggered.")
    }
}

private func requestPermissions(then start: @escaping () -> Void) {
    SFSpeechRecognizer.requestAuthorization { status in
        guard status == .authorized else {
            print("Speech recognition permission was not granted.")
            exit(EXIT_FAILURE)
        }
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            guard granted else {
                print("Microphone permission was not granted.")
                exit(EXIT_FAILURE)
            }
            DispatchQueue.main.async(execute: start)
        }
    }
}

do {
    let shortcut = try parseShortcut(Array(CommandLine.arguments.dropFirst()))
    let listener = WakeListener(shortcut: shortcut)
    requestPermissions {
        do {
            try listener.start()
        } catch WakeError.unavailable(let message) {
            print(message)
            exit(EXIT_FAILURE)
        } catch {
            print("Could not start microphone capture.")
            exit(EXIT_FAILURE)
        }
    }
    RunLoop.main.run()
} catch {
    print("Usage: JarvisWake <keycode> [command|control|option|shift ...]")
    exit(EXIT_FAILURE)
}
