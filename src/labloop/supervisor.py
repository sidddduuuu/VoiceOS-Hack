"""Minimal Slack transport for supervisor questions and replies."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import SupervisorMessage


_API_ROOT = "https://slack.com/api"
_TIMEOUT_SECONDS = 10
_USER_AGENT = "LabLoop-Supervisor/0.1"
_MAX_MESSAGE_LENGTH = 40_000
_SLACK_ERROR = re.compile(r"[a-z0-9_]{1,80}")
_SLACK_TIMESTAMP = re.compile(r"(\d+)\.(\d{1,6})")


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _timestamp_parts(value: object) -> tuple[int, int]:
    if not isinstance(value, str) or (match := _SLACK_TIMESTAMP.fullmatch(value)) is None:
        raise RuntimeError("Slack returned a malformed message timestamp")
    return int(match.group(1)), int(match.group(2).ljust(6, "0"))


def _iso_timestamp(value: object) -> str:
    seconds, microseconds = _timestamp_parts(value)
    try:
        timestamp = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            seconds=seconds, microseconds=microseconds
        )
    except OverflowError as error:
        raise RuntimeError("Slack returned a malformed message timestamp") from error
    return timestamp.isoformat().replace("+00:00", "Z")


def _message_fields(message: object) -> tuple[str, str]:
    if not isinstance(message, dict):
        raise RuntimeError("Slack returned a malformed message")
    timestamp = message.get("ts")
    text = message.get("text")
    _timestamp_parts(timestamp)
    if not isinstance(text, str):
        raise RuntimeError("Slack returned a malformed message")
    return timestamp, text


def _bot_identity(message: object) -> str | None:
    if not isinstance(message, dict):
        return None
    bot_id = message.get("bot_id")
    if isinstance(bot_id, str) and bot_id:
        return bot_id
    profile = message.get("bot_profile")
    if isinstance(profile, dict):
        profile_id = profile.get("id")
        if isinstance(profile_id, str) and profile_id:
            return profile_id
    return None


class SlackGateway:
    """Send questions to one Slack channel and read their thread replies."""

    def __init__(self, token: str, channel: str):
        self._token = _required_text(token, "token").strip()
        self._channel = _required_text(channel, "channel").strip()
        self._bot_id: str | None = None

    def __repr__(self) -> str:
        return "SlackGateway()"

    def send_question(
        self, run_id: str, context: dict, question: str
    ) -> SupervisorMessage:
        run_id = _required_text(run_id, "run_id")
        question = _required_text(question, "question")
        if not isinstance(context, dict):
            raise ValueError("context must be a dict")
        try:
            context_json = json.dumps(
                context, ensure_ascii=True, allow_nan=False, separators=(",", ":")
            )
        except (TypeError, ValueError) as error:
            raise ValueError("context must be JSON-serializable") from error

        text = f"LabLoop run: {run_id}\nContext: {context_json}\nQuestion: {question}"
        if self._token in text:
            raise ValueError("Slack message must not contain the configured token")
        if len(text) > _MAX_MESSAGE_LENGTH:
            raise ValueError("Slack message exceeds the 40,000-character limit")
        body = json.dumps({"channel": self._channel, "text": text}).encode("utf-8")
        payload = self._request_json("chat.postMessage", body=body)

        channel = payload.get("channel")
        timestamp = payload.get("ts")
        message = payload.get("message")
        if not isinstance(channel, str) or not channel or not isinstance(message, dict):
            raise RuntimeError("Slack returned a malformed chat.postMessage response")
        message_timestamp, message_text = _message_fields(message)
        if timestamp != message_timestamp:
            raise RuntimeError("Slack returned a malformed chat.postMessage response")
        if self._token in message_text:
            raise RuntimeError("Slack returned message text containing the configured token")
        self._bot_id = _bot_identity(message) or self._bot_id
        return SupervisorMessage(
            id=message_timestamp,
            run_id=run_id,
            channel=channel,
            text=message_text,
            direction="outbound",
            created_at=_iso_timestamp(message_timestamp),
            thread_id=message_timestamp,
        )

    def fetch_replies(
        self, run_id: str, thread_id: str
    ) -> list[SupervisorMessage]:
        run_id = _required_text(run_id, "run_id")
        thread_id = _required_text(thread_id, "thread_id")
        query = urllib.parse.urlencode({"channel": self._channel, "ts": thread_id})
        payload = self._request_json(f"conversations.replies?{query}")
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise RuntimeError("Slack returned a malformed conversations.replies response")
        if not messages:
            return []

        parent_timestamp, _ = _message_fields(messages[0])
        if parent_timestamp != thread_id:
            raise RuntimeError("Slack returned a malformed conversations.replies response")
        bot_id = _bot_identity(messages[0]) or self._bot_id
        replies: list[tuple[tuple[int, int], SupervisorMessage]] = []
        for raw_message in messages[1:]:
            timestamp, text = _message_fields(raw_message)
            if bot_id is not None and _bot_identity(raw_message) == bot_id:
                continue
            if self._token in text:
                raise RuntimeError("Slack returned message text containing the configured token")
            replies.append(
                (
                    _timestamp_parts(timestamp),
                    SupervisorMessage(
                        id=timestamp,
                        run_id=run_id,
                        channel=self._channel,
                        text=text,
                        direction="inbound",
                        created_at=_iso_timestamp(timestamp),
                        thread_id=thread_id,
                    ),
                )
            )
        return [message for _, message in sorted(replies, key=lambda item: item[0])]

    def _request_json(self, endpoint: str, body: bytes | None = None) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": _USER_AGENT,
        }
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            f"{_API_ROOT}/{endpoint}", data=body, headers=headers, method="POST" if body else "GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", None)
                if not isinstance(status, int) or isinstance(status, bool):
                    raise RuntimeError("Slack returned an invalid HTTP status")
                if not 200 <= status < 300:
                    raise RuntimeError(f"Slack request failed with HTTP status {status}")
                raw = response.read()
        except urllib.error.HTTPError as error:
            status = str(error.code).replace(self._token, "[redacted]")
            raise RuntimeError(f"Slack request failed with HTTP status {status}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            raise RuntimeError("Slack request failed; check network connectivity") from None

        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError("Slack returned malformed JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Slack returned a malformed response object")
        if payload.get("ok") is not True:
            code = payload.get("error")
            detail = (
                f": {code}"
                if isinstance(code, str)
                and self._token not in code
                and _SLACK_ERROR.fullmatch(code)
                else ""
            )
            raise RuntimeError(f"Slack API rejected the request{detail}")
        return payload
