"""Unit contracts for the MCP wire adapter."""

from __future__ import annotations

import json

from mcp.types import CallToolResult, ImageContent, TextContent

from t20_mcp.mcp_runtime import to_call_tool_result


def test_json_success_becomes_structured_complete_result() -> None:
    text = json.dumps({"ok": True, "payload": {"handle": "2A"}})

    result = to_call_tool_result(text)

    assert result.result_type == "complete"
    assert result.is_error is False
    assert result.structured_content == {"ok": True, "payload": {"handle": "2A"}}
    assert result.content == [TextContent(type="text", text=text)]


def test_json_failure_sets_mcp_execution_error() -> None:
    text = json.dumps({"ok": False, "error": "bad input", "hint": "fix it"})

    result = to_call_tool_result(text)

    assert result.is_error is True
    assert result.structured_content == {
        "ok": False,
        "error": "bad input",
        "hint": "fix it",
    }
    assert result.content[0].text == text


def test_image_content_is_preserved_while_text_drives_structured_output() -> None:
    content = [
        TextContent(type="text", text='{"ok":true,"screenshot":"attached"}'),
        ImageContent(type="image", data="cG5n", mime_type="image/png"),
    ]

    result = to_call_tool_result(content)

    assert result.content == content
    assert result.structured_content == {"ok": True, "screenshot": "attached"}
    assert result.is_error is False


def test_existing_call_tool_result_keeps_explicit_error_state() -> None:
    existing = CallToolResult(
        content=[TextContent(type="text", text='{"ok":true}')],
        is_error=True,
    )

    result = to_call_tool_result(existing)

    assert result.is_error is True
    assert result.structured_content == {"ok": False}
