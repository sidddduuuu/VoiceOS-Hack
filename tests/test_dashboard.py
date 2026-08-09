import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from labloop.contracts import (
    AuditEvent,
    EventKind,
    ExpectedRange,
    ExperimentRun,
    InventoryItem,
    Protocol,
    ProtocolStep,
    PurchaseRequest,
    RunStatus,
)
from labloop.dashboard import SECURITY_HEADERS, _handler_class, _port_from_environment


class MockEventStore:
    def __init__(self) -> None:
        self.run = ExperimentRun(
            id="run-1",
            protocol_id="dna-demo",
            protocol_version="1.0",
            operator="Ada",
            sample_ids=("sample-a", "sample-b"),
            status=RunStatus.RUNNING,
            current_step_index=2,
            started_at="2026-08-09T12:00:00Z",
        )
        self.events = [
            AuditEvent(
                id="event-1",
                run_id="run-1",
                kind=EventKind.MEASUREMENT,
                payload={"values": (1.5, 2.0), "nested": {"kind": EventKind.DEVIATION}},
                created_at="2026-08-09T12:01:00Z",
            )
        ]
        self.reads: list[tuple[str, object]] = []

    def list_runs(self):
        self.reads.append(("list_runs", None))
        return [self.run]

    def get_run(self, run_id):
        self.reads.append(("get_run", run_id))
        return self.run if run_id == self.run.id else None

    def list_events(self, run_id):
        self.reads.append(("list_events", run_id))
        return self.events


class MockInventoryStore:
    def __init__(self) -> None:
        self.reads: list[tuple[str, object]] = []

    def list_items(self):
        self.reads.append(("list_items", None))
        return [InventoryItem("kit", "Extraction kit", 2, "runs", 3, 6)]

    def list_purchase_requests(self, status=None):
        self.reads.append(("list_purchase_requests", status))
        return [PurchaseRequest("request-1", "kit", 6, "runs", "pending", "2026-08-09T12:02:00Z")]


class DashboardTests(unittest.TestCase):
    def test_dashboard_port_environment_is_validated(self) -> None:
        for raw_port in ("nope", "1023", "65536"):
            with self.subTest(raw_port=raw_port), patch.dict(
                "os.environ", {"LABLOOP_DASHBOARD_PORT": raw_port}
            ):
                with self.assertRaisesRegex(ValueError, "LABLOOP_DASHBOARD_PORT"):
                    _port_from_environment()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        web_dir = Path(self.temp_dir.name)
        (web_dir / "index.html").write_text("<main>LabLoop</main>", encoding="utf-8")
        (web_dir / "app.js").write_text("'use strict';", encoding="utf-8")
        (web_dir / "tokens.css").write_text(":root {}", encoding="utf-8")
        (web_dir / "styles.css").write_text("body {}", encoding="utf-8")
        (web_dir / "motion.css").write_text("", encoding="utf-8")
        self.events = MockEventStore()
        self.inventory = MockInventoryStore()
        self.protocols = {
            "dna-demo": Protocol(
                id="dna-demo",
                name="DNA Demo",
                version="1.0",
                steps=(
                    ProtocolStep("step-1", "Prepare", "Prepare the recorded samples."),
                    ProtocolStep("step-2", "Observe", "Record an observation."),
                    ProtocolStep(
                        "step-3",
                        "Measure",
                        "Record the approved measurement.",
                        expected_unit="demo units",
                        expected_range=ExpectedRange(10, 20),
                    ),
                ),
            )
        }
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _handler_class(self.events, self.inventory, web_dir, self.protocols),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp_dir.cleanup()

    def request(self, method: str, path: str):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, body

    def test_health_static_and_api_success(self) -> None:
        cases = (
            ("/api/health", "application/json", {"status": "ok"}),
            ("/api/runs", "application/json", None),
            ("/api/runs/run-1", "application/json", None),
            ("/api/inventory", "application/json", None),
            ("/", "text/html", None),
            ("/app.js", "application/javascript", None),
            ("/tokens.css", "text/css", None),
            ("/styles.css", "text/css", None),
            ("/motion.css", "text/css", None),
        )
        for path, content_type, expected in cases:
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith(content_type))
                if expected is not None:
                    self.assertEqual(json.loads(body), expected)

        status, headers, body = self.request("HEAD", "/api/health")
        self.assertEqual((status, body), (200, b""))
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_run_serializes_enums_tuples_and_nested_payloads(self) -> None:
        status, _, body = self.request("GET", "/api/runs/run-1")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["run"]["status"], "running")
        self.assertEqual(payload["run"]["sample_ids"], ["sample-a", "sample-b"])
        self.assertEqual(payload["events"][0]["payload"]["values"], [1.5, 2.0])
        self.assertEqual(payload["events"][0]["payload"]["nested"]["kind"], "deviation")
        self.assertEqual(payload["protocol"]["name"], "DNA Demo")
        self.assertEqual(payload["protocol"]["step_count"], 3)
        self.assertEqual(payload["current_step"]["id"], "step-3")
        self.assertEqual(payload["current_step"]["expected_range"], {"minimum": 10, "maximum": 20})

    def test_unknown_malformed_and_store_failure_are_safe(self) -> None:
        for path, expected in (
            ("/api/runs/missing", 404),
            ("/api/runs/bad%2Fid", 400),
            ("/api/runs/" + "x" * 129, 400),
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(status, expected)

        original = self.events.list_runs
        self.events.list_runs = lambda: (_ for _ in ()).throw(RuntimeError("/secret/db.sqlite"))
        status, _, body = self.request("GET", "/api/runs")
        self.events.list_runs = original
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"error": "internal server error"})
        self.assertNotIn(b"secret", body)

    def test_write_methods_are_rejected(self) -> None:
        before = (list(self.events.reads), list(self.inventory.reads))
        for method in ("POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                status, headers, body = self.request(method, "/api/runs")
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET, HEAD")
                self.assertEqual(json.loads(body)["error"], "method not allowed")
        self.assertEqual((self.events.reads, self.inventory.reads), before)

    def test_traversal_and_unknown_static_paths_are_not_served(self) -> None:
        for path in ("/../AGENTS.md", "/%2e%2e%2fAGENTS.md", "/missing.js"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"LabLoop repository instructions", body)

    def test_security_headers_are_on_static_and_json(self) -> None:
        for path in ("/", "/api/health", "/missing"):
            with self.subTest(path=path):
                _, headers, _ = self.request("GET", path)
                for name, value in SECURITY_HEADERS.items():
                    self.assertEqual(headers[name], value)

    def test_get_apis_only_call_read_methods(self) -> None:
        for path in ("/api/runs", "/api/runs/run-1", "/api/inventory"):
            self.request("GET", path)
        self.assertEqual(
            self.events.reads,
            [("list_runs", None), ("get_run", "run-1"), ("list_events", "run-1")],
        )
        self.assertEqual(
            self.inventory.reads,
            [("list_items", None), ("list_purchase_requests", "pending")],
        )


if __name__ == "__main__":
    unittest.main()
