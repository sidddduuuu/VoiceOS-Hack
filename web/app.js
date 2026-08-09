"use strict";

const state = {
  runs: [],
  selectedRunId: null,
  detail: null,
  inventory: { items: [], pending_requests: [] },
  phase: "loading",
  error: null,
  syncing: false,
};

const element = (id) => document.getElementById(id);
const ui = {
  workspace: document.querySelector(".workspace"),
  connectionDot: element("connection-dot"),
  connectionLabel: element("connection-label"),
  lastSync: element("last-sync"),
  runSelect: element("run-select"),
  viewState: element("view-state"),
  protocolVersion: element("protocol-version"),
  protocolName: element("protocol-name"),
  operator: element("operator"),
  runStatus: element("run-status"),
  stepNumber: element("step-number"),
  stepDetail: element("step-detail"),
  samples: element("samples"),
  sampleCount: element("sample-count"),
  measurements: element("measurements"),
  deviations: element("deviations"),
  deviationCount: element("deviation-count"),
  messages: element("messages"),
  messageCount: element("message-count"),
  inventory: element("inventory"),
  requestCount: element("request-count"),
  timeline: element("timeline"),
  eventCount: element("event-count"),
};

function makeNode(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatTime(timestamp) {
  if (!timestamp) return "Time not recorded";
  const date = new Date(timestamp);
  return Number.isNaN(date.valueOf())
    ? String(timestamp)
    : new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(date);
}

function valueText(value, fallback = "Not recorded") {
  if (value === null || value === undefined || value === "") return fallback;
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function eventSource(event) {
  if (event.payload && event.payload.source) return valueText(event.payload.source);
  if (event.kind === "supervisor") return "Supervisor message";
  if (["checkpoint", "run"].includes(event.kind)) return "Protocol state";
  return "Recorded experiment data";
}

function eventSummary(event) {
  const payload = event.payload || {};
  if (event.kind === "measurement") {
    const reading = payload.value === null || payload.value === undefined ? "Incomplete reading" : `${payload.value} ${payload.unit || ""}`.trim();
    return `${payload.sample_id || "Run"}: ${reading}`;
  }
  if (Array.isArray(payload.issues)) {
    return payload.issues.map((issue) => valueText(issue.question || issue.field, "Validation issue")).join(" · ");
  }
  return valueText(
    payload.text || payload.question || payload.message || payload.note || payload.title || payload.step_title,
    `${valueText(event.kind, "Event")} recorded`,
  );
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

async function refresh() {
  if (state.syncing) return;
  state.syncing = true;
  try {
    const [runPayload, inventory] = await Promise.all([
      fetchJson("/api/runs"),
      fetchJson("/api/inventory"),
    ]);
    state.runs = Array.isArray(runPayload.runs) ? runPayload.runs : [];
    state.inventory = inventory;
    if (!state.runs.some((run) => run.id === state.selectedRunId)) {
      state.selectedRunId = state.runs[0]?.id || null;
    }
    state.detail = state.selectedRunId
      ? await fetchJson(`/api/runs/${encodeURIComponent(state.selectedRunId)}`)
      : null;
    state.phase = state.runs.length ? "ready" : "empty";
    state.error = null;
    ui.lastSync.textContent = `Synced ${formatTime(new Date().toISOString())}`;
  } catch (error) {
    state.phase = "error";
    state.error = error instanceof Error ? error.message : "Dashboard unavailable";
  } finally {
    state.syncing = false;
    render();
  }
}

async function selectRun(runId) {
  state.selectedRunId = runId;
  state.phase = "loading";
  renderConnection();
  try {
    state.detail = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
    state.phase = "ready";
    state.error = null;
  } catch (error) {
    state.phase = "error";
    state.error = error instanceof Error ? error.message : "Run unavailable";
  }
  render();
}

function renderConnection() {
  const connected = state.phase === "ready" || state.phase === "empty";
  ui.connectionDot.className = `connection-dot ${connected ? "is-live" : state.phase === "error" ? "is-error" : ""}`;
  ui.connectionLabel.textContent = connected ? "Live" : state.phase === "error" ? "Disconnected" : "Connecting";
  ui.workspace.setAttribute("aria-busy", String(state.phase === "loading"));
  ui.viewState.className = `view-state ${state.phase === "error" ? "is-error" : ""}`;
  ui.viewState.textContent = state.phase === "error"
    ? `Connection error: ${state.error}`
    : state.phase === "empty"
      ? "No experiment runs yet. This view will update automatically."
      : state.phase === "loading"
        ? "Loading the latest experiment state…"
        : "Live experiment data. No controls can modify the record.";
}

function renderRunSelector() {
  const options = state.runs.map((run) => {
    const option = makeNode("option", "", `${run.protocol_id} · ${run.operator}`);
    option.value = run.id;
    option.selected = run.id === state.selectedRunId;
    return option;
  });
  if (!options.length) options.push(makeNode("option", "", "No runs available"));
  ui.runSelect.replaceChildren(...options);
  ui.runSelect.disabled = !state.runs.length;
}

function currentStepDetail(events, run) {
  const matching = [...events].reverse().find((event) => {
    const payload = event.payload || {};
    return payload.step_index === run.current_step_index || payload.step_id === run.current_step_id;
  });
  const payload = matching?.payload || {};
  return valueText(payload.step_title || payload.title || payload.instruction, "Protocol step details are not recorded yet");
}

function renderHero(run, events) {
  ui.protocolVersion.textContent = `PROTOCOL ${run.protocol_version || "—"}`;
  ui.protocolName.textContent = valueText(run.protocol_name || run.protocol_id, "No protocol selected");
  ui.operator.textContent = `Operator ${valueText(run.operator, "—")}`;
  ui.runStatus.textContent = valueText(run.status, "unknown");
  ui.runStatus.className = `status-badge status-${valueText(run.status, "unknown")}`;
  ui.stepNumber.textContent = Number.isInteger(run.current_step_index) ? String(run.current_step_index + 1).padStart(2, "0") : "—";
  ui.stepDetail.textContent = currentStepDetail(events, run);
}

function renderEmptyHero() {
  ui.protocolVersion.textContent = "PROTOCOL —";
  ui.protocolName.textContent = "Waiting for a run";
  ui.operator.textContent = "Operator —";
  ui.runStatus.textContent = "Empty";
  ui.runStatus.className = "status-badge";
  ui.stepNumber.textContent = "—";
  ui.stepDetail.textContent = "Awaiting experiment data";
  ui.sampleCount.textContent = "0 tracked";
  ui.samples.replaceChildren(makeNode("span", "placeholder", "No samples recorded"));
}

function renderSamples(run) {
  const samples = Array.isArray(run.sample_ids) ? run.sample_ids : [];
  ui.sampleCount.textContent = `${samples.length} tracked`;
  ui.samples.replaceChildren(...(samples.length
    ? samples.map((sample) => makeNode("span", "sample-chip", valueText(sample)))
    : [makeNode("span", "placeholder", "No samples recorded")]
  ));
}

function renderMeasurements(events) {
  const measurements = events.filter((event) => event.kind === "measurement").slice(-5).reverse();
  ui.measurements.replaceChildren(...(measurements.length
    ? measurements.map((event) => {
        const item = makeNode("li", "measurement-row");
        const reading = makeNode("span", "measurement-value", eventSummary(event));
        const meta = makeNode("span", "measurement-meta", `${valueText(event.payload?.instrument, "Instrument —")} · ${formatTime(event.created_at)}`);
        item.append(reading, meta);
        return item;
      })
    : [makeNode("li", "placeholder", "No measurements recorded")]
  ));
}

function renderSignalList(target, events, emptyText) {
  target.replaceChildren(...(events.length
    ? events.slice(-4).reverse().map((event) => {
        const item = makeNode("li", "signal-item");
        item.append(
          makeNode("p", "", eventSummary(event)),
          makeNode("span", "signal-meta", `${eventSource(event)} · ${formatTime(event.created_at)}`),
        );
        return item;
      })
    : [makeNode("li", "placeholder", emptyText)]
  ));
}

function renderInventory() {
  const items = Array.isArray(state.inventory.items) ? state.inventory.items : [];
  const requests = Array.isArray(state.inventory.pending_requests) ? state.inventory.pending_requests : [];
  const requestItems = new Set(requests.map((request) => request.item_id));
  ui.requestCount.textContent = `${requests.length} pending restock${requests.length === 1 ? "" : "s"}`;
  ui.inventory.replaceChildren(...(items.length
    ? items.map((item) => {
        const warning = Number(item.quantity) <= Number(item.reorder_threshold);
        const row = makeNode("div", `inventory-row ${warning ? "is-low" : ""}`);
        const identity = makeNode("div", "inventory-identity");
        identity.append(
          makeNode("strong", "", valueText(item.name || item.id)),
          makeNode("span", "", warning ? "Below next-run threshold" : "Stock level sufficient"),
        );
        const quantity = makeNode("strong", "inventory-quantity", `${valueText(item.quantity, "—")} ${valueText(item.unit, "")}`.trim());
        const request = makeNode("span", `request-badge ${requestItems.has(item.id) ? "is-pending" : ""}`, requestItems.has(item.id) ? "Restock pending" : "No request");
        row.append(identity, quantity, request);
        return row;
      })
    : [makeNode("p", "placeholder", "No inventory items recorded")]
  ));
}

function renderTimeline(events) {
  const ordered = [...events].sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
  ui.eventCount.textContent = `${ordered.length} event${ordered.length === 1 ? "" : "s"}`;
  ui.timeline.replaceChildren(...(ordered.length
    ? ordered.map((event) => {
        const item = makeNode("li", "timeline-event");
        const marker = makeNode("span", `timeline-marker kind-${valueText(event.kind, "system")}`);
        marker.setAttribute("aria-hidden", "true");
        const content = makeNode("div", "timeline-content");
        const head = makeNode("div", "timeline-head");
        head.append(
          makeNode("span", "event-kind", valueText(event.kind, "event")),
          makeNode("span", "event-source", eventSource(event)),
          makeNode("time", "", formatTime(event.created_at)),
        );
        content.append(head, makeNode("p", "event-summary", eventSummary(event)));
        if (event.supersedes_event_id) {
          content.append(makeNode("span", "correction-badge", `Correction · supersedes ${event.supersedes_event_id}`));
        }
        item.append(marker, content);
        return item;
      })
    : [makeNode("li", "placeholder", "No events recorded")]
  ));
}

function render() {
  renderConnection();
  renderRunSelector();
  const run = state.detail?.run;
  const events = Array.isArray(state.detail?.events) ? state.detail.events : [];
  if (run) {
    renderHero(run, events);
    renderSamples(run);
  } else if (state.phase === "empty") {
    renderEmptyHero();
  }
  renderMeasurements(events);
  const deviations = events.filter((event) => event.kind === "deviation");
  const messages = events.filter((event) => event.kind === "supervisor");
  ui.deviationCount.textContent = `${deviations.length} flag${deviations.length === 1 ? "" : "s"}`;
  ui.messageCount.textContent = `${messages.length} message${messages.length === 1 ? "" : "s"}`;
  renderSignalList(ui.deviations, deviations, "No deviations recorded");
  renderSignalList(ui.messages, messages, "No supervisor messages");
  renderInventory();
  renderTimeline(events);
}

ui.runSelect.addEventListener("change", (event) => selectRun(event.target.value));
refresh();
setInterval(refresh, 1000);
