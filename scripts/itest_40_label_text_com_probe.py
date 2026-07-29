"""真机联调 Step 40 — drawing_name / arrow / elevation 文本 COM 注入评估 (B2).

目标 (TODO_BACKLOG B2, 二选一结案):
    三个标注类子命令的文字/样式当前走天正面板记忆值, 不可参数化。本探针
    逐命令回答: 生成的 TCH_DRAWINGNAME / TCH_ARROW / TCH_ELEVATION 是否
    暴露可写的 COM 文本属性 (或 DXF 字符串组可 entmod)?
        - 任一路径写入且读回匹配  -> 可注入 (后续增强参数)
        - 全部 vl-catch-all-error -> 该命令落 S-4 级 (面板锁死, 永久 STOPPED)

方法 (三段式, 全部 try/finally 保护):
    A. 创建实体 (走 generate_lisp 已验证模板), 校验 delta=+1 + 类型;
       LOGFILEMODE=1 捕获 vlax-dump-object 全量属性/方法到日志文件,
       同机 Python 直接读日志 (GBK), 解析 RW 属性清单; 另抓 entget 字符串组。
    B. COM put/get 探针: 对 RW 属性逐个 vlax-put-property 测试值 ->
       读回比对 -> 恢复原值。字符串属性写 "T20MCP-B2", 数值属性写 123.0。
    C. DXF 探针 (COM 无字符串命中时才有决定性意义, 但恒执行以留证据):
       对 entget 中的字符串组 (1/2/3/4/300..309) 逐个 entmod -> 读回 ->
       恢复。custom entity 大概率拒绝 entmod, 拒绝本身即证据。

cleanup 铁律 (P0):
    无论 PASS/FAIL/异常, 撤回本轮实体到 baseline, CMDACTIVE 拉 0, 复位
    CMDDIA=1 / FILEDIA=1 / OSMODE=0 / LOGFILEMODE=0。所有探针写入都在
    LISP 内就地恢复原值, undo 只负责实体删除。

用法:
    uv run python scripts/itest_40_label_text_com_probe.py drawing_name
    uv run python scripts/itest_40_label_text_com_probe.py arrow
    uv run python scripts/itest_40_label_text_com_probe.py elevation
    uv run python scripts/itest_40_label_text_com_probe.py all
    uv run python scripts/itest_40_label_text_com_probe.py inject
        — E2E 验证 generate_lisp 新增文本参数 (name_text/scale_text,
          text/text2, text) 的真机注入 + COM 读回精确匹配 (含中文 GBK 往返)。

返回码: 0=探针完成且得出明确结论 (可注入/不可注入都算), 2=基建失败/cleanup 不干净
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import generate_lisp  # noqa: E402

MODES: dict[str, dict] = {
    "drawing_name": {
        "params": {"ins_x": 5000.0, "ins_y": 5000.0},
        "etype": "TCH_DRAWINGNAME",
    },
    "arrow": {
        "params": {"x1": 0.0, "y1": 0.0, "x2": 2000.0, "y2": 1000.0},
        "etype": "TCH_ARROW",
    },
    "elevation": {
        "params": {"base_x": 0.0, "base_y": 0.0, "label_x": 1000.0, "label_y": 1000.0},
        "etype": "TCH_ELEVATION",
    },
}

TEST_STR = "T20MCP-B2"

# inject 模式: generate_lisp 文本参数 -> 期望 COM 属性值 (含中文验证 GBK 全链路)。
INJECT_CASES: dict[str, dict] = {
    "drawing_name": {
        "params": {
            "ins_x": 5000.0,
            "ins_y": 5000.0,
            "name_text": "一层平面图",
            "scale_text": "1:50",
        },
        "expect": {"NameText": "一层平面图", "ScaleText": "1:50"},
    },
    "arrow": {
        "params": {
            "x1": 0.0,
            "y1": 0.0,
            "x2": 2000.0,
            "y2": 1000.0,
            "text": "做法见详图",
            "text2": "1:20",
        },
        "expect": {"Text": "做法见详图", "Text2": "1:20"},
    },
    "elevation": {
        "params": {
            "base_x": 0.0,
            "base_y": 0.0,
            "label_x": 1000.0,
            "label_y": 1000.0,
            "text": "3.000",
        },
        "expect": {"Text": "3.000"},
    },
}

# 退出活动命令 + 复位环境 (对齐 itest_35, 追加 LOGFILEMODE=0)。
RESET_ENV = (
    "(progn (setq n 0)"
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (setvar "LOGFILEMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)

ENV_VARS = ["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE", "LOGFILEMODE"]

# 阶段 A: 记 handle -> LOGFILE 捕获 vlax-dump-object (含方法) -> 关日志。
# LOGFILENAME 必须在 mode=1 且已有输出后读取, 否则可能为空。
DUMP_LISP = """
(vl-load-com)
(setq t20mcp:b2-h (cdr (assoc 5 (entget (entlast)))))
(setq t20mcp:b2-o (vlax-ename->vla-object (entlast)))
(setvar "LOGFILEMODE" 1)
(vl-catch-all-apply 'vlax-dump-object (list t20mcp:b2-o T))
(setq t20mcp:b2-log (getvar "LOGFILENAME"))
(setvar "LOGFILEMODE" 0)
(strcat "handle=" t20mcp:b2-h " log=" t20mcp:b2-log)
"""

# 阶段 A 补充: entget 字符串组快照 (探 DXF 文本落点)。
ENTGET_STR_LISP = """
(setq t20mcp:b2-strs "")
(foreach t20mcp:b2-p (entget (entlast))
  (if (= (type (cdr t20mcp:b2-p)) 'STR)
      (setq t20mcp:b2-strs
            (strcat t20mcp:b2-strs " (" (itoa (car t20mcp:b2-p)) " . "
                    (vl-prin1-to-string (cdr t20mcp:b2-p)) ")"))))
(strcat "dxf-strs:" t20mcp:b2-strs)
"""

# dump 的属性行: ";   Name (RO) = value" / ";   Name = value"
PROP_RE = re.compile(r"^;\s+(\w+)(\s+\(RO\))?\s+=\s+(.*)$")

# AcadEntity 标准 RW 属性, 与天正文本无关, 不探 (省时 + 避免 Layer 等噪声报错)。
STD_PROP_SKIP = frozenset(
    {
        "Layer",
        "Linetype",
        "LinetypeScale",
        "Lineweight",
        "Material",
        "PlotStyleName",
        "TrueColor",
        "Visible",
        "EntityTransparency",
        "Color",
        "Normal",
        "Thickness",
        "Hyperlinks",
    }
)

# dump 解析失败时的后备候选 (常见天正/文字属性名, 全按字符串探)。
FALLBACK_PROPS: list[tuple[str, str]] = [
    ("Text", "str"),
    ("TextString", "str"),
    ("Contents", "str"),
    ("NoteText", "str"),
    ("Word", "str"),
    ("Name", "str"),
    ("DrawingName", "str"),
    ("Title", "str"),
    ("UpText", "str"),
    ("DownText", "str"),
    ("TextStyle", "str"),
    ("Style", "str"),
    ("Scale", "num"),
    ("Ratio", "num"),
    ("TextHeight", "num"),
]

# 文本语义相关的属性名特征 (用于结论分级)。
TEXTY_RE = re.compile(r"text|name|content|note|word|title|caption|string", re.I)

# 每轮 IPC 探针的属性数上限 (payload 体积保护)。
PROBE_BATCH = 8


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def _reset_env(backend: FileIPCBackend) -> None:
    r = await backend.execute_lisp(RESET_ENV)
    if not r.ok:
        print(f"[reset] FAIL: {r.error}")


async def _cleanup(backend: FileIPCBackend, base: int) -> bool:
    """撤实体回 baseline + 复位五环境变量; 任一不满足即 cleanup FAIL。"""
    rounds = 0
    while rounds < 16:
        c = await count(backend)
        if c <= base or c < 0:
            break
        u = await backend.undo()
        if not u.ok:
            print(f"[cleanup] undo fail: {u.error}")
            break
        rounds += 1
    final = await count(backend)
    await _reset_env(backend)
    env = await backend.drawing_get_variables(ENV_VARS)
    print(f"[cleanup] rounds={rounds} final={final} (baseline {base}) env={env.payload}")
    return (
        final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
        and env.payload.get("LOGFILEMODE") == 0
    )


def _parse_dump(log_path: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """解析日志中最后一段 vlax-dump-object 输出。

    返回 (props, dump_lines): props 为 (name, ro|rw, value_repr) 列表,
    dump_lines 为原始 dump 文本 (证据用)。日志读不到返回空。"""
    p = Path(log_path)
    if not log_path or not p.exists():
        return [], []
    text = p.read_text(encoding="gbk", errors="replace")
    # 取最后一次属性段起的段落 (日志可能含多次 dump)。
    # 中文版 AutoCAD 的 dump 段落标记是本地化的 ";特性值:" / ";支持的方法:"。
    idx = max(text.rfind("Property values:"), text.rfind("特性值:"))
    if idx < 0:
        return [], []
    seg = text[text.rfind("\n; ", 0, idx) + 1 if idx else 0 :]
    props: list[tuple[str, str, str]] = []
    dump_lines: list[str] = []
    for line in seg.splitlines():
        if not line.startswith(";"):
            continue
        dump_lines.append(line)
        m = PROP_RE.match(line)
        if m:
            props.append((m.group(1), "ro" if m.group(2) else "rw", m.group(3).strip()))
    return props, dump_lines


def _pick_probes(props: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """从 dump 属性中选 RW 探针对象: 字符串值按 str 探, 数值按 num 探。

    文本语义相关的排前面; 上限 2*PROBE_BATCH 个。"""
    cand: list[tuple[str, str]] = []
    for name, rw, val in props:
        if rw != "rw" or name in STD_PROP_SKIP:
            continue
        if val.startswith('"'):
            cand.append((name, "str"))
        elif re.match(r"^-?[\d.]+(e[+-]?\d+)?$", val, re.I):
            cand.append((name, "num"))
        # VLA-OBJECT / variant 值不探 (无文本注入意义)
    cand.sort(key=lambda t: (0 if TEXTY_RE.search(t[0]) else 1, t[0]))
    return cand[: PROBE_BATCH * 2]


def _prop_probe_lisp(handle: str, probes: list[tuple[str, str]]) -> str:
    """生成一轮 COM put/get/restore 直线式探针 LISP (结尾返回汇总串)。"""
    lines = [
        "(vl-load-com)",
        f'(setq t20mcp:b2-o (vlax-ename->vla-object (handent "{handle}")) t20mcp:b2-out "")',
    ]
    for name, kind in probes:
        test = f'"{TEST_STR}"' if kind == "str" else "123.0"
        lines += [
            f"(setq t20mcp:b2-old (vl-catch-all-apply 'vlax-get-property"
            f' (list t20mcp:b2-o "{name}")))',
            f"(setq t20mcp:b2-put (vl-catch-all-apply 'vlax-put-property"
            f' (list t20mcp:b2-o "{name}" {test})))',
            f"(setq t20mcp:b2-new (vl-catch-all-apply 'vlax-get-property"
            f' (list t20mcp:b2-o "{name}")))',
            # 恢复原值 (put 成功且 old 可读时)
            "(if (and (not (vl-catch-all-error-p t20mcp:b2-put))"
            " (not (vl-catch-all-error-p t20mcp:b2-old)))"
            f" (vl-catch-all-apply 'vlax-put-property"
            f' (list t20mcp:b2-o "{name}" t20mcp:b2-old)))',
            f'(setq t20mcp:b2-out (strcat t20mcp:b2-out "|{name}:'
            ' old=" (vl-prin1-to-string t20mcp:b2-old)'
            ' " put=" (if (vl-catch-all-error-p t20mcp:b2-put) "ERR" "OK")'
            ' " new=" (vl-prin1-to-string t20mcp:b2-new)))',
        ]
    lines.append("t20mcp:b2-out")
    return "\n".join(lines)


def _dxf_probe_lisp(handle: str, codes: list[int]) -> str:
    """生成 DXF 字符串组 entmod 探针 LISP (改 -> 读回 -> 恢复)。"""
    lines = [
        f'(setq t20mcp:b2-e (handent "{handle}") t20mcp:b2-out "")',
    ]
    for c in codes:
        lines += [
            "(setq t20mcp:b2-l (entget t20mcp:b2-e))",
            f"(setq t20mcp:b2-old (cdr (assoc {c} t20mcp:b2-l)))",
            f"(setq t20mcp:b2-r (vl-catch-all-apply 'entmod"
            f' (list (subst (cons {c} "{TEST_STR}") (assoc {c} t20mcp:b2-l)'
            " t20mcp:b2-l))))",
            f"(setq t20mcp:b2-new (cdr (assoc {c} (entget t20mcp:b2-e))))",
            # 写进去了才需要恢复
            f'(if (equal t20mcp:b2-new "{TEST_STR}")'
            f" (vl-catch-all-apply 'entmod"
            f" (list (subst (cons {c} t20mcp:b2-old)"
            f" (assoc {c} (entget t20mcp:b2-e)) (entget t20mcp:b2-e)))))",
            "(vl-catch-all-apply 'entupd (list t20mcp:b2-e))",
            f'(setq t20mcp:b2-out (strcat t20mcp:b2-out "|dxf{c}:'
            ' old=" (vl-prin1-to-string t20mcp:b2-old)'
            ' " mod=" (if (vl-catch-all-error-p t20mcp:b2-r) "ERR"'
            ' (if t20mcp:b2-r "OK" "NIL"))'
            ' " new=" (vl-prin1-to-string t20mcp:b2-new)))',
        ]
    lines.append("t20mcp:b2-out")
    return "\n".join(lines)


def _hits(payload: str) -> list[str]:
    """从探针汇总串中挑出写入成功且读回=测试值 的命中项名。

    字符串探针命中 new="T20MCP-B2"; 数值探针命中 new=123.0。
    put=OK 但读回未变的属性视为静默失败, 不计命中。"""
    out = []
    for item in payload.split("|"):
        if not item.strip() or "put=OK" not in item:
            continue
        name = item.split(":", 1)[0].strip()
        if f'new="{TEST_STR}"' in item or re.search(r"new=123\.0\b", item):
            out.append(name)
    return out


async def probe_mode(backend: FileIPCBackend, mode: str) -> tuple[bool, str]:
    """单命令探针。返回 (探针是否完成, 结论行)。cleanup 由内部 finally 保证。"""
    spec = MODES[mode]
    base = await count(backend)
    print(f"\n===== [{mode}] baseline={base} =====")
    verdict = "INCOMPLETE"
    done = False
    try:
        # A1: 创建实体
        code = generate_lisp(mode, dict(spec["params"]))
        r = await backend.execute_lisp(code)
        after = await count(backend)
        print(f"[create] ok={r.ok} payload={r.payload!r} count {base}->{after}")
        if after != base + 1:
            return False, f"{mode}: FAIL 实体未创建 (delta={after - base})"

        # A2: dump 捕获
        d = await backend.execute_lisp(DUMP_LISP)
        print(f"[dump] ok={d.ok} payload={d.payload!r}")
        if not d.ok or "handle=" not in str(d.payload):
            return False, f"{mode}: FAIL dump round-trip 失败"
        m = re.search(r"handle=(\S+)\s+log=(.*)$", str(d.payload))
        handle, log_path = m.group(1), m.group(2).strip()
        etype_ok = spec["etype"]  # 类型由模板内部校验 (t20mcp:fail 会报), 此处记录

        props, dump_lines = _parse_dump(log_path)
        if dump_lines:
            print(f"[dump-raw] ({len(dump_lines)} 行, log={log_path})")
            for ln in dump_lines:
                print("  " + ln)
        else:
            print(f"[dump-raw] 日志解析为空 (log={log_path!r}), 转后备候选名单")

        # A3: entget 字符串组
        eg = await backend.execute_lisp(ENTGET_STR_LISP)
        print(f"[entget-strs] {eg.payload!r}")
        dxf_codes = sorted(
            {
                int(c)
                for c in re.findall(r"\((\d+) \. ", str(eg.payload or ""))
                if int(c) in (1, 2, 3, 4) or 300 <= int(c) <= 309
            }
        )

        # B: COM put/get 探针 (分批)
        probes = _pick_probes(props) if props else list(FALLBACK_PROPS)
        src = "dump" if props else "fallback"
        print(f"[com-probe] {src} 候选 {len(probes)}: {[p[0] for p in probes]}")
        com_payload = ""
        for i in range(0, len(probes), PROBE_BATCH):
            batch = probes[i : i + PROBE_BATCH]
            pr = await backend.execute_lisp(_prop_probe_lisp(handle, batch))
            print(f"[com-probe {i // PROBE_BATCH + 1}] ok={pr.ok} {pr.payload!r}")
            com_payload += str(pr.payload or "")
        com_hits = _hits(com_payload)

        # C: DXF entmod 探针
        dxf_hits: list[str] = []
        if dxf_codes:
            dr = await backend.execute_lisp(_dxf_probe_lisp(handle, dxf_codes))
            print(f"[dxf-probe] codes={dxf_codes} ok={dr.ok} {dr.payload!r}")
            dxf_hits = _hits(str(dr.payload or ""))
        else:
            print("[dxf-probe] 无字符串组可探 (仅 0/100 类结构组)")

        # 结论
        texty = [h for h in com_hits if TEXTY_RE.search(h)]
        if texty:
            verdict = f"{mode}: INJECTABLE-COM 文本属性可写 {texty} (全部命中 {com_hits})"
        elif dxf_hits:
            verdict = f"{mode}: INJECTABLE-DXF 字符串组可 entmod {dxf_hits} (COM 命中 {com_hits})"
        elif com_hits:
            verdict = f"{mode}: PARTIAL 非文本属性可写 {com_hits}, 文本仍锁死 -> 文字落 S-4"
        else:
            verdict = f"{mode}: NOT-INJECTABLE COM/DXF 全败 -> 落 S-4 永久 STOPPED"
        print(f"[verdict] {verdict} (etype 预期 {etype_ok})")
        done = True
    finally:
        clean = await _cleanup(backend, base)
        print(f"[{mode}] cleanup clean: {'PASS' if clean else 'FAIL'}")
        if not clean:
            done = False
            verdict += " [cleanup FAIL]"
    return done, verdict


def _get_props_lisp(props: list[str]) -> str:
    """生成 entlast 的 COM 属性读回 LISP (返回 "|Prop=repr" 汇总串)。"""
    lines = [
        "(vl-load-com)",
        '(setq t20mcp:b2-o (vlax-ename->vla-object (entlast)) t20mcp:b2-out "")',
    ]
    for name in props:
        lines.append(
            f'(setq t20mcp:b2-out (strcat t20mcp:b2-out "|{name}="'
            f" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property"
            f' (list t20mcp:b2-o "{name}")))))'
        )
    lines.append("t20mcp:b2-out")
    return "\n".join(lines)


async def inject_mode(backend: FileIPCBackend, mode: str) -> tuple[bool, str]:
    """E2E: 带文本参数创建 -> COM 读回精确匹配。返回 (PASS?, 结论行)。"""
    case = INJECT_CASES[mode]
    base = await count(backend)
    print(f"\n===== [inject {mode}] baseline={base} =====")
    ok = False
    detail = ""
    try:
        code = generate_lisp(mode, dict(case["params"]))
        r = await backend.execute_lisp(code)
        after = await count(backend)
        print(f"[create] ok={r.ok} payload={r.payload!r} count {base}->{after}")
        if after != base + 1:
            return False, f"inject {mode}: FAIL 实体未创建 (delta={after - base})"

        rb = await backend.execute_lisp(_get_props_lisp(list(case["expect"])))
        payload = str(rb.payload or "")
        print(f"[readback] ok={rb.ok} {payload!r}")
        misses = [
            f"{prop}(期望 {want!r})"
            for prop, want in case["expect"].items()
            if f'|{prop}="{want}"' not in payload
        ]
        ok = not misses
        detail = "全部精确匹配" if ok else f"未匹配: {', '.join(misses)}"
    finally:
        clean = await _cleanup(backend, base)
        print(f"[inject {mode}] cleanup clean: {'PASS' if clean else 'FAIL'}")
        ok = ok and clean
    return ok, f"inject {mode}: {'PASS' if ok else 'FAIL'} {detail}"


async def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in (*MODES, "all", "inject"):
        print(__doc__)
        return 2
    inject = sys.argv[1] == "inject"
    modes = list(MODES) if sys.argv[1] in ("all", "inject") else [sys.argv[1]]

    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 2

    # 开头清场: 残留实体撤光 + 复位环境。
    guard = 0
    while await count(backend) > 0 and guard < 8:
        await backend.undo()
        guard += 1
    await _reset_env(backend)
    print(f"start clean: entity={await count(backend)} (undo x{guard})")

    results: list[tuple[bool, str]] = []
    for mode in modes:
        if inject:
            results.append(await inject_mode(backend, mode))
        else:
            results.append(await probe_mode(backend, mode))

    print("\n=== Step40 B2 总结 ===")
    all_done = True
    for done, verdict in results:
        print(f"  [{'DONE' if done else 'FAIL'}] {verdict}")
        all_done = all_done and done
    return 0 if all_done else 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
