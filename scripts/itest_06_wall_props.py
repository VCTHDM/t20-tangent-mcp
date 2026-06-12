"""真机联调 Step 6 — TCH_WALL ActiveX 属性探测 (墙参数注入路线) + 标注实体确认.

  A. 最小序列画墙 → 逐一探测候选 VLA 属性名 (get), 命中后尝试 put 并回读验证
  B. TDIMMP [位置 p1 p2 回车] 画标注 → 确认实体类型 (期望 TCH_DIM 系)

用法: uv run python scripts/itest_06_wall_props.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude

TRIAL = """
(defun c:t20mcp-trial ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "trial"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "{CMD}" (list {ARGS}))
      (t20mcp:end "trial" t20mcp:saved)
      (t20mcp:fail "trial" t20mcp:saved "command-failed"))
  (princ))
(c:t20mcp-trial)
"""

PROP_CANDIDATES = [
    "LeftWidth", "RightWidth", "Width", "Height", "Elevation",
    "Length", "Style", "WallType", "Usage", "Material",
    "StartPoint", "EndPoint", "Insulate", "InsuThick", "HighEdge",
]

PROBE_GET = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach p (list {PROPS})
  (setq t20mcp:v (vl-catch-all-apply 'vlax-get-property (list t20mcp:obj p)))
  (setq t20mcp:r
        (strcat t20mcp:r p "="
                (if (vl-catch-all-error-p t20mcp:v)
                    "<no>"
                    (vl-princ-to-string (if (= (type t20mcp:v) 'VARIANT)
                                            (vlax-variant-value t20mcp:v)
                                            t20mcp:v)))
                ";")))
t20mcp:r
"""

PROBE_PUT = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach pv (list {PAIRS})
  (setq t20mcp:e (vl-catch-all-apply 'vlax-put-property
                                     (list t20mcp:obj (car pv) (cdr pv))))
  (setq t20mcp:r (strcat t20mcp:r (car pv) "->"
                         (if (vl-catch-all-error-p t20mcp:e) "putFAIL" "putOK") ";")))
t20mcp:r
"""

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # --- A: 画墙 + 属性探测 ---
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", "TGWALL").replace(
        "{ARGS}", '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    await backend.execute_lisp(code)

    props = " ".join(f'"{p}"' for p in PROP_CANDIDATES)
    got = await backend.execute_lisp(PROBE_GET.replace("{PROPS}", props))
    print(f"[A1 get 探测] {got.payload if got.ok else got.error}")

    pairs = '(cons "LeftWidth" 240.0) (cons "RightWidth" 120.0) (cons "Height" 3300.0)'
    put = await backend.execute_lisp(PROBE_PUT.replace("{PAIRS}", pairs))
    print(f"[A2 put 试写] {put.payload if put.ok else put.error}")

    verify = await backend.execute_lisp(
        PROBE_GET.replace("{PROPS}", '"LeftWidth" "RightWidth" "Height"'))
    print(f"[A3 回读验证] {verify.payload if verify.ok else verify.error}")
    await backend.undo()

    # --- B: TDIMMP 实体类型确认 ---
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", "TDIMMP").replace(
        "{ARGS}", '(t20mcp:pt 1500 1000) (t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    await backend.execute_lisp(code)
    dim_type = await backend.execute_lisp(LAST_TYPE)
    print(f"[B 标注实体类型] {dim_type.payload!r}")
    await backend.undo()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
