"""Offline contract tests for MCP registration and response envelopes."""

from __future__ import annotations

import asyncio
import json

import pytest

from t20_mcp import server
from t20_mcp.client import _failure, _safe


def test_registered_tool_names_and_mutability_annotations_are_consistent() -> None:
    tools = server.mcp._tool_manager._tools

    assert set(tools) == {
        "drawing",
        "entity",
        "layer",
        "block",
        "annotation",
        "pid",
        "view",
        "system",
        "tangent",
    }
    assert all(tool.annotations.readOnlyHint is False for tool in tools.values())


def test_failure_helper_always_emits_explicit_failure_envelope() -> None:
    payload = json.loads(_failure("bad input", hint="fix it", payload={"code": "BAD"}))

    assert payload == {
        "ok": False,
        "error": "bad input",
        "hint": "fix it",
        "payload": {"code": "BAD"},
    }


def test_safe_decorator_uses_positional_operation_in_error_context() -> None:
    @_safe("demo")
    async def failing_tool(operation: str) -> str:
        raise RuntimeError("boom")

    payload = json.loads(asyncio.run(failing_tool("create")))

    assert payload["ok"] is False
    assert payload["error"] == "[demo.create] boom"


@pytest.mark.parametrize(
    ("handler", "kwargs", "tool_name"),
    [
        (server.drawing, {}, "drawing"),
        (server.entity, {}, "entity"),
        (server.layer, {}, "layer"),
        (server.block, {}, "block"),
        (server.annotation, {}, "annotation"),
        (server.pid, {}, "pid"),
        (server.view, {}, "view"),
        (server.system, {}, "system"),
    ],
)
def test_unknown_operation_returns_uniform_failure(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    kwargs: dict,
    tool_name: str,
) -> None:
    async def fake_get_backend():
        return object()

    monkeypatch.setattr(server, "get_backend", fake_get_backend)

    payload = json.loads(asyncio.run(handler(operation="bogus", **kwargs)))

    assert payload["ok"] is False
    assert payload["error"] == f"Unknown {tool_name} operation: bogus"
