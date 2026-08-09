# Ticket 20 — Full UI integration, browser QA, and demo handoff

## Outcome

Replace the original dashboard composition with the complete World Labs-inspired
LabLoop surface, wire every phase-two component to real API data, and prove the
result works end to end at demo resolutions.

This ticket starts only after tickets 11–19 are merged into `main`.

## Read first

Read `AGENTS.md`, both phase-two shared docs, tickets 11–19 and their handoffs,
existing dashboard/server/tests, and all merged section/design files. Run the full
test suite before editing to establish a baseline.

## Owned files

- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `src/labloop/dashboard.py`
- `tests/test_dashboard.py`
- `tests/test_full_ui.py`

Do not edit business logic, contracts, MCP tools, phase-two component files, their
tests, demo seed data, or protocol data. If a component violates its frozen
contract, report the exact mismatch for a targeted fix rather than copying or
rewriting the component here.

## Integration architecture

### HTML

- Use semantic masthead/main/section/footer landmarks and one logical heading tree.
- Provide a skip link, original LabLoop wordmark, connection status, optional
  in-page anchors, and one root per component.
- Load `app.js` as a native ES module and local styles only.
- No copied reference copy/assets, inline event handlers, inline scripts, external
  fonts, hidden SEO text, forms, dialogs, drag surfaces, or fake controls.

### CSS

`styles.css` becomes a short ordered import manifest:

1. tokens and shell;
2. section styles 12–18;
3. motion and responsive layers last.

Add only integration glue that cannot belong to an individual component. Do not
duplicate component rules or create a second token palette.

### JavaScript

- Import all seven section factories and the motion controller.
- Preserve the existing one-second API refresh, run selection, error handling, and
  no-overlapping-refresh guard.
- Maintain one immutable state object and derive a new view model for renders.
- Mount each component once, call `render` after state changes, and call `destroy`
  during `pagehide`.
- Listen only for `labloop:run-selected`; validate its run ID against loaded runs
  before fetching.
- Derive `voice.state` honestly: loading/active request → processing, successful
  fresh response → complete briefly only through an event-driven CSS state,
  disconnected → error, otherwise idle. Label it “LabLoop connection activity”
  unless actual VoiceOS telemetry is added in a future contract.
- Preserve selected run between refreshes without local/session storage.
- Do not announce every poll to assistive technology, replay animations for old
  events, mutate API payloads, or use dynamic `innerHTML`.

### Python static serving

Extend the explicit static-route map to serve every merged CSS, JS, SVG, and preview
dependency required by the final page with correct content types. Keep path traversal
impossible, CSP/security headers intact, bind address unchanged, and all APIs
read-only. Production page routes must not expose arbitrary repository files.

## Visual acceptance

- 1440×900: editorial hero/apparatus occupies the first view; dark operational
  stage begins without hiding essential live status.
- 1024×768: composition stacks deliberately with no tiny apparatus/data text.
- 390×844 and 320px: one column, no horizontal overflow, 44px run selector, full
  long IDs/messages, and visible connection state.
- Bright lab readability: body text ≥4.5:1, large text/state graphics ≥3:1.
- Motion conveys protocol/voice/data state and fully respects reduced motion.
- No default-template card grid, gradient text, glass stacks, wide ghost shadows,
  oversized radii, copied World Labs artwork, or decorative grid background.

## Automated tests

Update dashboard tests for all explicit static assets and retain every existing
security/read-only assertion. `test_full_ui.py` must verify:

1. all expected components/styles/modules are loaded exactly once;
2. factories are mounted/rendered/destroyed by the orchestrator;
3. API refresh/run selection/error behavior remains present;
4. CSP permits required local assets but no external/script-inline source;
5. no missing local import/link path;
6. no dynamic `innerHTML`, external URL, write endpoint, or microphone claim;
7. semantic landmarks/headings, skip link, labels, focus, and reduced-motion rules;
8. the original dashboard data categories all remain represented;
9. phase-two ownership files are unchanged from their merged commits.

Run all repository tests, not only the two owned test files.

## Manual end-to-end verification

1. Create a fresh virtual environment and install editable package.
2. Seed a disposable synthetic database with `demo/seed.py`.
3. Start the dashboard on `127.0.0.1` using a free port.
4. Confirm health/runs/inventory APIs and every static asset return 200.
5. Inspect loading, ready, empty, error, completed, correction, deviation,
   supervisor, pending-restock, long-content, and 100-event states.
6. Capture 1440×900, 1024×768, 390×844, and reduced-motion screenshots.
7. Use keyboard-only navigation and 200% zoom; confirm no focus/overflow failures.
8. Start the MCP server and confirm the UI updates after one synthetic tool action.
9. If VoiceOS/Slack credentials are available, label those checks live; otherwise
   use the documented fallback and state clearly that it was simulated.

Do not claim browser, VoiceOS, wake-word, or Slack verification unless actually run.

## Acceptance criteria

- The final page uses real LabLoop API data and every ticket 11–19 artifact.
- Existing scientific/security behavior remains intact.
- All automated tests pass and required screenshots are visually inspected.
- The complete two-to-three-minute demo can be rehearsed from `demo/demo-script.md`.
- Only the six owned files change.

## Verify and hand off

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests demo
git diff --check
git diff --name-only origin/main...HEAD
```

Handoff must include commit hash, changed files, exact test counts/results, server
commands, screenshot paths, viewport/reduced-motion/keyboard/zoom results, live vs
simulated integrations, and any remaining blocker. Do not merge to `main`; central
review performs the merge.
