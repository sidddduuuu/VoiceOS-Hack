# LabLoop full-build UI specification

Phase two turns the functional read-only dashboard into a polished, animated demo
surface inspired by `docs/worldlabs-ui-reference.md`. Existing APIs, safety rules,
MCP tools, and data contracts remain unchanged.

## Product outcome

Within two seconds, a researcher or judge should understand:

1. which approved protocol is running;
2. which step and samples are active;
3. whether VoiceOS/LabLoop is listening, processing, or waiting;
4. whether a measurement, deviation, supervisor reply, or inventory issue needs
   attention;
5. that every action is preserved in an immutable record.

The page is primarily observational. Preserve the native run selector, but do not
build the interactive 3D behavior, editors, drag controls, command forms, modals,
or write APIs present in richer products.

## Technology boundary

- Keep Python's standard-library dashboard and vanilla HTML/CSS/JavaScript.
- Add no framework, bundler, animation library, WebGL renderer, font package, or
  network-hosted asset.
- `src/labloop/dashboard.py` remains bound to `127.0.0.1` and read-only.
- Existing API payloads are the only UI data source.
- Ticket 20 is the only phase-two ticket allowed to edit `web/index.html`,
  `web/app.js`, `web/styles.css`, `src/labloop/dashboard.py`, or
  `tests/test_dashboard.py`.

## Component contract for tickets 12–18

Each `web/sections/<name>.js` is a native ES module and exports one named factory:

```javascript
const component = createExampleSection(rootElement);
component.render(viewModel);
component.destroy();
```

The exact factory name is defined in its ticket. Requirements shared by every
factory:

- validate that `rootElement` is an `Element` and fail clearly otherwise;
- create its static DOM once; subsequent renders update existing nodes;
- return only `render(viewModel)` and `destroy()`;
- treat the view model as immutable; never fetch, poll, persist, or mutate it;
- never use `innerHTML` for dynamic content; use `textContent` and DOM methods;
- tolerate missing/empty fields and render an instructive empty state;
- apply animation state through `data-*` attributes/classes, not inline styles;
- remove any listener/observer it creates in `destroy()`.

Ticket 20 passes this frozen view model:

```text
{
  phase: "loading" | "ready" | "empty" | "error",
  error: string | null,
  runs: ExperimentRun JSON[],
  selectedRunId: string | null,
  detail: {run: ExperimentRun JSON, events: AuditEvent JSON[]} | null,
  inventory: {items: InventoryItem JSON[], pending_requests: PurchaseRequest JSON[]},
  lastSync: ISO timestamp | null,
  voice: {state: "idle" | "listening" | "processing" | "complete" | "error",
          label: string}
}
```

The current backend does not expose VoiceOS runtime telemetry. Until a future API
exists, ticket 20 derives `voice.state` from connection/tool activity and labels it
honestly as LabLoop connection activity; it must not pretend microphone state is live.

## CSS contract

- Ticket 11 owns shared tokens and shell primitives under `web/design/`.
- Component CSS uses only those tokens with a literal fallback, so isolated preview
  pages remain legible before ticket 11 merges.
- Section selectors start with a unique `.ll-<section>` prefix.
- JavaScript hooks use `data-role`; CSS classes are not queried from JavaScript.
- Breakpoints and reduced-motion overrides belong to ticket 19, except a component
  may include a minimal intrinsic layout using `auto-fit`, flex-wrap, and container
  size-independent styles.
- No component changes global `html`, `body`, `*`, link, button, or focus styles.

## Integration order

Tickets 11–19 can be implemented in parallel from this foundation because their
owned paths do not overlap. Merge them in numeric order. Create ticket 20 only
after 11–19 are on `main`; it integrates and visually verifies the whole surface.

## Quality gates

- WCAG 2.1 AA contrast; visible keyboard focus; semantic regions/headings/lists.
- 320px–1440px without horizontal overflow or clipped content.
- `prefers-reduced-motion` verified.
- No copied World Labs asset, logo, text, or source.
- Dynamic values are XSS-safe.
- Existing 82 tests stay green; each ticket adds one focused test.
- Final screenshots are checked at 1440×900, 1024×768, and 390×844.
