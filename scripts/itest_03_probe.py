"""真机联调 Step 3 — T20 命令名探测 (P1-4 编目回填依据).

对 docs/T20_COMMANDS.md 中的候选别名逐一 getcname 探测, 并扫描 atoms-family
中 C:T* 形式的 LISP 命令, 输出真机上确实存在的命令名。

用法: uv run python scripts/itest_03_probe.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude

# 目标功能 -> 候选命令名 (编目推测 + 天正历史版本惯用 T8x_/T9x_ 前缀)
CANDIDATES: dict[str, list[str]] = {
    "wall(绘制墙体)": [
        "TGWALL", "HZQT", "TWALL", "DRAWWALL", "TDRAWWALL",
        "T81_TDRAWWALL", "T91_TDRAWWALL", "T96_TDRAWWALL", "T98_TDRAWWALL", "T20_TDRAWWALL",
        "绘制墙体",
    ],
    "axis_grid(绘制轴网)": [
        "HZZW", "TGAXISGRID", "TAXISGRID", "TRECTAXIS",
        "T81_TAXISGRID", "T96_TAXISGRID", "T98_TAXISGRID",
        "绘制轴网",
    ],
    "door/window(门窗)": [
        "MC", "TOPENING", "TGOPENING", "TDOOR", "TWINDOW",
        "T81_TOPENING", "T96_TOPENING", "T98_TOPENING",
        "门窗",
    ],
    "dimension(逐点标注)": [
        "ZDBZ", "TDIM", "TDIMMP", "TLINEARDIM", "TDIMENSION",
        "T81_TDIMMP", "T96_TDIMMP", "T98_TDIMMP",
        "逐点标注",
    ],
    "export_t3(图形导出)": [
        "T20_EXPORT", "TEXPORT", "TSAVEAS", "LJZH",
        "T81_TSAVEAS", "T96_TSAVEAS", "T98_TSAVEAS",
        "图形导出",
    ],
    "texplode(分解对象)": [
        "TEXPLODE", "FJDX", "T81_TEXPLODE", "T96_TEXPLODE", "T98_TEXPLODE",
        "分解对象",
    ],
}


def build_probe_lisp(names: list[str]) -> str:
    quoted = " ".join(f'"{n}"' for n in names)
    return (
        _load_prelude()
        + "\n"
        + "(setq t20mcp:proberes \"\")\n"
        + f"(foreach c (list {quoted})\n"
        + "  (setq t20mcp:proberes\n"
        + "        (strcat t20mcp:proberes c \"=\" (if (t20mcp:cmd-known-p c) \"1\" \"0\") \";\")))\n"
        + "t20mcp:proberes\n"
    )


ATOMS_SCAN = """
(setq t20mcp:atomres "")
(foreach a (atoms-family 1)
  (if (and (wcmatch a "C:T*") (< (strlen t20mcp:atomres) 3500))
      (setq t20mcp:atomres (strcat t20mcp:atomres (substr a 3) ";"))))
t20mcp:atomres
"""


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    found_any: dict[str, list[str]] = {}
    for group, names in CANDIDATES.items():
        result = await backend.execute_lisp(build_probe_lisp(names))
        if not result.ok:
            print(f"[{group}] 探测失败: {result.error}")
            continue
        pairs = [p for p in str(result.payload).split(";") if "=" in p]
        hits = [p.split("=")[0] for p in pairs if p.endswith("=1")]
        found_any[group] = hits
        print(f"[{group}]")
        print(f"  raw: {result.payload}")
        print(f"  命中: {hits if hits else '(无)'}")

    scan = await backend.execute_lisp(_load_prelude() + "\n" + ATOMS_SCAN)
    print("\n[atoms-family C:T* 扫描 (前3500字符)]")
    print(f"  {scan.payload if scan.ok else scan.error}")

    print("\n=== Step3 汇总 ===")
    for group, hits in found_any.items():
        print(f"  {group}: {', '.join(hits) if hits else '未命中, 需人工在 T20 菜单里核对命令行回显'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
