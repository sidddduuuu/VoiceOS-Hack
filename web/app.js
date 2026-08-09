"use strict";

let state = Object.freeze({
  runs: [],
  selectedRunId: null,
  detail: null,
  inventory: Object.freeze({ items: [], pending_requests: [] }),
  phase: "loading",
  error: null,
  lastSync: null,
});
let syncing = false;
let initialEventsSeen = false;
const seenEventIds = new Set();

const element = (id) => document.getElementById(id);
const ui = {
  connectionDot: element("connection-dot"),
  connectionLabel: element("connection-label"),
  lastSync: element("last-sync"),
  heroProtocol: element("hero-protocol"),
  heroState: element("hero-state"),
  apparatus: element("lab-apparatus"),
  apparatusCaption: element("apparatus-caption"),
  voicePresence: element("voice-presence"),
  voiceLabel: element("voice-label"),
  viewState: element("view-state"),
  runSelect: element("run-select"),
  protocolVersion: element("protocol-version"),
  protocolName: element("protocol-name"),
  runStatus: element("run-status"),
  operator: element("operator"),
  startedAt: element("started-at"),
  stepNumber: element("step-number"),
  stepTitle: element("step-title"),
  stepDetail: element("step-detail"),
  samples: element("samples"),
  sampleCount: element("sample-count"),
  measurementCount: element("measurement-count"),
  latestSample: element("latest-sample"),
  latestValue: element("latest-value"),
  latestMeta: element("latest-meta"),
  rangePanel: element("range-panel"),
  rangeLabel: element("range-label"),
  rangeMarker: element("range-marker"),
  rangeNote: element("range-note"),
  measurements: element("measurements"),
  signalCount: element("signal-count"),
  deviations: element("deviations"),
  deviationCount: element("deviation-count"),
  messages: element("messages"),
  messageCount: element("message-count"),
  inventory: element("inventory"),
  requestCount: element("request-count"),
  timeline: element("timeline"),
  eventCount: element("event-count"),
};

function setState(patch) {
  state = Object.freeze({ ...state, ...patch });
}

function makeNode(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function valueText(value, fallback = "Not recorded") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return fallback;
    }
  }
  return String(value);
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatTime(timestamp) {
  if (!timestamp) return "Time not recorded";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return String(timestamp);
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatDate(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "Date not recorded";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

function eventSource(event) {
  const payload = event?.payload || {};
  if (payload.source) return valueText(payload.source);
  if (event?.kind === "supervisor") return "Attributed supervisor message";
  if (["checkpoint", "run"].includes(event?.kind)) return "Approved protocol state";
  if (event?.kind === "inventory") return "Inventory record";
  return "Recorded experiment data";
}

function issueSummary(issue) {
  if (!issue || typeof issue !== "object") return "Protocol validation issue";
  return valueText(issue.question || issue.field, "Protocol validation issue");
}

function eventSummary(event) {
  const payload = event?.payload || {};
  if (event?.kind === "measurement") {
    const reading = payload.value === null || payload.value === undefined
      ? "Incomplete reading"
      : `${payload.value} ${payload.unit || ""}`.trim();
    return `${valueText(payload.sample_id, "Run-level reading")}: ${reading}`;
  }
  if (Array.isArray(payload.issues)) {
    return payload.issues.map(issueSummary).join(" · ") || "Protocol validation issue";
  }
  if (event?.kind === "checkpoint" && payload.completed_step_id) {
    return `Completed approved protocol step ${payload.completed_step_id}`;
  }
  if (event?.kind === "run" && payload.status) {
    return `Experiment status changed to ${payload.status}`;
  }
  return valueText(
    payload.text || payload.question || payload.message || payload.note || payload.title || payload.step_title,
    `${valueText(event?.kind, "Event")} recorded`,
  );
}

function currentRun() {
  return state.detail?.run || null;
}

function currentEvents() {
  return safeArray(state.detail?.events);
}

function currentStep(run, events) {
  if (state.detail?.current_step) return state.detail.current_step;
  const matching = [...events].reverse().find((event) => {
    const payload = event?.payload || {};
    return payload.next_step_index === run?.current_step_index
      || payload.step_index === run?.current_step_index;
  });
  const payload = matching?.payload || {};
  return {
    id: payload.step_id || null,
    title: payload.step_title || payload.title || null,
    instruction: payload.instruction || null,
    expected_unit: null,
    expected_range: null,
  };
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  let body;
  try {
    body = await response.json();
  } catch (_error) {
    throw new Error(`Invalid response from LabLoop (${response.status})`);
  }
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

async function refresh() {
  if (syncing) return;
  syncing = true;
  if (state.phase !== "ready") setState({ phase: "loading" });
  renderConnection();
  try {
    const [runPayload, inventory] = await Promise.all([
      fetchJson("/api/runs"),
      fetchJson("/api/inventory"),
    ]);
    const runs = safeArray(runPayload.runs);
    const selectedRunId = runs.some((run) => run.id === state.selectedRunId)
      ? state.selectedRunId
      : runs[0]?.id || null;
    const detail = selectedRunId
      ? await fetchJson(`/api/runs/${encodeURIComponent(selectedRunId)}`)
      : null;
    setState({
      runs,
      selectedRunId,
      detail,
      inventory: inventory && typeof inventory === "object"
        ? Object.freeze({
            items: safeArray(inventory.items),
            pending_requests: safeArray(inventory.pending_requests),
          })
        : Object.freeze({ items: [], pending_requests: [] }),
      phase: runs.length ? "ready" : "empty",
      error: null,
      lastSync: new Date().toISOString(),
    });
  } catch (error) {
    setState({
      phase: "error",
      error: error instanceof Error ? error.message : "Dashboard unavailable",
    });
  } finally {
    syncing = false;
    render();
  }
}

async function selectRun(runId) {
  if (!state.runs.some((run) => run.id === runId)) return;
  setState({ selectedRunId: runId, phase: "loading", error: null });
  renderConnection();
  try {
    const detail = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
    setState({ detail, phase: "ready", lastSync: new Date().toISOString() });
  } catch (error) {
    setState({
      phase: "error",
      error: error instanceof Error ? error.message : "Run unavailable",
    });
  }
  render();
}

function renderConnection() {
  const connected = state.phase === "ready" || state.phase === "empty";
  document.body.dataset.phase = state.phase;
  ui.connectionDot.className = `connection-dot ${connected ? "is-live" : state.phase === "error" ? "is-error" : ""}`;
  ui.connectionLabel.textContent = connected ? "Live" : state.phase === "error" ? "Disconnected" : "Connecting";
  ui.lastSync.textContent = state.lastSync ? formatTime(state.lastSync) : "—";
  ui.lastSync.dateTime = state.lastSync || "";
  ui.viewState.className = `view-state ${state.phase === "error" ? "is-error" : ""}`;
  ui.viewState.textContent = state.phase === "error"
    ? `Connection error: ${state.error}`
    : state.phase === "empty"
      ? "No experiment runs yet. This view updates automatically."
      : state.phase === "loading"
        ? "Reading the latest experiment state…"
        : "Live experiment data. This surface cannot modify the record.";

  const voiceState = state.phase === "error" ? "error" : state.phase === "loading" ? "processing" : "complete";
  ui.voicePresence.dataset.voiceState = voiceState;
  ui.voiceLabel.textContent = voiceState === "error"
    ? "LabLoop connection activity — attention required"
    : voiceState === "processing"
      ? "LabLoop connection activity — recording state"
      : "LabLoop connection activity — record synchronized";
}

function renderRunSelector() {
  const options = state.runs.map((run) => {
    const option = makeNode("option", "", `${valueText(run.protocol_id, "Protocol")} · ${valueText(run.operator, "Operator")}`);
    option.value = run.id;
    option.selected = run.id === state.selectedRunId;
    return option;
  });
  if (!options.length) options.push(makeNode("option", "", "No runs available"));
  ui.runSelect.replaceChildren(...options);
  ui.runSelect.disabled = !state.runs.length;
}

function renderHero(run, step) {
  const protocol = state.detail?.protocol || {};
  const protocolName = valueText(protocol.name || run?.protocol_name || run?.protocol_id, "Waiting for a run");
  const status = valueText(run?.status, state.phase === "error" ? "error" : "waiting");
  const stepIndex = Number.isInteger(run?.current_step_index) ? run.current_step_index : 0;
  const apparatusStep = Math.max(0, Math.min(6, stepIndex));
  const completed = status === "completed";

  ui.heroProtocol.textContent = protocolName;
  ui.heroState.textContent = run
    ? completed ? "Protocol complete · completed" : `Step ${stepIndex + 1} · ${status}`
    : state.phase === "error" ? "Connection needs attention" : "Awaiting experiment state";
  ui.apparatus.dataset.step = String(apparatusStep);
  ui.apparatus.dataset.state = status === "running" ? "running" : status;
  ui.apparatusCaption.textContent = run
    ? completed
      ? `${protocolName} · all recorded steps complete`
      : `${protocolName} · step ${stepIndex + 1} · ${valueText(step?.title, "details not recorded")}`
    : "Approved protocol path awaiting live data";
}

function renderRunStage(run, events, step) {
  const protocol = state.detail?.protocol || {};
  if (!run) {
    ui.protocolVersion.textContent = "Approved protocol —";
    ui.protocolName.textContent = "Waiting for a research session";
    ui.runStatus.textContent = state.phase === "error" ? "Error" : "Waiting";
    ui.runStatus.className = `status-tag ${state.phase === "error" ? "status-error" : ""}`;
    ui.operator.textContent = "—";
    ui.startedAt.textContent = "—";
    ui.stepNumber.textContent = "—";
    ui.stepTitle.textContent = "Awaiting approved protocol state";
    ui.stepDetail.textContent = "Protocol instructions will appear from the recorded run.";
    ui.sampleCount.textContent = "0 tracked";
    ui.samples.replaceChildren(makeNode("span", "empty-copy", "No samples recorded"));
    return;
  }

  const rawStepNumber = Number.isInteger(run.current_step_index) ? run.current_step_index + 1 : null;
  const stepNumber = run.status === "completed" && Number.isInteger(protocol.step_count)
    ? protocol.step_count
    : rawStepNumber;
  const protocolName = valueText(protocol.name || run.protocol_name || run.protocol_id, "Protocol name unavailable");
  ui.protocolVersion.textContent = `Approved protocol ${valueText(run.protocol_id, "—")} · version ${valueText(run.protocol_version, "—")}`;
  ui.protocolName.textContent = protocolName;
  ui.runStatus.textContent = valueText(run.status, "unknown");
  ui.runStatus.className = `status-tag status-${valueText(run.status, "unknown")}`;
  ui.operator.textContent = valueText(run.operator, "Not recorded");
  ui.startedAt.textContent = run.started_at ? formatTime(run.started_at) : "Not recorded";
  ui.stepNumber.textContent = stepNumber ? String(stepNumber).padStart(2, "0") : "—";
  ui.stepTitle.textContent = valueText(step?.title, run.status === "completed" ? "Protocol complete" : "Step details not recorded");
  ui.stepDetail.textContent = valueText(
    step?.instruction,
    run.status === "completed"
      ? "All recorded protocol steps are complete."
      : "The run records a step index, but no instruction text is available.",
  );

  const samples = safeArray(run.sample_ids);
  ui.sampleCount.textContent = `${samples.length} tracked`;
  ui.samples.replaceChildren(...(samples.length
    ? samples.map((sample) => {
        const token = makeNode("span", "sample-token", valueText(sample));
        token.title = valueText(sample);
        return token;
      })
    : [makeNode("span", "empty-copy", "No samples recorded")]
  ));
}

function measurementEvents(events) {
  return events
    .filter((event) => event?.kind === "measurement")
    .slice()
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
}

function renderMeasurements(events, step) {
  const measurements = measurementEvents(events);
  const latest = measurements.at(-1);
  const payload = latest?.payload || {};
  ui.measurementCount.textContent = `${measurements.length} reading${measurements.length === 1 ? "" : "s"}`;

  if (!latest) {
    ui.latestSample.textContent = "Latest recorded value";
    ui.latestValue.textContent = "—";
    ui.latestMeta.textContent = "No measurement recorded";
  } else {
    ui.latestSample.textContent = valueText(payload.sample_id, "Run-level reading");
    ui.latestValue.textContent = payload.value === null || payload.value === undefined
      ? "Incomplete"
      : `${payload.value} ${payload.unit || ""}`.trim();
    ui.latestMeta.textContent = `${valueText(payload.instrument, "Instrument not recorded")} · ${formatTime(latest.created_at)}`;
  }

  const range = step?.expected_range;
  const minimum = range?.minimum;
  const maximum = range?.maximum;
  const value = payload.value;
  const completeRange = finiteNumber(minimum) && finiteNumber(maximum) && maximum > minimum;
  const completeValue = finiteNumber(value);
  if (completeRange) {
    ui.rangeLabel.textContent = `${minimum}–${maximum} ${valueText(step.expected_unit || payload.unit, "")}`.trim();
    if (completeValue) {
      const rawPosition = ((value - minimum) / (maximum - minimum)) * 100;
      const position = Math.max(0, Math.min(100, rawPosition));
      const outside = value < minimum || value > maximum;
      ui.rangePanel.dataset.rangeState = outside ? "warning" : "ready";
      ui.rangeMarker.style.setProperty("--range-position", `${position}%`);
      ui.rangeNote.textContent = outside
        ? "Recorded value is outside the approved protocol range."
        : "Recorded value is within the approved protocol range.";
    } else {
      ui.rangePanel.dataset.rangeState = "empty";
      ui.rangeNote.textContent = "A value is required before comparison.";
    }
  } else {
    ui.rangePanel.dataset.rangeState = "empty";
    ui.rangeLabel.textContent = "Not recorded";
    ui.rangeMarker.style.removeProperty("--range-position");
    ui.rangeNote.textContent = "LabLoop does not infer a range when one is absent.";
  }

  const recent = measurements.slice(-8).reverse();
  ui.measurements.replaceChildren(...(recent.length
    ? recent.map((event) => {
        const item = makeNode("li", "measurement-row");
        const head = makeNode("div");
        const eventPayload = event.payload || {};
        const reading = eventPayload.value === null || eventPayload.value === undefined
          ? "Incomplete reading"
          : `${eventPayload.value} ${eventPayload.unit || ""}`.trim();
        head.append(
          makeNode("strong", "", reading),
          makeNode("time", "", formatTime(event.created_at)),
        );
        head.lastChild.dateTime = event.created_at || "";
        item.append(
          head,
          makeNode("p", "", `${valueText(eventPayload.sample_id, "Run-level")} · ${valueText(eventPayload.instrument, "Instrument not recorded")}`),
        );
        return item;
      })
    : [makeNode("li", "empty-copy", "No measurements recorded")]
  ));
}

function severityFor(event) {
  const severities = safeArray(event?.payload?.issues).map((issue) => issue?.severity);
  return severities.includes("blocking") ? "blocking" : "warning";
}

function renderSignals(events) {
  const deviations = events.filter((event) => event?.kind === "deviation");
  const messages = events.filter((event) => event?.kind === "supervisor");
  ui.deviationCount.textContent = `${deviations.length} flag${deviations.length === 1 ? "" : "s"}`;
  ui.messageCount.textContent = `${messages.length} message${messages.length === 1 ? "" : "s"}`;
  ui.signalCount.textContent = `${deviations.length + messages.length} recorded signal${deviations.length + messages.length === 1 ? "" : "s"}`;

  ui.deviations.replaceChildren(...(deviations.length
    ? deviations.slice(-5).reverse().map((event) => {
        const severity = severityFor(event);
        const item = makeNode("li", "signal-item");
        const symbol = makeNode("span", `signal-symbol ${severity}`);
        symbol.append(makeNode("span", "", severity === "blocking" ? "!" : "△"));
        const copy = makeNode("div");
        copy.append(
          makeNode("p", "", eventSummary(event)),
          makeNode("span", "signal-meta", `Automated protocol check · ${severity} · ${formatTime(event.created_at)}`),
        );
        item.append(symbol, copy);
        return item;
      })
    : [makeNode("li", "empty-copy", "No deviations recorded")]
  ));

  ui.messages.replaceChildren(...(messages.length
    ? messages.slice(-5).reverse().map((event) => {
        const payload = event.payload || {};
        const item = makeNode("li", "signal-item");
        const symbol = makeNode("span", "signal-symbol supervisor", "↗");
        const copy = makeNode("div");
        const direction = valueText(payload.direction, "message");
        copy.append(
          makeNode("p", "", eventSummary(event)),
          makeNode("span", "signal-meta", `${eventSource(event)} · ${direction} · ${formatTime(event.created_at)}`),
        );
        item.append(symbol, copy);
        return item;
      })
    : [makeNode("li", "empty-copy", "No supervisor messages recorded")]
  ));
}

function renderInventory() {
  const items = safeArray(state.inventory.items);
  const requests = safeArray(state.inventory.pending_requests);
  const requestItems = new Set(requests.map((request) => request?.item_id).filter(Boolean));
  ui.requestCount.textContent = `${requests.length} pending request${requests.length === 1 ? "" : "s"}`;
  ui.inventory.replaceChildren(...(items.length
    ? items.map((item) => {
        const quantity = finiteNumber(item.quantity) ? item.quantity : null;
        const threshold = finiteNumber(item.reorder_threshold) ? item.reorder_threshold : null;
        const low = quantity !== null && threshold !== null && quantity <= threshold;
        const scale = quantity !== null && threshold !== null
          ? Math.max(quantity, threshold * 1.75, 1)
          : null;
        const fill = scale ? Math.max(0, Math.min(100, (quantity / scale) * 100)) : 0;
        const thresholdPosition = scale ? Math.max(0, Math.min(100, (threshold / scale) * 100)) : 35;
        const pending = requestItems.has(item.id);
        const row = makeNode("div", `inventory-row ${low ? "is-low" : ""}`);
        const identity = makeNode("div", "inventory-identity");
        identity.append(
          makeNode("strong", "", valueText(item.name || item.id, "Unnamed material")),
          makeNode("span", "", low ? "Below next-run threshold" : quantity === null ? "Quantity unavailable" : "Stock level sufficient"),
        );
        const reservoir = makeNode("div", "reservoir");
        reservoir.style.setProperty("--threshold-position", `${thresholdPosition}%`);
        const reservoirFill = makeNode("span", "reservoir-fill");
        reservoirFill.style.setProperty("--fill-position", `${fill}%`);
        reservoir.append(reservoirFill);
        const amount = makeNode("div", "inventory-amount");
        amount.append(
          makeNode("strong", "", quantity === null ? "Quantity unavailable" : `${quantity} ${valueText(item.unit, "")}`.trim()),
          makeNode("span", "", threshold === null ? "Threshold unavailable" : `Threshold ${threshold} ${valueText(item.unit, "")}`.trim()),
          makeNode("span", `request-tag ${pending ? "is-pending" : ""}`, pending ? "Pending request — human approval required" : "No pending request"),
        );
        row.append(identity, reservoir, amount);
        return row;
      })
    : [makeNode("p", "empty-copy", "No inventory items recorded")]
  ));
}

function markNewEvent(item, eventId) {
  if (!eventId) return;
  item.dataset.eventId = eventId;
  if (initialEventsSeen && !seenEventIds.has(eventId)) item.classList.add("is-new");
  seenEventIds.add(eventId);
  if (seenEventIds.size > 500) seenEventIds.delete(seenEventIds.values().next().value);
}

function renderTimeline(events) {
  const ordered = events
    .slice()
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)) || String(left.id).localeCompare(String(right.id)));
  const visible = ordered.slice(-100);
  const correctionsByTarget = new Map();
  for (const event of ordered) {
    if (event?.supersedes_event_id) correctionsByTarget.set(event.supersedes_event_id, event.id);
  }
  ui.eventCount.textContent = ordered.length > 100 ? `100 of ${ordered.length} events shown` : `${ordered.length} event${ordered.length === 1 ? "" : "s"}`;

  const nodes = [];
  let lastDate = null;
  for (const event of visible) {
    const date = formatDate(event.created_at);
    if (date !== lastDate) {
      nodes.push(makeNode("li", "timeline-date", date));
      lastDate = date;
    }
    const item = makeNode("li", "timeline-event");
    markNewEvent(item, event.id);
    const kind = valueText(event.kind, "event");
    const marker = makeNode("span", `event-marker kind-${kind}`);
    marker.setAttribute("aria-hidden", "true");
    const copy = makeNode("div", "event-copy");
    copy.append(
      makeNode("p", "", eventSummary(event)),
      makeNode("span", "", `${eventSource(event)} · ${valueText(event.id, "Event ID unavailable")}`),
    );
    if (event.supersedes_event_id) {
      copy.append(makeNode("span", "correction-note", `Correction · supersedes ${event.supersedes_event_id}`));
    }
    if (correctionsByTarget.has(event.id)) {
      copy.append(makeNode("span", "correction-note", `Superseded by correction ${correctionsByTarget.get(event.id)}`));
    }
    const time = makeNode("time", "", formatTime(event.created_at));
    time.dateTime = event.created_at || "";
    item.append(makeNode("span", "event-kind", kind), marker, copy, time);
    nodes.push(item);
  }
  ui.timeline.replaceChildren(...(nodes.length ? nodes : [makeNode("li", "empty-copy", "No events recorded")]));
  initialEventsSeen = true;
}

function render() {
  renderConnection();
  renderRunSelector();
  const run = currentRun();
  const events = currentEvents();
  const step = currentStep(run, events);
  renderHero(run, step);
  renderRunStage(run, events, step);
  renderMeasurements(events, step);
  renderSignals(events);
  renderInventory();
  renderTimeline(events);
}

ui.runSelect.addEventListener("change", (event) => selectRun(event.target.value));
const refreshTimer = window.setInterval(refresh, 1000);
window.addEventListener("pagehide", () => window.clearInterval(refreshTimer), { once: true });
refresh();
