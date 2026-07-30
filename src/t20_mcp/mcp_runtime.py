"""MCP protocol boundary, server construction, and tool registration.

Business handlers in this project intentionally return the compact JSON strings
used before MCP SDK v2.  This module is the only wire adapter: it preserves that
text content for older callers while also emitting typed ``CallToolResult``
objects with ``structuredContent`` and correct ``isError`` semantics.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import update_wrapper
from typing import Annotated, Any, TypeAlias

from mcp.server import MCPServer
from mcp.types import CallToolResult, ContentBlock, ImageContent, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, ValidationError

SERVER_NAME = "autocad-mcp"
MODERN_PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (MODERN_PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION)

ToolResult: TypeAlias = str | list[TextContent | ImageContent]
BusinessTool = Callable[..., Awaitable[ToolResult | CallToolResult]]
WireTool = Callable[..., Awaitable[CallToolResult]]


class ToolEnvelope(BaseModel):
    """Common structured output contract shared by every consolidated tool."""

    ok: bool
    payload: Any = None
    error: str | None = None
    hint: str | None = None

    model_config = ConfigDict(extra="allow")


WireToolResult: TypeAlias = Annotated[CallToolResult, ToolEnvelope]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declarative metadata for a business handler exposed as an MCP tool."""

    handler: BusinessTool
    title: str
    name: str | None = None
    read_only: bool = False

    @property
    def tool_name(self) -> str:
        return self.name or self.handler.__name__


def _structured_envelope(value: Any, *, default_ok: bool) -> dict[str, Any]:
    if isinstance(value, dict):
        envelope = dict(value)
        envelope.setdefault("ok", default_ok)
    else:
        envelope = {"ok": default_ok, "payload": value}

    try:
        envelope["ok"] = ToolEnvelope.model_validate(envelope).ok
    except ValidationError:
        return {
            "ok": False,
            "error": "Internal tool result did not satisfy the MCP output envelope",
            "payload": envelope,
        }
    return envelope


def _parse_text_envelope(content: Sequence[ContentBlock]) -> dict[str, Any] | None:
    for block in content:
        if not isinstance(block, TextContent):
            continue
        try:
            decoded = json.loads(block.text)
        except (json.JSONDecodeError, TypeError):
            continue
        return _structured_envelope(decoded, default_ok=True)
    return None


def to_call_tool_result(result: ToolResult | CallToolResult) -> CallToolResult:
    """Normalize a business result at the MCP wire boundary.

    Existing text/image content is retained verbatim.  JSON text is additionally
    exposed through ``structuredContent``; an ``ok: false`` envelope becomes an
    MCP execution error without turning it into a JSON-RPC protocol error.
    """

    if isinstance(result, CallToolResult):
        content = result.content
        structured = result.structured_content
        if structured is None:
            structured = _parse_text_envelope(content)
        envelope = _structured_envelope(structured, default_ok=not result.is_error)
        if result.is_error:
            envelope["ok"] = False
        return result.model_copy(
            update={
                "structured_content": envelope,
                "is_error": envelope["ok"] is False,
            }
        )

    if isinstance(result, str):
        content: list[TextContent | ImageContent] = [TextContent(type="text", text=result)]
        try:
            decoded = json.loads(result)
        except json.JSONDecodeError:
            decoded = result
        envelope = _structured_envelope(decoded, default_ok=True)
    else:
        content = list(result)
        envelope = _parse_text_envelope(content) or {"ok": True}

    return CallToolResult(
        content=content,
        structured_content=envelope,
        is_error=envelope["ok"] is False,
    )


def wire_handler(handler: BusinessTool) -> WireTool:
    """Wrap a business handler with the SDK v2 structured-output annotation."""

    async def wrapped(*args: Any, **kwargs: Any) -> CallToolResult:
        return to_call_tool_result(await handler(*args, **kwargs))

    update_wrapper(wrapped, handler)
    signature = inspect.signature(handler, eval_str=True)
    wrapped.__signature__ = signature.replace(return_annotation=WireToolResult)  # type: ignore[attr-defined]
    wrapped.__annotations__ = dict(handler.__annotations__)
    wrapped.__annotations__["return"] = WireToolResult
    return wrapped


def register_tool(server: Any, spec: ToolSpec) -> WireTool:
    """Register one spec on an MCPServer or a decorator-compatible test double."""

    handler = wire_handler(spec.handler)
    annotations = ToolAnnotations(title=spec.title, readOnlyHint=spec.read_only)

    if hasattr(server, "add_tool"):
        server.add_tool(
            handler,
            name=spec.tool_name,
            annotations=annotations,
            structured_output=True,
        )
    else:
        server.tool(
            name=spec.tool_name,
            annotations=annotations,
            structured_output=True,
        )(handler)
    return handler


def register_tools(server: Any, specs: Sequence[ToolSpec]) -> None:
    """Register a complete declarative tool catalog."""

    for spec in specs:
        register_tool(server, spec)


def create_server(*, version: str, tools: Sequence[ToolSpec]) -> MCPServer:
    """Build the public MCP server from identity, version, and tool specs."""

    server = MCPServer(SERVER_NAME, version=version)
    register_tools(server, tools)
    return server
