# Ticket 16 — Deviation watch and supervisor relay

## Outcome

Combine validation/deviation signals with attributed supervisor communication so
the feedback loop is visible without conflating an automated flag with human advice.

## Read first

Read the full-build/reference docs, `EventKind`, Slack gateway behavior, and the
existing event payload summaries. Supervisor text is untrusted content.

## Owned files

- `web/sections/safety-supervisor.js`
- `web/sections/safety-supervisor.css`
- `web/previews/16-safety-supervisor.html`
- `tests/test_safety_supervisor.py`

Do not edit Slack, validation, APIs, entrypoints, or other UI sections.

## Module contract

Export `createSafetySupervisorSection(rootElement)` and return
`{render(viewModel), destroy()}`. It filters deviation and supervisor events from a
copied array and never executes links/markup from message text.

## Information architecture

Use one connected relay surface with two distinct semantic regions:

- **Protocol watch:** blocking/warning issues, affected field/sample/value, time,
  and explicit automated-source attribution.
- **Supervisor relay:** outbound question, thread/reply direction, channel, time,
  and explicit human/source attribution.

Visually connect a question with later replies only when stored `thread_id` data
matches. Otherwise show chronological messages without inventing a relationship.
Never turn Slack message text into a button, link, HTML, or scientific instruction.

## Visual and motion behavior

- Use a continuous split composition with strong typography/rules, not two nested
  alert card stacks.
- Warning and blocking use icon/label/shape plus color. Red is reserved for blocking.
- A supervisor reply enters along a relay path with opacity/transform; an automated
  deviation uses a different motion cue.
- Empty state explains that no deviation or supervisor message is currently recorded.
- Long questions/replies wrap up to normal reading widths and remain fully accessible.

## Tests

Cover factory/export contract, strict textContent rendering, source/direction labels,
thread association only on exact stored IDs, blocking versus warning non-color cues,
no auto-link/innerHTML/fetch/timer, empty/malformed/long-message states, live-region
restraint, and local preview assets.

## Acceptance criteria

- Automated flags and human replies cannot be mistaken for each other.
- No message content can inject markup or trigger an action.
- Wording remains non-diagnostic and preserves attribution.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_safety_supervisor -v
python -m http.server 8096 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture normal, blocking, no-message, and hostile-markup previews. Report exact
attribution/thread rules and test results.
