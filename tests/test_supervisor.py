import io
import json
import socket
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

from labloop.contracts import SupervisorMessage
from labloop.supervisor import SlackGateway


TOKEN = "xoxb-test-secret-token"


class Response(io.BytesIO):
    def __init__(self, payload: object, status: int = 200):
        super().__init__(json.dumps(payload).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class RawResponse(Response):
    def __init__(self, payload: bytes, status: int = 200):
        io.BytesIO.__init__(self, payload)
        self.status = status


class SlackGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = SlackGateway(TOKEN, "C lab")

    @patch("urllib.request.urlopen")
    def test_send_request_and_message_mapping(self, urlopen) -> None:
        outbound = "LabLoop run: run-1\nContext: {\"samples\":[\"S1\"]}\nQuestion: Continue?"
        urlopen.return_value = Response(
            {
                "ok": True,
                "channel": "C lab",
                "ts": "1704067200.123456",
                "message": {
                    "ts": "1704067200.123456",
                    "text": outbound,
                    "bot_id": "B-LABLOOP",
                },
            }
        )

        result = self.gateway.send_question(
            "run-1", {"samples": ["S1"]}, "Continue?"
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://slack.com/api/chat.postMessage")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")
        self.assertEqual(request.get_header("User-agent"), "LabLoop-Supervisor/0.1")
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 10})
        self.assertEqual(json.loads(request.data), {"channel": "C lab", "text": outbound})
        self.assertNotIn(TOKEN, request.data.decode())
        self.assertEqual(
            result,
            SupervisorMessage(
                id="1704067200.123456",
                run_id="run-1",
                channel="C lab",
                text=outbound,
                direction="outbound",
                created_at="2024-01-01T00:00:00.123456Z",
                thread_id="1704067200.123456",
            ),
        )

    @patch("urllib.request.urlopen")
    def test_fetch_encodes_query_orders_replies_and_filters_parent_and_bot(self, urlopen) -> None:
        urlopen.return_value = Response(
            {
                "ok": True,
                "messages": [
                    {"ts": "1704067200.000001", "text": "parent", "bot_id": "B-LABLOOP"},
                    {"ts": "1704067202.000001", "text": "second", "user": "U2"},
                    {"ts": "1704067203.000001", "text": "bot follow-up", "bot_id": "B-LABLOOP"},
                    {"ts": "1704067201.000001", "text": "first", "user": "U1"},
                ],
            }
        )

        result = self.gateway.fetch_replies("run / 1", "1704067200.000001")

        request = urlopen.call_args.args[0]
        parsed = urllib.parse.urlparse(request.full_url)
        self.assertEqual(parsed.path, "/api/conversations.replies")
        self.assertEqual(
            urllib.parse.parse_qs(parsed.query),
            {"channel": ["C lab"], "ts": ["1704067200.000001"]},
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual([message.text for message in result], ["first", "second"])
        self.assertEqual(result[0].direction, "inbound")
        self.assertEqual(result[0].run_id, "run / 1")
        self.assertEqual(result[0].channel, "C lab")
        self.assertEqual(result[0].thread_id, "1704067200.000001")
        self.assertEqual(result[0].created_at, "2024-01-01T00:00:01.000001Z")

    @patch("urllib.request.urlopen")
    def test_fetch_without_bot_identity_returns_every_message_after_parent(self, urlopen) -> None:
        urlopen.return_value = Response(
            {
                "ok": True,
                "messages": [
                    {"ts": "1704067200.000001", "text": "parent"},
                    {"ts": "1704067201.000001", "text": "bot or human"},
                ],
            }
        )
        self.assertEqual(
            [message.text for message in self.gateway.fetch_replies("run-1", "1704067200.000001")],
            ["bot or human"],
        )

    @patch("urllib.request.urlopen")
    def test_input_validation_precedes_network_access(self, urlopen) -> None:
        invalid_calls = [
            lambda: self.gateway.send_question("", {}, "question"),
            lambda: self.gateway.send_question("run", [], "question"),
            lambda: self.gateway.send_question("run", {"bad": object()}, "question"),
            lambda: self.gateway.send_question("run", {}, " "),
            lambda: self.gateway.send_question("run", {}, TOKEN),
            lambda: self.gateway.fetch_replies("run", " "),
        ]
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        urlopen.assert_not_called()
        with self.assertRaises(ValueError):
            SlackGateway(" ", "channel")
        with self.assertRaises(ValueError):
            SlackGateway(TOKEN, " ")

    @patch("urllib.request.urlopen")
    def test_oversized_message_is_rejected_before_network_access(self, urlopen) -> None:
        with self.assertRaisesRegex(ValueError, "40,000"):
            self.gateway.send_question("run", {}, "x" * 40_000)
        urlopen.assert_not_called()

    def test_expected_transport_and_response_failures_are_safe(self) -> None:
        failures = [
            urllib.error.HTTPError("https://slack.com", 403, TOKEN, {}, None),
            urllib.error.URLError(TOKEN),
            socket.timeout(TOKEN),
            Response({"ok": True}, status=503),
            RawResponse(b"not json"),
            Response({"ok": False, "error": TOKEN}),
            Response([]),
            Response({"ok": True, "channel": "C", "ts": "bad", "message": {}}),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch(
                "urllib.request.urlopen", side_effect=failure if isinstance(failure, BaseException) else None
            ) as urlopen:
                if not isinstance(failure, BaseException):
                    urlopen.return_value = failure
                with self.assertRaises(RuntimeError) as raised:
                    self.gateway.send_question("run", {}, "question")
                self.assertNotIn(TOKEN, str(raised.exception))

    def test_token_is_absent_from_repr(self) -> None:
        self.assertNotIn(TOKEN, repr(self.gateway))


if __name__ == "__main__":
    unittest.main()
