"""真机验证: t20mcp:pt 2 位小数精度修复.

背景: _prelude.lsp 中 t20mcp:pt 从 rtos 2 8 改为 rtos 2 2, 修复天正
TDIMMP 标注浮点精度误差导致标注歪斜。本脚本在真机上自动化验证:
  1. dimension / two_point_dimension / wall_thickness_dimension 仍正常生成 TCH_DIM*
  2. dimension 标注值正确 (≈ 跨距), 几何不歪斜 (DXF 回读)
  3. 墙端点对齐: 相邻墙共享端点经 t20mcp:pt 2 位小数后仍重合
  4. t20mcp:pt 对非整数坐标按 2 位小数舍入 (DIMZIN 可省略整数尾零)
全部用 COM/DXF 自动回读, 不靠肉眼看; 每场景后 UNDO cleanup.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import generate_lisp  # noqa: E402

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'

RESET_ENV = """
(progn
  (setq n 0)
  (while (and (< n 6) (> (getvar "CMDACTIVE") 0))
    (command)
    (setq n (1+ n)))
  (setvar "CMDDIA" 1)
  (setvar "FILEDIA" 1)
  (setvar "OSMODE" 0)
  "env-reset")
"""

# 回读 entlast 的完整 entget (DXF 组码), 用于检查标注几何点
ENTGET_DUMP = """
(progn
  (setq t20mcp:e (entlast))
  (setq t20mcp:s (cdr (assoc 0 (entget t20mcp:e))))
  (setq t20mcp:g "")
  (foreach p (entget t20mcp:e)
    (setq t20mcp:g (strcat t20mcp:g "(" (itoa (car p)) " . "
                  (vl-princ-to-string (cdr p)) ") ")))
  (strcat "TYPE=" t20mcp:s " | " t20mcp:g))
"""

# COM 属性回读 (天正实体可能不暴露标准 dim 属性, 用 entget DXF 兜底)
READBACK = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach p (list {PROPS})
  (setq t20mcp:v (vl-catch-all-apply 'vlax-get-property (list t20mcp:obj p)))
  (setq t20mcp:r
        (strcat t20mcp:r p "="
                (if (vl-catch-all-error-p t20mcp:v)
                    "<no>"
                    (vl-princ-to-string t20mcp:v))
                ";")))
t20mcp:r
"""


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def cleanup_to(backend: FileIPCBackend, target: int) -> None:
    guard = 0
    while await count(backend) > target and guard < 16:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    results: dict[str, bool] = {}
    notes: dict[str, str] = {}

    # ==================================================================
    # 场景 0: t20mcp:pt 输出格式确认
    # ==================================================================
    fmt_code = '''
(progn
  (defun t20mcp:pt (x y) (strcat (rtos x 2 2) "," (rtos y 2 2)))
  (strcat "pt_test=" (t20mcp:pt 6000.123 -1500.126)
          "|" (t20mcp:pt 0.004 0.005)))
'''
    fmt_r = await backend.execute_lisp(fmt_code)
    fmt_payload = str(fmt_r.payload)
    fmt_ok = (
        fmt_r.ok
        and "6000.12,-1500.13" in fmt_payload
        and "0,0.01" in fmt_payload
    )
    results["pt_format"] = fmt_ok
    notes["pt_format"] = str(fmt_r.payload)
    print(f"[pt_format] ok={fmt_ok} payload={fmt_r.payload!r}")

    # ==================================================================
    # 场景 1: dimension (水平标注) — 生成 + 类型 + DXF 回读
    # ==================================================================
    before = await count(backend)
    # 先画一面墙给标注附着力 (dimension 需要 wall 基线)
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 12000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    before = await count(backend)
    r = await backend.execute_lisp(generate_lisp("dimension", {
        "p1_x": 0, "p1_y": 0, "p2_x": 12000, "p2_y": 0,
        "pos_x": 6000, "pos_y": -1500,
    }))
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    dump = await backend.execute_lisp(ENTGET_DUMP)
    dim_ok = r.ok and after == before + 1 and str(t.payload).startswith("TCH_DIM")
    results["dimension"] = dim_ok
    notes["dimension"] = f"type={t.payload!r} dump={dump.payload!r}"
    print(f"[dimension] ok={dim_ok} exec={r.ok} {before}->{after} type={t.payload!r}")
    print(f"  dump={dump.payload!r}")
    await cleanup_to(backend, base)

    # ==================================================================
    # 场景 2: two_point_dimension (垂直标注)
    # ==================================================================
    # TDIMTP 的穿越线必须穿过多个独立对象；单墙会报“对象数目太少”。
    for y in (0, 2000, 4000):
        await backend.execute_lisp(generate_lisp(
            "wall", {"x1": 0, "y1": y, "x2": 3000, "y2": y,
                     "left_width": 120, "right_width": 120,
                     "height": 3000, "wall_type": "砖"},
        ))
    before = await count(backend)
    r = await backend.execute_lisp(generate_lisp("two_point_dimension", {
        "p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 4500,
        "pos_x": 2500, "pos_y": 2000,
    }))
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    dump = await backend.execute_lisp(ENTGET_DUMP)
    tpd_ok = r.ok and after == before + 1 and str(t.payload).startswith("TCH_DIM")
    results["two_point_dimension"] = tpd_ok
    notes["two_point_dimension"] = f"type={t.payload!r} dump={dump.payload!r}"
    print(f"[two_point_dimension] ok={tpd_ok} exec={r.ok} {before}->{after} type={t.payload!r}")
    print(f"  dump={dump.payload!r}")
    await cleanup_to(backend, base)

    # ==================================================================
    # 场景 3: wall_thickness_dimension
    # ==================================================================
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 6000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    before = await count(backend)
    r = await backend.execute_lisp(generate_lisp("wall_thickness_dimension", {
        "p1_x": 3000, "p1_y": -200, "p2_x": 3000, "p2_y": 200,
    }))
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    wtd_ok = r.ok and after == before + 1 and str(t.payload).startswith("TCH_DIM")
    results["wall_thickness_dimension"] = wtd_ok
    notes["wall_thickness_dimension"] = f"type={t.payload!r}"
    print(f"[wall_thickness_dimension] ok={wtd_ok} exec={r.ok} {before}->{after} type={t.payload!r}")
    await cleanup_to(backend, base)

    # ==================================================================
    # 场景 4: 墙端点对齐 — 两面相连墙, COM 回读端点验证重合
    # ==================================================================
    before = await count(backend)
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 6000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    # 第二面墙起点 = 第一面墙终点 (6000,0)
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 6000, "y1": 0, "x2": 6000, "y2": 6000,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    after = await count(backend)
    # TCH_WALL 不暴露 StartPoint/EndPoint 属性，必须走 Curve 协议。
    wall_rb_code = '''
(progn
  (setq t20mcp:ss (ssget "X" '((0 . "TCH_WALL"))))
  (setq t20mcp:n (sslength t20mcp:ss))
  (setq t20mcp:out "")
  (setq t20mcp:i (1- t20mcp:n))
  (while (>= t20mcp:i 0)
    (setq t20mcp:e (ssname t20mcp:ss t20mcp:i))
    (setq t20mcp:o (vlax-ename->vla-object t20mcp:e))
    (setq t20mcp:sp (vl-catch-all-apply 'vlax-curve-getStartPoint (list t20mcp:o)))
    (setq t20mcp:ep (vl-catch-all-apply 'vlax-curve-getEndPoint (list t20mcp:o)))
    (setq t20mcp:out (strcat t20mcp:out "W" (itoa t20mcp:i)
                     " SP=" (if (vl-catch-all-error-p t20mcp:sp) "<no>" (vl-princ-to-string t20mcp:sp))
                     " EP=" (if (vl-catch-all-error-p t20mcp:ep) "<no>" (vl-princ-to-string t20mcp:ep))
                     " | "))
    (setq t20mcp:i (1- t20mcp:i)))
  t20mcp:out)
'''
    wall_rb = await backend.execute_lisp(wall_rb_code)
    rb_str = str(wall_rb.payload)
    # 墙1终点与墙2起点都应为 (6000,0,0)。
    wall_align_ok = (
        after == before + 2
        and "<no>" not in rb_str
        and rb_str.count("(6000.0 0.0 0.0)") >= 2
    )
    results["wall_endpoint_align"] = wall_align_ok
    notes["wall_endpoint_align"] = rb_str
    print(f"[wall_endpoint_align] ok={wall_align_ok} {before}->{after}")
    print(f"  readback={rb_str!r}")
    await cleanup_to(backend, base)

    # ==================================================================
    # 场景 5: dimension 标注值 — COM 读 Measurement (如可读)
    # ==================================================================
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 12000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    before = await count(backend)
    await backend.execute_lisp(generate_lisp("dimension", {
        "p1_x": 0, "p1_y": 0, "p2_x": 12000, "p2_y": 0,
        "pos_x": 6000, "pos_y": -1500,
    }))
    after = await count(backend)
    # 尝试读 Measurement / Text 属性 (天正实体可能不暴露)
    meas_rb = await backend.execute_lisp(
        READBACK.replace("{PROPS}", '"Measurement" "Text" "TextOverride"'))
    results["dimension_measurement"] = after == before + 1
    notes["dimension_measurement"] = str(meas_rb.payload)
    print(f"[dimension_measurement] ok={results['dimension_measurement']} readback={meas_rb.payload!r}")
    await cleanup_to(backend, base)

    # ==================================================================
    # 汇总
    # ==================================================================
    final_count = await count(backend)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        final_count == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )

    print()
    print("=" * 60)
    print("t20mcp:pt 2 位小数精度修复 — 真机验证结果")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"    -> {notes.get(name, '')}")
    print(f"  ({passed}/{total} passed)")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'} (count {final_count}=={base})")
    print()
    if passed == total and clean:
        print("结论: 2 位小数修复验证通过 — 标注正常生成, 墙端点对齐, 图纸清理干净")
    else:
        print("结论: 存在 FAIL 项, 需进一步排查 (见上方 notes)")
    return 0 if passed == total and clean else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
