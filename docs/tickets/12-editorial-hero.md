# Ticket 12 — Editorial hero and animated lab apparatus

## Outcome

Build the first-view narrative and an original isometric laboratory apparatus that
turns current protocol state into an immediately understandable visual system.
No 3D interaction or copied World Labs artwork is allowed.

## Read first

Read the phase-two spec/reference and ticket 11's token contract. Work against
fallback token values because ticket 11 may merge later.

## Owned files

- `web/sections/hero.js`
- `web/sections/hero.css`
- `web/assets/lab-apparatus.svg`
- `web/previews/12-editorial-hero.html`
- `tests/test_editorial_hero.py`

Do not edit existing dashboard files, shared styles, or other sections.

## Module contract

Export `createHeroSection(rootElement)`. Return `{render(viewModel), destroy()}`
and follow every rule in `docs/full-build-spec.md`.

The static structure contains a display title, one-sentence product thesis,
protocol/run attribution, a concise state line, and the apparatus. Dynamic copy
must come from the selected run without using `innerHTML`.

## Apparatus asset

Create one accessible, original inline-loadable SVG showing:

- sample vessels entering a protocol track;
- a central measurement chamber;
- a supervisor relay and inventory reservoir;
- 6–8 protocol nodes connected in one coherent isometric system.

Use grouped semantic IDs/classes and `currentColor`/CSS custom properties so state
can be styled externally. Keep the SVG under 35 KB, with no embedded raster, font,
script, filter noise, copied globe, logo, or World Labs geometry. Decorative detail
is `aria-hidden`; the surrounding figure provides the useful accessible name.

## State and motion hooks

`render` maps loading/ready/completed/error and current step index to `data-state`
and `data-step` attributes. CSS may use transform/opacity to pulse the active node,
move a sample token, and rotate a chamber ring. Content is fully visible when
animations do not run. Ticket 19 supplies final global timing/reduced-motion rules.

## Visual behavior

- Wide: title and thesis occupy the left half; apparatus overlaps the right visual
  field without obscuring text.
- Small: title precedes apparatus; no SVG label becomes unreadably tiny.
- Serif display copy never exceeds 5.5rem or `-0.04em` tracking.
- The hero is mostly bright canvas; use lilac/copper/blue as restrained state cues.

## Tests

Verify factory/export names, no fetch/timer/innerHTML, required empty/error states,
SVG size and prohibited tags, unique IDs, accessible figure labeling, data-state
hooks, local-only preview assets, and reduced-motion-safe CSS defaults.

## Acceptance criteria

- The hero reads as LabLoop within two seconds and does not resemble a generic SaaS
  card grid.
- Apparatus movement communicates current protocol activity.
- It works without pointer interaction and without JavaScript animation libraries.
- Only owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_editorial_hero -v
python -m http.server 8092 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture ready, empty, and error previews at desktop/mobile widths and report exact
assets, tests, and state assumptions.
