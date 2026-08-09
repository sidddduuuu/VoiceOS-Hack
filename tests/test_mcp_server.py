import asyncio
import contextlib
import io
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from labloop.contracts import (
    AuditEvent,
    EventKind,
    ExperimentRun,
    InventoryItem,
    ProtocolStep,
    PurchaseRequest,
    RunStatus,
    Severity,
    SupervisorMessage,
    ValidationIssue,
)
from labloop import mcp_server


INVALID_CALLS = [
    ("start_experiment", {"protocol_id": "dna", "operator": "Ada", "sample_ids": "s1"}),
    (
        "record_measurement",
        {
            "run_id": "run-1",
            "step_id": "step-1",
            "sample_id": "sample-1",
            "value": True,
            "unit": "mL",
        },
    ),
    (
        "record_measurement",
        {
            "run_id": "run-1",
            "step_id": "step-1",
            "sample_id": "sample-1",
            "value": float("inf"),
            "unit": "mL",
        },
    ),
    (
        "record_measurement",
        {
            "run_id": "run-1",
            "step_id": "step-1",
            "sample_id": "sample-1",
            "value": 1,
            "unit": "mL",
            "conditions": [],
        },
    ),
    (
        "record_measurement",
        {
            "run_id": "run-1",
            "step_id": "step-1",
            "sample_id": "sample-1",
            "value": 1,
            "unit": "mL",
            "captured_at": "tomorrow",
        },
    ),
    ("correct_record", {"run_id": "run-1", "event_id": "event-1", "replacement": []}),
    ("consume_inventory", {"item_id": "buffer", "amount": -1, "unit": "mL"}),
]


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self._set_contract_fixtures()
        self._set_backend_mocks()
        self._install_backend_modules()
        self.server = mcp_server.build_server("db.sqlite", "protocols")

    def _set_contract_fixtures(self):
        self.run = ExperimentRun(
            id="run-1",
            protocol_id="dna",
            protocol_version="1.0",
            operator="Ada",
            sample_ids=("sample-1",),
            status=RunStatus.RUNNING,
        )
        self.step = ProtocolStep(
            id="step-1",
            title="Lyse",
            instruction="Add buffer.",
            required_fields=("unit", "instrument"),
            timer_seconds=30,
        )
        self.event = AuditEvent(
            id="event-1",
            run_id="run-1",
            kind=EventKind.OBSERVATION,
            payload={},
            created_at="2026-08-09T12:00:00Z",
        )
        self.item = InventoryItem("buffer", "Buffer", 4.0, "mL", 5.0, 10.0)
        self.request = PurchaseRequest(
            "request-1", "buffer", 10.0, "mL", "pending", "2026-08-09T12:00:00Z"
        )
        self.message = SupervisorMessage(
            "message-1",
            "run-1",
            "channel-1",
            "Continue after confirming the lot.",
            "inbound",
            "2026-08-09T12:01:00Z",
            "thread-1",
        )

    def _set_backend_mocks(self):
        self.service = Mock()
        self.service.begin_experiment.return_value = self.run
        self.service.get_run.return_value = self.run
        self.service.get_current_step.return_value = self.step
        self.service.record_observation.return_value = self.event
        self.service.record_measurement.return_value = (self.event, [])
        self.service.complete_checkpoint.return_value = self.run
        self.service.correct_event.return_value = self.event
        self.service.finish_experiment.return_value = self.run

        self.inventory = Mock()
        self.inventory.consume.return_value = (self.item, None)
        self.gateway = Mock()
        self.gateway.send_question.return_value = self.message
        self.gateway.fetch_replies.return_value = [self.message]

    def _install_backend_modules(self):
        service_module = types.ModuleType("labloop.service")
        service_module.LabLoopService = Mock(return_value=self.service)
        inventory_module = types.ModuleType("labloop.inventory")
        inventory_module.InventoryStore = Mock(return_value=self.inventory)
        supervisor_module = types.ModuleType("labloop.supervisor")
        supervisor_module.SlackGateway = Mock(return_value=self.gateway)
        self.service_type = service_module.LabLoopService
        self.inventory_type = inventory_module.InventoryStore
        self.gateway_type = supervisor_module.SlackGateway
        self.modules = patch.dict(
            sys.modules,
            {
                "labloop.service": service_module,
                "labloop.inventory": inventory_module,
                "labloop.supervisor": supervisor_module,
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def call(self, name, **arguments):
        result = asyncio.run(self.server.call_tool(name, arguments))
        if isinstance(result, tuple):
            result = result[0]
        return "".join(block.text for block in result if hasattr(block, "text"))

    def test_registers_exact_tool_names(self):
        tools = asyncio.run(self.server.list_tools())
        self.assertEqual(
            {tool.name for tool in tools},
            {
                "start_experiment",
                "get_current_step",
                "record_observation",
                "record_measurement",
                "complete_step",
                "correct_record",
                "finish_experiment",
                "consume_inventory",
                "ask_supervisor",
                "check_supervisor_replies",
            },
        )
        self.service_type.assert_called_once_with("db.sqlite", "protocols")
        self.inventory_type.assert_called_once_with("db.sqlite")

    def test_valid_handlers_map_to_application_calls(self):
        current, sent, replies = self._call_valid_handlers()
        self.service.begin_experiment.assert_called_once_with("dna", "Ada", ["sample-1"])
        self.assertIn("Approved protocol step step-1", current)
        self.assertIn("Required fields: unit, instrument", current)
        self.assertIn("Timer: 30 seconds", current)
        self.service.record_observation.assert_called_once_with("run-1", "clear", None)
        measurement = self.service.record_measurement.call_args.args[0]
        self.assertEqual(measurement.value, 2.0)
        self.assertEqual(measurement.conditions, {"temperature_c": 22})
        self.assertEqual(measurement.captured_at, "2026-08-09T12:00:00Z")
        self.service.complete_checkpoint.assert_called_once_with("run-1", "step-1")
        self.service.correct_event.assert_called_once_with(
            "run-1", "event-0", {"note": "clear"}
        )
        self.service.finish_experiment.assert_called_once_with("run-1")
        self.inventory.consume.assert_called_once_with("buffer", 1.0, "mL")
        context = self.gateway.send_question.call_args.args[1]
        self.assertEqual(context["run"]["id"], "run-1")
        self.assertEqual(context["current_step"]["id"], "step-1")
        self.assertIn("thread-1", sent)
        self.gateway.fetch_replies.assert_called_once_with("run-1", "thread-1")
        self.assertIn("Attributed supervisor message", replies)

    def _call_valid_handlers(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "token", "SLACK_CHANNEL_ID": "channel-1"},
        ):
            self.call(
                "start_experiment",
                protocol_id=" dna ",
                operator=" Ada ",
                sample_ids=[" sample-1 "],
            )
            current = self.call("get_current_step", run_id="run-1")
            self.call("record_observation", run_id="run-1", note=" clear ", sample_id=None)
            self.call(
                "record_measurement",
                run_id="run-1",
                step_id="step-1",
                sample_id="sample-1",
                value=2,
                unit="mL",
                instrument="pipette",
                conditions={"temperature_c": 22},
                captured_at="2026-08-09T12:00:00Z",
            )
            self.call("complete_step", run_id="run-1", step_id="step-1")
            self.call(
                "correct_record",
                run_id="run-1",
                event_id="event-0",
                replacement={"note": "clear"},
            )
            self.call("finish_experiment", run_id="run-1")
            self.call("consume_inventory", item_id="buffer", amount=1, unit="mL")
            sent = self.call("ask_supervisor", run_id="run-1", question=" Continue? ")
            replies = self.call(
                "check_supervisor_replies", run_id="run-1", thread_id="thread-1"
            )
        return current, sent, replies

    def test_malformed_boundaries_stop_downstream_calls(self):
        for name, arguments in INVALID_CALLS:
            with self.subTest(name=name, arguments=arguments):
                self.assertIn("Unable to", self.call(name, **arguments))

        self.service.begin_experiment.assert_not_called()
        self.service.record_measurement.assert_not_called()
        self.service.correct_event.assert_not_called()
        self.inventory.consume.assert_not_called()

    def test_measurement_responses_are_safe_and_concise(self):
        blocking = ValidationIssue("instrument", "Which instrument was used?", Severity.BLOCKING)
        warning = ValidationIssue("value", "Unexpected diagnostic detail", Severity.WARNING)
        arguments = {
            "run_id": "run-1",
            "step_id": "step-1",
            "sample_id": "sample-1",
            "value": 9,
            "unit": "mL",
        }

        self.service.record_measurement.return_value = (self.event, [blocking, warning])
        response = self.call("record_measurement", **arguments)
        self.assertEqual(
            response,
            "Follow-up required: Which instrument was used? (1 remaining issue).",
        )

        self.service.record_measurement.return_value = (self.event, [warning])
        response = self.call("record_measurement", **arguments)
        self.assertEqual(response, "Measurement recorded; value is outside the approved range.")
        self.assertNotIn(warning.question, response)

        self.service.record_measurement.return_value = (self.event, [])
        self.assertEqual(self.call("record_measurement", **arguments), "Measurement recorded.")

    def test_inventory_reports_pending_request_without_purchase_claim(self):
        self.inventory.consume.return_value = (self.item, self.request)
        response = self.call("consume_inventory", item_id="buffer", amount=1, unit="mL")
        self.assertIn("Pending restock request", response)
        self.assertIn("human approval", response)
        self.assertNotIn("order was placed", response.lower())

    def test_absent_slack_configuration_is_safe_and_actionable(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.call("ask_supervisor", run_id="run-1", question="Continue?")
        self.assertIn("SLACK_BOT_TOKEN", response)
        self.assertNotIn("db.sqlite", response)
        self.gateway.send_question.assert_not_called()

    def test_main_uses_stdio_defaults_without_stdout(self):
        fake_server = Mock()
        stdout = io.StringIO()
        with (
            patch.object(mcp_server, "build_server", return_value=fake_server) as build,
            patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stdout(stdout),
        ):
            mcp_server.main()

        build.assert_called_once_with("./labloop.db", "./protocols")
        fake_server.run.assert_called_once_with(transport="stdio")
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
