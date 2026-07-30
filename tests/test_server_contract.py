"""Offline contract tests for MCP registration and response envelopes."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp import Client

from t20_mcp import __version__, server
from t20_mcp.client import _failure, _safe
from t20_mcp.mcp_runtime import LEGACY_PROTOCOL_VERSION, MODERN_PROTOCOL_VERSION

EXPECTED_TOOLS = {
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


def test_registered_tool_names_and_mutability_annotations_are_consistent() -> None:
    tools = server.mcp._tool_manager._tools

    assert set(tools) == EXPECTED_TOOLS
    assert all(tool.annotations.read_only_hint is False for tool in tools.values())
    assert tuple(spec.tool_name for spec in server.TOOL_SPECS) == tuple(tools)


def test_mcp_2026_protocol_and_server_identity_are_advertised() -> None:
    async def exercise() -> None:
        async with Client(server.mcp, mode="auto") as client:
            assert client.protocol_version == MODERN_PROTOCOL_VERSION
            assert client.session.discover_result is not None
            assert client.session.initialize_result is None
            assert client.server_info is not None
            assert client.server_info.name == "autocad-mcp"
            assert client.server_info.version == __version__

            tools = await client.list_tools()
            assert tools.result_type == "complete"
            assert {tool.name for tool in tools.tools} == set(server.mcp._tool_manager._tools)
            assert all(tool.output_schema is not None for tool in tools.tools)
            assert all(tool.output_schema["required"] == ["ok"] for tool in tools.tools)

            result = await client.call_tool(
                "tangent",
                {
                    "operation": "axis_lines",
                    "data": {"hspacings": [3000], "vspacings": [2000]},
                },
            )
            assert result.result_type == "complete"
            assert result.is_error is False
            assert result.structured_content["ok"] is True
            assert result.structured_content["operation"] == "axis_lines"
            assert result.structured_content["dry_run"] is True

            failure = await client.call_tool("tangent", {"operation": "bogus"})
            assert failure.result_type == "complete"
            assert failure.is_error is True
            assert failure.structured_content["ok"] is False
            assert "[tangent.bogus]" in failure.structured_content["error"]

    asyncio.run(exercise())


def test_mcp_legacy_clients_remain_supported() -> None:
    async def exercise() -> None:
        async with Client(server.mcp, mode="legacy") as client:
            assert client.protocol_version == LEGACY_PROTOCOL_VERSION
            assert client.session.discover_result is None
            assert client.session.initialize_result is not None
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == set(server.mcp._tool_manager._tools)
            assert all(tool.output_schema is not None for tool in tools.tools)

            result = await client.call_tool(
                "tangent",
                {
                    "operation": "axis_lines",
                    "data": {"hspacings": [3000], "vspacings": [2000]},
                },
            )
            assert result.is_error is False
            assert result.structured_content["ok"] is True

    asyncio.run(exercise())


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
