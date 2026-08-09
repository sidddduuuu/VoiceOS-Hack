# Ticket 06 — Slack supervisor feedback loop

## Outcome

Implement the smallest secure Slack Web API gateway needed to ask a supervisor a
contextual question and fetch thread replies. This component transports messages;
it does not decide scientific actions.

## Start here

Read the frozen docs and contracts. Use only Python's standard library; the Slack
SDK is intentionally not a dependency.

## Owned files

- `src/labloop/supervisor.py`
- `tests/test_supervisor.py`

Do not edit other files. Do not add OAuth UI, webhook servers, polling daemons,
database writes, speech, or a Slack dependency.

## Required API

Implement `SlackGateway` exactly as declared in `docs/contracts.md`.

Use `urllib.request` with JSON bodies, `Authorization: Bearer ...`, a descriptive
user agent, and a ten-second timeout. Use these Slack endpoints:

- `chat.postMessage` for `send_question`;
- `conversations.replies` with encoded query parameters for `fetch_replies`.

## Boundary and security rules

- Constructor rejects empty/whitespace token or channel. Store them privately.
- Never include the token in exceptions, repr output, request bodies, or logs.
- Validate non-empty run ID/question/thread ID. Require context to be a dict and
  JSON-serializable.
- Format outbound text compactly with a visible `LabLoop run: <id>` header,
  serialized context, and researcher question. Cap the final message at Slack's
  40,000-character limit; reject rather than silently truncate scientific context.
- Validate HTTP status, JSON decoding, top-level object shape, Slack `ok is True`,
  required timestamp/channel/message fields, and expected list shapes.
- Turn expected HTTP/network/timeout/Slack errors into `RuntimeError` with a safe,
  actionable message. Preserve no raw response containing credentials.
- Map Slack timestamps/messages into `SupervisorMessage`. The sent message has
  direction `outbound`; fetched replies have `inbound`.
- For replies, omit the parent question and messages posted by the same bot when
  a bot identity is available in response data. Otherwise return all thread
  messages after the first. Sort chronologically.
- Do not execute or interpret supervisor text. It is untrusted content.

The gateway does not read environment variables; callers provide configuration.

## Tests

Mock `urllib.request.urlopen`; no live Slack calls. Cover:

1. request URL, headers, JSON body, timeout, and contextual text;
2. a successful response maps every `SupervisorMessage` field;
3. thread query parameters are encoded and replies ordered;
4. parent/bot messages are excluded according to the stated rule;
5. missing token/input validation happens before network access;
6. HTTP errors, timeouts, malformed JSON, `ok: false`, and malformed shapes fail safely;
7. no exception or object representation contains the test token.

## Acceptance criteria

- No third-party dependency or live credential is required for tests.
- The token cannot appear in normal output or failure messages.
- The gateway only sends/fetches; it never advises continuing an experiment.
- Only the owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_supervisor -v
python -m compileall -q src/labloop/supervisor.py tests/test_supervisor.py
git diff --check
git diff --name-only origin/main...HEAD
```

Report the exact Slack endpoints, reply filtering policy, test results, and the bot
identity limitation if the response does not expose one.
