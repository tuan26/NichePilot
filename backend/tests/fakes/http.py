"""Transport HTTP giả lập cho test adapter (TEST DOUBLE – không gọi mạng).

SDK anthropic/openai hiện dùng gói `httpx2`, nên dùng `httpx2.MockTransport` thay vì respx.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx2

Handler = Callable[[httpx2.Request], httpx2.Response]


@dataclass
class Recorder:
    responder: Handler | Exception
    calls: list[httpx2.Request] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(request)
        if isinstance(self.responder, Exception):
            raise self.responder
        return self.responder(request)

    @property
    def last_json(self) -> dict[str, Any]:
        return json.loads(self.calls[-1].content)


def mock_client(responder: Handler | Exception) -> tuple[httpx2.AsyncClient, Recorder]:
    rec = Recorder(responder)
    return httpx2.AsyncClient(transport=httpx2.MockTransport(rec)), rec


def json_response(status: int, body: dict[str, Any], headers: dict[str, str] | None = None) -> Handler:
    return lambda _req: httpx2.Response(status, json=body, headers=headers or {})
