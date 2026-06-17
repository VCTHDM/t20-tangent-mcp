# Handoff 34 — window 模式 SillHeight 真机闭合 (D1 完结)

> 日期: 2026-06-17
> 关联: TODO_BACKLOG.md §D1, Handoff 33 附录 A (SillHeight -> DoorSill 修复)
> 状态: PASS — D1 闭合, D2 文档同步可启动

---

## 0. TL;DR

| 项 | 结果 |
|---|---|
| 真机入口 | `uv run python scripts/itest_35_opening_readback.py window` |
| Exit code | 0 (PASS) |
| 实体类型 | TCH_OPENING |
| DXF group 71 | 1 (窗模式) |
| W/H/DoorSill 注入 | 1500 / 1500 / 900 精确匹配 |
| 三组 sweep DS=600/1200/300 | 全部精确匹配 |
| cleanup | entity baseline + CMDACTIVE=0 / CMDDIA=1 / FILEDIA=1 / OSMODE=0 全绿 |

D1 任务书的闭合判据 "DS=600/1200/300 与传入 sill_height 精确匹配, group71=1"
全部满足, 不留余项。

---

## 1. 任务书还原 (摘自 TODO_BACKLOG §D1)

- 状态: BLOCKED-等用户切面板
- 前提: 用户把 "门窗" 面板手动切到窗模式 (Window) 并保留, 不要关闭
- 行动: `uv run python scripts/itest_35_opening_readback.py window`
- 闭合判据: readback 显示 DS=600/1200/300 与传入 sill_height 精确匹配, group71=1
- 背景: Handoff 33 附录 A 已修代码 (SillHeight -> DoorSill), 仅缺一份窗模式真机日志

---

## 2. 推进路径

### 2.1 第一次尝试 — 面板尚在门模式 (SKIP, 非代码回归)

```
[wall] ok=True count 0->1
[window] ok=True payload='' count 1->2 last_type='TCH_OPENING' CMDACTIVE=0
[readback] payload='type="TCH_OPENING" W=1500.0 H=1500.0 DS=900.0 SH=#<%catch-all-apply-error%>'
  [preflight] DXF group 71 = '0' (1=窗模式, 0=门模式)
  -> 面板当前在门模式, SKIP
```

按设计, 面板在门模式时 window preflight 走 SKIP(3) 路径; W/H/DS 注入本身已经
精确匹配, 仅 group71 不为窗。

### 2.2 用户切面板后第二次尝试 — 暴露 itest_35 脚本小 bug

用户把天正"门窗"面板切到"窗" Tab 后再跑, 输出:

```
  [preflight] DXF group 71 = '1' (1=窗模式, 0=门模式)
  -> 面板当前在门模式 (group71!=1), window 探针无法验证窗台高。
  overall: SKIP (window 非窗模式, 非代码回归)
Exit code 3
```

文字明明显示 group 71 = '1', 但仍判 "门模式"。

根因: backend.execute_lisp 把 LISP 标量结果以字符串形式回传, itest_35 第 213 行
的 `if g71_val != 1` 是把字符串 '1' 与整数 1 比较, 永远成立。

修复 (本次提交):

```
- if g71_val != 1:
+ # IPC payload 把 LISP 的 int 也以字符串形式回传, 1 / "1" 都视为窗模式。
+ if g71_val not in (1, "1"):
```

### 2.3 第三次尝试 — D1 真机 PASS

```
baseline entity count=0 (cleaned 0 undo)
[wall] ok=True count 0->1
[window] ok=True payload='' count 1->2 last_type='TCH_OPENING' CMDACTIVE=0
[readback] payload='type="TCH_OPENING" W=1500.0 H=1500.0 DS=900.0 SH=#<%catch-all-apply-error%>'

=== Step35 [window] verdict ===
  entity delta=+1: PASS
  type=TCH_OPENING: PASS
  expected: W=1500.0 H=1500.0 DS=900.0 SH=None
  raw readback: type="TCH_OPENING" W=1500.0 H=1500.0 DS=900.0 SH=#<%catch-all-apply-error%>
  [preflight] DXF group 71 = '1' (1=窗模式, 0=门模式)
[cleanup] rounds=2 final=0 (baseline 0) env={'CMDACTIVE': 0, 'CMDDIA': 1, 'FILEDIA': 1, 'OSMODE': 0}
  cleanup clean: PASS
Exit code 0
```

### 2.4 任务书要求的 sill_height 三参数 sweep

任务书原文: "DS=600/1200/300 与传入 sill_height 精确匹配"。单次 itest_35 只测
sh=900, 为补全证据, 用一次性探针 scripts/_probe_window_sweep.py (沿用
FileIPCBackend + tangent.generate_lisp 入口, 无新逻辑) 在同一段墙的不同 ins_x
上插 3 扇窗:

```
  [sh=600.0  w=800.0  h=1500.0  ix=1000.0] -> type="TCH_OPENING" g71=1 W=800.0  H=1500.0 DS=600.0
  [sh=1200.0 w=600.0  h=1800.0  ix=2500.0] -> type="TCH_OPENING" g71=1 W=600.0  H=1800.0 DS=1200.0
  [sh=300.0  w=1200.0 h=1500.0  ix=4000.0] -> type="TCH_OPENING" g71=1 W=1200.0 H=1500.0 DS=300.0
final=0 (baseline 0)

=== sweep summary ===
  sh=  600.0 W= 800.0 H=1500.0  -> PASS
  sh= 1200.0 W= 600.0 H=1800.0  -> PASS
  sh=  300.0 W=1200.0 H=1500.0  -> PASS
overall: PASS
```

三组 sill_height 与 readback DoorSill 一一精确匹配, group71 全为 1。

---

## 3. 与 Handoff 33 附录 A 的关系

Handoff 33 附录 A 把 opening.lsp 模板从注入 SillHeight 改为注入 DoorSill,
仅缺一份窗模式 (group71=1) 下的真机日志。本次给出的 readback:

- SH=#<%catch-all-apply-error%> — 证实 TCH_OPENING 不暴露独立的 SillHeight 属性
  (与 Handoff 33 enumeration 一致; 这是 catch-all-error, 不是数值零, 表示属性不存在)
- DS=600/900/1200/300 — 证实窗模式下 DoorSill 承载窗台高, 与传入参数精确同值

结论与 Handoff 33 推断一致: 门 / 窗共用 DoorSill 字段, 由 DXF group 71
决定语义 — group71=0 时是门槛高, group71=1 时是窗台高。tangent.window 的
sill_height 参数语义闭合。

---

## 4. 代码改动

| 文件 | 改动 |
|---|---|
| scripts/itest_35_opening_readback.py | 1 行修复 + 1 行注释 — preflight 接受字符串 '1' |
| scripts/_probe_window_sweep.py | 新增 sweep 探针 (一次性, 仅生成本份证据用) |
| docs/handoff/34_window_sillheight_close.md | 本文 |

src/t20_mcp/ 下任何 dispatcher / wrapper 代码完全没动, 离线 pytest 不需要变更。

---

## 5. 留给 D2 的待办 (后续轮次)

按 TODO_BACKLOG §D2:

1. 复核 tangent.py::LOW_CONFIDENCE_WARNINGS["window"] 文案 — 当前文案已经
   说明 "Handoff 33 已真机验证", D1 闭合后可补一句 "Handoff 34 sweep 三参数
   精确匹配" 增强可信度 (非必须, 当前文案不算错)。
2. docs/T20_COMMANDS.md 1.1 表 "门窗" 行 "window 调用前需人工把门窗面板
   切到窗模式" 不变 (这是不可消除的人工前提), 可补 "已真机闭合 (Handoff 34)"
   到风险列。
3. README.md 第 70 行 "window 调用前需人工切天正门窗面板到窗模式" 保留。

闭合判据: pytest -q + compileall 仍绿。

---

## 6. 经验回填

- 跨进程数值返回类型一律不可信: file_ipc 的 LISP payload 把整数也走
  vl-prin1-to-string 拉成字符串, 比较时必须显式 str() 或显式接受两种形态。
  本仓库以后再加 preflight 类校验时, 模板:
  `if payload_val not in (expected_int, str(expected_int)):`

- 门 / 窗 共用 DoorSill 的语义模型: COM 不暴露 SillHeight 属性, 也不接受
  COM 写入门窗模式 — 模式 100% 由天正面板和 DXF group 71 决定。这条结论
  在 Handoff 33 与本次 sweep 双重验证后, 落入 TODO_BACKLOG §S-4
  "面板记忆值锁死" 的最终形态; 不要再开任何 "用 COM 切窗模式" 的探针。

- D 级任务的耗时画像: D1 实际推进总耗时 < 15 分钟, 验证了 TODO_BACKLOG
  表头 "D 级 < 0.5 天" 的工时估计。
