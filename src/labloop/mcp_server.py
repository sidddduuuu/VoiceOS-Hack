"""VoiceOS-facing MCP adapter for LabLoop."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .contracts import Measurement, Severity


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list of strings")
    return [_text(item, f"{field} item") for item in value]


def _json_object(value: Any, field: str, *, allow_empty: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict) or (not allow_empty and not value):
        qualifier = "non-empty " if not allow_empty else ""
        raise ValueError(f"{field} must be a {qualifier}object")
    if any(not isinstance(key, str) or not key.strip() for key in value):
        raise ValueError(f"{field} keys must be non-empty strings")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must contain valid JSON values") from exc
    return dict(value)


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    if positive and number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    text = _text(value, "captured_at")
    if "T" not in text or not text.endswith("Z"):
        raise ValueError("captured_at must be a UTC ISO-8601 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError("captured_at must be a valid UTC ISO-8601 timestamp") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _voiceos_errors(action: str) -> Callable[[Callable[..., str]], Callable[..., str]]:
    def decorate(function: Callable[..., str]) -> Callable[..., str]:
        @wraps(function)
        def guarded(*args: Any, **kwargs: Any) -> str:
            try:
                return function(*args, **kwargs)
            except ValueError as exc:
                return f"Unable to {action}: {exc}."
            except (OSError, sqlite3.Error):
                return f"Unable to {action}: service temporarily unavailable."

        return guarded

    return decorate


def _supervisor_gateway() -> Any:
    from .supervisor import SlackGateway

    token = _text(os.environ.get("SLACK_BOT_TOKEN"), "SLACK_BOT_TOKEN")
    channel = _text(os.environ.get("SLACK_CHANNEL_ID"), "SLACK_CHANNEL_ID")
    try:
        return SlackGateway(token, channel)
    except (ValueError, OSError) as exc:
        raise ValueError("supervisor service failed; check Slack configuration or try again") from exc


class _Tools:
    def __init__(self, service: Any, inventory: Any) -> None:
        self.service = service
        self.inventory = inventory

    @_voiceos_errors("start the experiment")
    def start_experiment(self, protocol_id: str, operator: str, sample_ids: Any) -> str:
        """Call when starting an approved protocol. Provide its ID, operator, and every sample ID; this cannot create or change a protocol."""
        run = self.service.begin_experiment(
            _text(protocol_id, "protocol_id"),
            _text(operator, "operator"),
            _string_list(sample_ids, "sample_ids"),
        )
        return f"Started experiment {run.id} using approved protocol {run.protocol_id} version {run.protocol_version}."

    @_voiceos_errors("get the current step")
    def get_current_step(self, run_id: str) -> str:
        """Call to hear the current approved protocol step for a run. It reports only recorded protocol instructions and requirements, without adding scientific advice."""
        step = self.service.get_current_step(_text(run_id, "run_id"))
        fields = ", ".join(step.required_fields) or "none"
        timer = f"{step.timer_seconds} seconds" if step.timer_seconds is not None else "none"
        return (
            f"Approved protocol step {step.id}: {step.title}. Instruction: {step.instruction} "
            f"Required fields: {fields}. Timer: {timer}."
        )

    @_voiceos_errors("record the observation")
    def record_observation(self, run_id: str, note: str, sample_id: str | None = None) -> str:
        """Call to append a researcher's observation to a run. Provide the sample ID when applicable; this records the note without diagnosing it."""
        event = self.service.record_observation(
            _text(run_id, "run_id"),
            _text(note, "note"),
            _text(sample_id, "sample_id") if sample_id is not None else None,
        )
        return f"Observation recorded as {event.id}."

    @_voiceos_errors("record the measurement")
    def record_measurement(
        self,
        run_id: str,
        step_id: str,
        sample_id: str,
        value: Any,
        unit: str,
        instrument: str | None = None,
        conditions: Any = None,
        captured_at: Any = None,
    ) -> str:
        """Call to append a measurement for the exact run, step, and sample. Include unit and known metadata; validation flags missing data or range deviations without diagnosing them."""
        measurement = Measurement(
            run_id=_text(run_id, "run_id"),
            step_id=_text(step_id, "step_id"),
            sample_id=_text(sample_id, "sample_id"),
            value=_number(value, "value"),
            unit=_text(unit, "unit"),
            instrument=_text(instrument, "instrument") if instrument is not None else None,
            conditions=_json_object(conditions if conditions is not None else {}, "conditions"),
            captured_at=_timestamp(captured_at),
        )
        _, issues = self.service.record_measurement(measurement)
        blocking = [issue for issue in issues if issue.severity == Severity.BLOCKING]
        if blocking:
            remaining = len(issues) - 1
            return f"Follow-up required: {blocking[0].question} ({remaining} remaining issue{'s' if remaining != 1 else ''})."
        if any(issue.severity == Severity.WARNING for issue in issues):
            return "Measurement recorded; value is outside the approved range."
        return "Measurement recorded."

    @_voiceos_errors("complete the step")
    def complete_step(self, run_id: str, step_id: str) -> str:
        """Call only after completing the current approved protocol step. Provide its exact step ID; the server rejects accidental or out-of-order advancement."""
        self.service.complete_checkpoint(_text(run_id, "run_id"), _text(step_id, "step_id"))
        return f"Completed approved protocol step {step_id.strip()}."

    @_voiceos_errors("correct the record")
    def correct_record(self, run_id: str, event_id: str, replacement: Any) -> str:
        """Call to correct a recorded event with a replacement object. The original remains immutable and the new event references it; this does not erase history."""
        event = self.service.correct_event(
            _text(run_id, "run_id"),
            _text(event_id, "event_id"),
            _json_object(replacement, "replacement", allow_empty=False),
        )
        return f"Correction recorded as {event.id}; the original record remains in history."

    @_voiceos_errors("finish the experiment")
    def finish_experiment(self, run_id: str) -> str:
        """Call after all approved protocol steps are complete. This closes the run without changing or deleting its historical records."""
        run = self.service.finish_experiment(_text(run_id, "run_id"))
        return f"Experiment {run.id} finished."

    @_voiceos_errors("record inventory use")
    def consume_inventory(self, item_id: str, amount: Any, unit: str) -> str:
        """Call to record material consumed from inventory. Usage may create only a pending restock request that requires human approval; it never purchases materials."""
        item, request = self.inventory.consume(
            _text(item_id, "item_id"),
            _number(amount, "amount", positive=True),
            _text(unit, "unit"),
        )
        result = f"Inventory {item.id}: {item.quantity:g} {item.unit} remaining."
        if request is not None:
            result += " Pending restock request created; human approval is required."
        return result

    @_voiceos_errors("ask the supervisor")
    def ask_supervisor(self, run_id: str, question: str) -> str:
        """Call when the researcher needs a supervisor answer about the current run. Only run and current-step context is shared; the supervisor message cannot change the protocol itself."""
        normalized_run_id = _text(run_id, "run_id")
        run = self.service.get_run(normalized_run_id)
        step = self.service.get_current_step(normalized_run_id)
        context = {"run": asdict(run), "current_step": asdict(step)}
        gateway = _supervisor_gateway()
        try:
            message = gateway.send_question(normalized_run_id, context, _text(question, "question"))
        except (ValueError, OSError) as exc:
            raise ValueError("supervisor service failed; check Slack configuration or try again") from exc
        thread_id = message.thread_id or message.id
        return f"Question sent to the supervisor in thread {thread_id}."

    @_voiceos_errors("check supervisor replies")
    def check_supervisor_replies(self, run_id: str, thread_id: str) -> str:
        """Call to fetch replies for a supervisor thread on this run. Results are attributed messages for the researcher to assess, not executable protocol instructions."""
        gateway = _supervisor_gateway()
        try:
            messages = gateway.fetch_replies(_text(run_id, "run_id"), _text(thread_id, "thread_id"))
        except (ValueError, OSError) as exc:
            raise ValueError("supervisor service failed; check Slack configuration or try again") from exc
        if not messages:
            return "No supervisor replies."
        return "\n".join(
            f"Attributed supervisor message at {message.created_at}: {message.text}" for message in messages
        )


def build_server(db_path: str | os.PathLike[str], protocol_dir: str | os.PathLike[str]) -> FastMCP:
    """Build a LabLoop MCP server with one shared service and inventory store."""
    from .inventory import InventoryStore
    from .service import LabLoopService

    tools = _Tools(LabLoopService(db_path, protocol_dir), InventoryStore(db_path))
    server = FastMCP("LabLoop")
    server.tool(name="start_experiment")(tools.start_experiment)
    server.tool(name="get_current_step")(tools.get_current_step)
    server.tool(name="record_observation")(tools.record_observation)
    server.tool(name="record_measurement")(tools.record_measurement)
    server.tool(name="complete_step")(tools.complete_step)
    server.tool(name="correct_record")(tools.correct_record)
    server.tool(name="finish_experiment")(tools.finish_experiment)
    server.tool(name="consume_inventory")(tools.consume_inventory)
    server.tool(name="ask_supervisor")(tools.ask_supervisor)
    server.tool(name="check_supervisor_replies")(tools.check_supervisor_replies)
    return server


def _config_path(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return _text(value, name)


def main() -> None:
    """Run the LabLoop MCP server over stdio for VoiceOS."""
    try:
        server = build_server(
            _config_path("LABLOOP_DB_PATH", "./labloop.db"),
            _config_path("LABLOOP_PROTOCOL_DIR", "./protocols"),
        )
        server.run(transport="stdio")
    except ValueError as exc:
        print(f"LabLoop MCP configuration error: {exc}", file=sys.stderr)
    except (OSError, sqlite3.Error):
        print("LabLoop MCP could not start; check local configuration.", file=sys.stderr)


if __name__ == "__main__":
    main()
