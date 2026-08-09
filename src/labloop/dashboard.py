"""Read-only HTTP dashboard for live LabLoop runs."""

from __future__ import annotations

import json
import os
import re
from dataclasses import fields, is_dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_RESPONSE_BYTES = 512 * 1024
MAX_RUN_ID_LENGTH = 128
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _handler_class(event_store: Any, inventory_store: Any, web_dir: Path = WEB_DIR):
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "LabLoopDashboard/1"

        def do_GET(self) -> None:  # noqa: N802
            self._serve(head_only=False)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(head_only=True)

        def do_POST(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_PUT(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_DELETE(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_PATCH(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._method_not_allowed()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _serve(self, head_only: bool) -> None:
            try:
                path = unquote(urlsplit(self.path).path)
                if path in STATIC_ROUTES:
                    filename, content_type = STATIC_ROUTES[path]
                    self._send(200, (web_dir / filename).read_bytes(), content_type, head_only)
                    return
                if path == "/api/health":
                    self._send_json(200, {"status": "ok"}, head_only)
                    return
                if path == "/api/runs":
                    self._send_json(200, {"runs": event_store.list_runs()}, head_only)
                    return
                if path == "/api/inventory":
                    self._send_json(
                        200,
                        {
                            "items": inventory_store.list_items(),
                            "pending_requests": inventory_store.list_purchase_requests(
                                status="pending"
                            ),
                        },
                        head_only,
                    )
                    return
                if path.startswith("/api/runs/"):
                    self._serve_run(path.removeprefix("/api/runs/"), head_only)
                    return
                self._send_json(404, {"error": "not found"}, head_only)
            except Exception:
                self._send_json(500, {"error": "internal server error"}, head_only)

        def _serve_run(self, run_id: str, head_only: bool) -> None:
            if (
                not 1 <= len(run_id) <= MAX_RUN_ID_LENGTH
                or RUN_ID_PATTERN.fullmatch(run_id) is None
            ):
                self._send_json(400, {"error": "invalid run id"}, head_only)
                return
            run = event_store.get_run(run_id)
            if run is None:
                self._send_json(404, {"error": "run not found"}, head_only)
                return
            self._send_json(
                200,
                {"run": run, "events": event_store.list_events(run_id)},
                head_only,
            )

        def _method_not_allowed(self) -> None:
            self._send_json(
                405, {"error": "method not allowed"}, head_only=False, allow="GET, HEAD"
            )

        def _send_json(
            self, status: int, value: Any, head_only: bool, allow: str | None = None
        ) -> None:
            try:
                body = _json_bytes(value)
            except (TypeError, ValueError):
                status, body = 500, b'{"error":"internal server error"}'
            self._send(status, body, "application/json; charset=utf-8", head_only, allow)

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
            head_only: bool,
            allow: str | None = None,
        ) -> None:
            if len(body) > MAX_RESPONSE_BYTES:
                status = 500
                content_type = "application/json; charset=utf-8"
                body = b'{"error":"response too large"}'
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if allow:
                self.send_header("Allow", allow)
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

    return DashboardHandler


def _port_from_environment() -> int:
    raw_port = os.environ.get("LABLOOP_DASHBOARD_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as error:
        raise ValueError("LABLOOP_DASHBOARD_PORT must be an integer") from error
    if not 1024 <= port <= 65535:
        raise ValueError("LABLOOP_DASHBOARD_PORT must be between 1024 and 65535")
    return port


def main() -> None:
    from labloop.inventory import InventoryStore
    from labloop.storage import EventStore

    raw_db_path = os.environ.get("LABLOOP_DB_PATH", "./labloop.db")
    if not raw_db_path.strip() or "\0" in raw_db_path:
        raise ValueError("LABLOOP_DB_PATH must be a non-empty filesystem path")
    db_path = Path(raw_db_path)
    server = ThreadingHTTPServer(
        (HOST, _port_from_environment()),
        _handler_class(EventStore(db_path), InventoryStore(db_path)),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
