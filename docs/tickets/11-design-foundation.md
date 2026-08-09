# Ticket 11 — World Labs-inspired design foundation

## Outcome

Create the shared visual tokens and spatial page-shell primitives used by the new
LabLoop surface. This ticket establishes the visual language without touching the
existing dashboard entry files.

## Read first

Read `AGENTS.md`, `docs/full-build-spec.md`,
`docs/worldlabs-ui-reference.md`, and the current `web/styles.css`. The reference
is directional only; all LabLoop assets and code must be original.

## Owned files

- `web/design/tokens.css`
- `web/design/shell.css`
- `web/previews/11-design-foundation.html`
- `tests/test_design_foundation.py`

Do not edit any other file. Do not add fonts, images, JavaScript, dependencies, or
component-specific styles.

## Tokens

Define documented OKLCH custom properties for:

- near-white canvas, fog surface, graphite ink, muted ink, fine rule;
- dark console surface and its readable text/muted text;
- dusty lilac identity accent, restrained blue live accent, warm copper physical
  accent, success, warning, blocking, and keyboard focus;
- serif display stack, sans UI stack, and tabular monospace/data stack;
- a compact fixed type scale, spacing scale, modest radii, semantic z-index scale,
  and ease-out-quart/expo timing tokens.

Verify body text and all semantic foreground/background pairs meet WCAG AA. The
canvas must be true/cool near-white, not cream. Accent colors are state/identity,
not decoration.

## Shell primitives

Implement only reusable layout classes prefixed `.ll-shell-`:

- slim masthead with original LabLoop wordmark treatment, connection slot, and
  optional anchor navigation;
- generous editorial intro region;
- asymmetric apparatus/content split;
- full-width dark live-console region;
- bounded content measure and divider rhythm;
- accessible skip link and visible focus treatment.

Use Grid only for true two-dimensional shell layout and Flexbox otherwise. Avoid
cards, wide shadows, glass, over-rounding, tiny uppercase eyebrows, and decorative
grids. Global selectors are limited to reset, `html`, `body`, typography, focus,
and reduced box sizing within `tokens.css`.

## Preview

The standalone preview loads only the two owned stylesheets and demonstrates type,
palette, focus, masthead, editorial split, dark console, status tags, and long-copy
wrapping. It uses clearly synthetic text and has no JavaScript.

## Tests

Use `unittest` to inspect owned assets. Cover:

1. required tokens exist and use OKLCH colors;
2. display/UI/data stacks are distinct and have local fallbacks;
3. semantic z-index and motion tokens exist;
4. banned gradient-text/glass/grid/oversized-radius patterns are absent;
5. preview references only local owned CSS and contains semantic landmarks;
6. token values pass a small contrast calculation for required color pairs.

## Acceptance criteria

- The preview visibly evokes the reference through composition/type, not copying.
- No network request is needed to render it.
- No component or existing entry file changes.
- Only the four owned files change.

## Verify and hand off

```sh
PYTHONPATH=src python -m unittest tests.test_design_foundation -v
python -m http.server 8091 -d web
git diff --check
git diff --name-only origin/main...HEAD
```

Capture the preview at 1440×900 and 390×844. Report contrast results, screenshot
paths, test results, and any token decision ticket 20 must preserve.
