"""MCP stdio 端到端冒烟.

启动 `python -m t20_mcp`, 通过 MCP ClientSession 列工具, 并调用 tangent dry-run。
该脚本不接触 AutoCAD 后端, 因为 `execute=False` 不会初始化 backend。

用法: uv run python scripts/itest_19_mcp_stdio_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            print(f"[tools] {names}")
            expected = {
                "tangent", "drawing", "entity", "layer", "block",
                "annotation", "pid", "view", "system",
            }
            missing = sorted(expected - set(names))
            if missing:
                print(f"FAIL: missing tools: {missing}")
                return 1

            result = await session.call_tool(
                "tangent",
                {
                    "operation": "axis_lines",
                    "data": {"hspacings": [3000], "vspacings": [2000]},
                    "execute": False,
                },
            )
            texts = [content.text for content in result.content if content.type == "text"]
            if not texts or '"operation":"axis_lines"' not in texts[0] or '"dry_run":true' not in texts[0]:
                print(f"FAIL: unexpected tangent dry-run response: {texts!r}")
                return 1
            print("[tangent.axis_lines dry-run] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
