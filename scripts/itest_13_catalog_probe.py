"""真机联调 Step 13 — 官方命令表全量注册探测, 生成 docs/T20_OFFICIAL_COMMANDS.md.

数据源: 安装目录官方命令表 SYS\\tchcmd.txt (项目内 UTF-8 副本
docs/t20_official_commands.txt, 格式: 中文名 命令名)。对每条命令在真机
getcname 探测注册状态, 输出带验证列的 Markdown 总表。

用法: uv run python scripts/itest_13_catalog_probe.py
"""

from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude

ROOT = Path(__file__).resolve().parent.parent
SRC_TXT = ROOT / "docs" / "t20_official_commands.txt"
OUT_MD = ROOT / "docs" / "T20_OFFICIAL_COMMANDS.md"

PROBE = """
(setq t20mcp:proberes "")
(foreach c (list {NAMES})
  (setq t20mcp:proberes
        (strcat t20mcp:proberes c "=" (if (t20mcp:cmd-known-p c) "1" "0") ";")))
t20mcp:proberes
"""


def parse_table() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in SRC_TXT.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        # 个别行中文名含空格 (如 "门 窗 库 TOpeningLib"): 命令名取末 token。
        if len(parts) >= 2:
            rows.append((" ".join(parts[:-1]), parts[-1]))
    return rows


async def main() -> int:
    rows = parse_table()
    commands = sorted({cmd.upper() for _, cmd in rows})
    print(f"官方表条目: {len(rows)}, 去重命令: {len(commands)}")

    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    registered: dict[str, bool] = {}
    chunk = 80
    for i in range(0, len(commands), chunk):
        batch = commands[i:i + chunk]
        names = " ".join(f'"{c}"' for c in batch)
        r = await backend.execute_lisp(_load_prelude() + "\n" + PROBE.replace("{NAMES}", names))
        if not r.ok:
            print(f"  批次 {i // chunk + 1} 探测失败: {r.error}")
            continue
        for pair in str(r.payload).split(";"):
            if "=" in pair:
                name, flag = pair.rsplit("=", 1)
                registered[name] = flag == "1"
        print(f"  批次 {i // chunk + 1}/{(len(commands) + chunk - 1) // chunk} 完成")

    hit = sum(registered.values())
    print(f"注册命中: {hit}/{len(registered)}")

    today = datetime.date.today().isoformat()
    lines = [
        "# T20 官方命令总表 (真机注册状态)",
        "",
        f"> 来源: 本机安装目录 `C:\\Tangent\\TArchT20V10\\SYS\\tchcmd.txt` (官方命令表, "
        f"原始 GBK 副本转 UTF-8 于 `docs/t20_official_commands.txt`)。",
        f"> 注册列: {today} 在 T20 V10 / AutoCAD 2024 真机经 `getcname` 探测。",
        "> ✓ = 命令表已注册; ✗ = 未注册 (可能为延迟加载的 ARX 模块或菜单宏, 不代表不存在)。",
        "> 交互序列与可驱动性仍以 `docs/T20_COMMANDS.md` 的逐条真机验证为准。",
        "",
        "| 中文命令名 | 命令名 | 注册 |",
        "|---|---|---|",
    ]
    for zh, cmd in rows:
        mark = "✓" if registered.get(cmd.upper()) else "✗"
        lines.append(f"| {zh} | `{cmd}` | {mark} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写出 {OUT_MD} ({len(rows)} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
