"""真机联调 Step 22 — 探索: DXF 导出 + ezdxf 解码天正实体 (非破坏读回路线).

假设: TCH_* 自定义实体在 DXFOUT 输出中携带 proxy graphics (group 92/310,
受 PROXYGRAPHICS 系统变量控制), ezdxf.proxygraphic 可解码为普通几何 ——
若成立, 读回管线完全不需要破坏性的 TExplode。

流程 (UNDO 包裹, 不动用户既有实体):
1. 记录 PROXYGRAPHICS / DWGNAME 基线;
2. 建一面已验证的 TCH_WALL, 取其 handle;
3. (command "_.DXFOUT" tmp.dxf ...) 导出全图, 断言 DWGNAME 未被改名;
4. UNDO 删墙, 实体数回基线;
5. Python 侧 ezdxf 读 tmp.dxf: 按 handle 找该实体, 报告 dxftype /
   proxy graphics 有无 / 解码出的图元类型与端点。

用法: uv run python scripts/itest_22_proxy_dxf_probe.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude, generate_lisp

LAST_HANDLE = '(if (entlast) (cdr (assoc 5 (entget (entlast)))) "none")'


def dxfout_lisp(path: str) -> str:
    posix = path.replace("\\", "/")
    return (
        _load_prelude()
        + f"""
(defun c:t20mcp-dxfout ( / t20mcp:saved *error* t20mcp:rc)
  (setq t20mcp:saved (t20mcp:begin "dxfout"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:rc (t20mcp:call-nocheck "_.DXFOUT" (list "{posix}" "16")))
  (if (findfile "{posix}")
      (t20mcp:end "dxfout" t20mcp:saved)
      (t20mcp:fail "dxfout" t20mcp:saved "no-dxf-written"))
  (princ))
(c:t20mcp-dxfout)
"""
    )


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    assert result.ok, result.error
    return result.payload["count"]


def analyze_dxf(path: str, handle: str) -> bool:
    import ezdxf
    from ezdxf.proxygraphic import ProxyGraphic

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    target = None
    types: dict[str, int] = {}
    for e in msp:
        t = e.dxftype()
        types[t] = types.get(t, 0) + 1
        if (e.dxf.handle or "").upper() == handle.upper():
            target = e
    print(f"[dxf] modelspace types={types}")
    if target is None:
        print(f"[dxf] FAIL: handle {handle} not found in DXF")
        return False

    print(f"[dxf] target dxftype={target.dxftype()}")
    blob = getattr(target, "proxy_graphic", None)
    if not blob:
        # 未知实体 (DXFTagStorage): 尝试从原始 tag 中提取 92/310 proxy 数据
        try:
            from ezdxf.lldxf.tags import Tags

            raw = bytearray()
            for subclass in getattr(target, "xtags", None).subclasses:
                tags = Tags(subclass)
                for code, value in tags:
                    if code == 310:
                        raw.extend(value)
            blob = bytes(raw) if raw else None
            if blob:
                print(f"[dxf] proxy bytes from raw 310 tags: {len(blob)}")
        except Exception as exc:
            print(f"[dxf] raw-tag extraction failed: {exc}")
    else:
        print(f"[dxf] proxy_graphic attr: {len(blob)} bytes")

    if not blob:
        print("[dxf] FAIL: no proxy graphics — PROXYGRAPHICS=0 或实体不写代理图形")
        return False

    try:
        entities = list(ProxyGraphic(blob, doc).virtual_entities())
    except Exception as exc:
        print(f"[dxf] FAIL: proxy graphic decode error: {exc}")
        return False
    summary: dict[str, int] = {}
    for v in entities:
        summary[v.dxftype()] = summary.get(v.dxftype(), 0) + 1
    print(f"[dxf] decoded virtual entities: {summary}")
    sample = entities[:3]
    for v in sample:
        if v.dxftype() == "LINE":
            print(f"  LINE {tuple(v.dxf.start)} -> {tuple(v.dxf.end)}")
        elif v.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = list(v.get_points())[:4]
            except Exception:
                pts = "(n/a)"
            print(f"  {v.dxftype()} pts[:4]={pts}")
    return len(entities) > 0


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    env = await backend.drawing_get_variables(["PROXYGRAPHICS", "DWGNAME", "CMDACTIVE"])
    print(f"[baseline] {env.payload}")
    dwgname_before = env.payload.get("DWGNAME")
    before = await count(backend)

    wall = await backend.execute_lisp(
        generate_lisp(
            "wall",
            {
                "x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                "left_width": 120, "right_width": 120, "height": 3000,
                "wall_type": "砖",
            },
        )
    )
    handle_r = await backend.execute_lisp(LAST_HANDLE)
    handle = (handle_r.payload or "").strip('"') if handle_r.ok else "none"
    print(f"[wall] ok={wall.ok} handle={handle} entities {before}->{await count(backend)}")
    if not wall.ok or handle in ("none", ""):
        print("FAIL: 墙体创建失败, 停")
        return 1

    dxf_path = str(Path(tempfile.gettempdir()) / f"t20mcp_probe_{int(time.time())}.dxf")
    out = await backend.execute_lisp(dxfout_lisp(dxf_path))
    env2 = await backend.drawing_get_variables(["DWGNAME", "CMDACTIVE", "CMDDIA", "FILEDIA"])
    print(f"[dxfout] ok={out.ok} payload={out.payload!r} error={out.error!r}")
    print(f"[dxfout] DWGNAME {dwgname_before!r} -> {env2.payload.get('DWGNAME')!r}")
    renamed = env2.payload.get("DWGNAME") != dwgname_before

    # 清理: UNDO 删墙
    while await count(backend) > before:
        undo = await backend.undo()
        if not undo.ok:
            print(f"[cleanup] undo failed: {undo.error}")
            break
    reset = await backend.execute_lisp(
        '(progn (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "env-reset")'
    )
    final_env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[cleanup] entities={await count(backend)} reset={reset.ok} env={final_env.payload}")

    if renamed:
        print("FAIL: DXFOUT 改写了 DWGNAME (会话被挟持), 此路线需改用其他导出方式")
        return 1
    if not out.ok or not Path(dxf_path).exists():
        print("FAIL: DXF 未写出")
        return 1

    ok = analyze_dxf(dxf_path, handle)
    Path(dxf_path).unlink(missing_ok=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
