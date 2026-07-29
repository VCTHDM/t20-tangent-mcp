"""MCP stdio 端到端冒烟.

启动 `python -m t20_mcp`, 通过 MCP v2 Client 自动协商协议、列工具并调用 tangent dry-run。
该脚本不接触 AutoCAD 后端, 因为 `execute=False` 不会初始化 backend。

用法: uv run python scripts/itest_19_mcp_stdio_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock

from _live_lock import live_lock_or_exit  # noqa: E402
from mcp import Client, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


async def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python_exe.is_file():
        python_exe = Path(sys.executable)

    # Windows + Chinese cwd: launching through cmd.exe is more reliable than
    # asking mcp.client.stdio to resolve uv/python directly.
    params = StdioServerParameters(
        command=r"C:\Windows\System32\cmd.exe",
        args=["/c", str(python_exe), "-m", "t20_mcp"],
        cwd=ROOT,
        env=env,
    )
    async with Client(stdio_client(params), mode="auto") as client:
        if client.protocol_version != "2026-07-28":
            print(
                f"FAIL: negotiated MCP protocol {client.protocol_version!r}, expected '2026-07-28'"
            )
            return 1
        if client.session.discover_result is None or client.session.initialize_result is not None:
            print("FAIL: modern stdio connection did not use server/discover exclusively")
            return 1
        print(f"[protocol] {client.protocol_version}")

        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        print(f"[tools] {names}")
        expected = {
            "tangent",
            "drawing",
            "entity",
            "layer",
            "block",
            "annotation",
            "pid",
            "view",
            "system",
        }
        missing = sorted(expected - set(names))
        if missing:
            print(f"FAIL: missing tools: {missing}")
            return 1

        result = await client.call_tool(
            "tangent",
            {
                "operation": "axis_lines",
                "data": {"hspacings": [3000], "vspacings": [2000]},
                "execute": False,
            },
        )
        texts = [content.text for content in result.content if content.type == "text"]
        if (
            result.result_type != "complete"
            or result.is_error
            or not texts
            or '"operation":"axis_lines"' not in texts[0]
            or '"dry_run":true' not in texts[0]
        ):
            print(f"FAIL: unexpected tangent dry-run response: {result!r}")
            return 1
        print("[tangent.axis_lines dry-run] PASS")

    async with Client(stdio_client(params), mode="legacy") as client:
        if client.protocol_version != "2025-11-25":
            print(
                f"FAIL: negotiated legacy MCP protocol {client.protocol_version!r}, "
                "expected '2025-11-25'"
            )
            return 1
        if client.session.discover_result is not None or client.session.initialize_result is None:
            print("FAIL: legacy stdio connection did not use initialize exclusively")
            return 1
        legacy_tools = await client.list_tools()
        legacy_names = {tool.name for tool in legacy_tools.tools}
        if legacy_names != expected:
            print(f"FAIL: legacy tool set mismatch: {sorted(legacy_names)!r}")
            return 1
        print(f"[legacy protocol] {client.protocol_version}")
    return 0


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
