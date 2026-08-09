# Ticket 19 — Motion, responsive composition, and accessibility layer

## Outcome

Create the shared animation and responsive system that makes the LabLoop surface
feel alive while remaining fast, legible, and fully usable with reduced motion,
keyboard navigation, zoom, and narrow screens.

## Read first

Read the phase-two spec/reference, ticket 11 shell/token contract, and expected
section class prefixes from tickets 12–18. This is a cross-component stylesheet but
must not alter component-specific color/content rules.

## Owned files

- `web/design/motion.css`
- `web/design/responsive.css`
- `web/motion.js`
- `web/previews/19-motion-responsive.html`
- `tests/test_motion_responsive.py`

Do not edit entrypoints, component modules/styles, Python, or shared tokens/shell.

## Motion module contract

Export `createMotionController(rootElement)` returning
`{markConnectionState(state), revealNewEvent(eventId), destroy()}`.

- Validate inputs and use classes/data attributes only.
- Remember seen event IDs in a bounded in-memory `Set` capped at 500; no storage.
- `revealNewEvent` animates only an element matching an exact safely escaped
  `data-event-id`; unknown IDs are no-ops.
- Use `matchMedia('(prefers-reduced-motion: reduce)')` and respond to changes.
- No requestAnimationFrame loop, scroll hijacking, custom cursor, audio, canvas,
  WebGL, third-party dependency, analytics, or global timer.

## Motion stylesheet

Define state-driven keyframes/utilities for protocol path, chamber ring, voice bars,
new measurement, relay reply, inventory threshold, connection state, and new event.
Animate transform/opacity only. Standard transitions are 150–250ms with ease-out;
ambient apparatus cycles are 8–16 seconds. No bounce, elastic, flashing, or infinite
motion outside apparatus/live indicators.

Under `prefers-reduced-motion: reduce`, disable ambient/keyframe motion, remove
smooth scrolling, and make essential state changes immediate. Content must never
start hidden awaiting JavaScript or IntersectionObserver.

## Responsive stylesheet

Implement structural breakpoints around content needs, covering at least:

- ≥1180px editorial split plus asymmetric live-console layout;
- 760–1179px stacked hero/apparatus and two-column operational sections;
- ≤759px one semantic column, compact masthead, full-width sections;
- ≤420px long protocol/sample/message data without overflow.

Preserve 44px controls, visible focus, readable 200% zoom, safe-area padding, and
no horizontal scrolling. Do not use fluid display type in product/data sections.

## Preview and tests

The preview composes representative static hooks from all expected section prefixes
without importing their modules. Tests verify module API, bounded Set, safe selector
construction, media-query listener cleanup, transform/opacity-only keyframes,
complete reduced-motion override, required breakpoints, no hidden-by-default content,
no prohibited APIs, focus/control/mobile rules, and local preview assets.

## Acceptance criteria

- Motion communicates real state and never delays access to information.
- Reduced-motion mode is calm and complete, not merely shorter.
- Layout works from 320px to 1440px and at 200% zoom.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_motion_responsive -v
python -m http.server 8099 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture 1440×900, 1024×768, 390×844, and reduced-motion previews. Report motion
durations, browser checks, and any component hook assumption ticket 20 must verify.
