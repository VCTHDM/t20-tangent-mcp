# Handoff 33 - P1/P2/P3 真机推进 (slimming 之后第二轮)

日期: 2026-06-17
分支: main
真机: AutoCAD 2024 + T20 V10 (acad.exe PID 24724) 全程在线; 全部探针真机执行。

本轮在 Handoff 32 基础上, 按 directive 推进 P1A / P1B / P1C / P2A / P3。
所有结论均带本地证据。

## 0. 离线基线 (本轮全程绿)

- pytest -q -> 150 passed
- compileall -q src scripts tests -> COMPILE_OK
- git diff --check -> DIFF_OK
- itest_19_mcp_stdio_smoke.py -> 9 tools, axis_lines dry-run PASS
- itest_01_bringup.py -> 窗口/ping/编码三项 PASS

## 1. P1-A - TPartSaveAs 局部导出路线

脚本: `scripts/itest_33_tpartsaveas_args_probe.py` (新增, 三阶段)

### Phase A 注册 [PASS]

`cname="_TPARTSAVEAS"`

### Phase B path-only [INDETERMINATE]

```
cmdf ok=True payload='active=1'
mid_popups=[(WPF idle), (MDIFrame)]   # 无 #32770
output_file_exists=False
```

含义: 命令仍在等下一个输入, 没消费 path-only。

### Phase B' LOGFILEMODE 抓取真实提示 (关键证据)

```
@@@PROBE-START@@@
TPARTSAVEAS
请选择要导出的对象<退出>:
@@@AFTER active=1@@@
```

TPartSaveAs 是 selection-first 命令: 第一个提示是"请选择要导出的对象", 不是文件路径。

### Phase C selection-set + path 形态 [BLOCKED]

```
prereq wall ok=True (entity 0->1)
cmdf ok=False error='Timeout waiting for result'
mid_popups=[('#32770', '图形导出'), ...]
post_popups=[('#32770', '图形导出'), ...]   # 残留
output_file_exists=False
-> BLOCKED-by-modal
```

含义: 选择集到位后, TPartSaveAs 弹 #32770 "图形导出" 模态框 (即使 FILEDIA=0),
dispatcher 因模态阻塞超时。**无 silent 导出参数形态。**

ESC-only 恢复: 用 PostMessage VK_ESCAPE 打到模态 hwnd 自身, 一轮内关闭, 环境归位。

### P1-A 结论

- TPartSaveAs **不可静默封装为 wrapper**, STOPPED, 与 export_t3 / TGetXML 同族。
- 资产: `scripts/itest_33_tpartsaveas_args_probe.py` (回归探针, 不入 SUBCOMMANDS)。
- 不要再尝试 path-only / version-token 等 vl-cmdf 形态。

## 2. P1-B - TSingleAxisDim 提示流捕获

复用 `scripts/itest_32_prompt_capture_log.py`。

### 关键证据

```
@@@PROBE-START@@@
TSINGLEAXISDIM
点取待标注的轴线或[手工绘制(D)]<退出>:*取消*
```

带坐标实验:

```
TSINGLEAXISDIM
命令: 0,0 未知命令"0,0"
```

含义: `0,0` 在 TSingleAxisDim 退出后才被命令行接到, 说明命令在第一个提示就因
"未点中实体"自行退出 - entsel 风格, 不接受坐标输入。

### P1-B 结论

- TSingleAxisDim 属于 selection-injection 族 (TLeader/TPointIndex/TDimRad 等),
  不要包装, STOPPED。
- axis_lines 普通 LINE 轴网仍是当前替代路径。

## 3. P1-C / P3 - TOpening (door / window) COM 读回

脚本: `scripts/itest_35_opening_readback.py` (新增)

### door 读回 [PASS]

```
[wall]   count 0->1
[door]   count 1->2
payload='type="TCH_OPENING" W=900.0 H=2100.0 DS=0.0 SH=#<%catch-all-apply-error%>'
entity delta=+1: PASS
type=TCH_OPENING: PASS
expected: W=900.0 H=2100.0 DS=0.0 SH=None  (matches)
cleanup clean: PASS
```

旁路深探 (entget + vlax-dump-object) 证实:
- DXF: `(0 . "TCH_OPENING") (100 . "TDbOpening")`
- COM `Width=900.0`, `vl-catch-all-error-p` 为 nil。

### window 读回 (面板当前在门模式) [INDETERMINATE]

```
[wall]   count 0->1
[window] count 1->2
payload='type="TCH_OPENING" W=1500.0 H=1500.0 DS=0.0 SH=#<%catch-all-apply-error%>'
```

含义: tangent.window (sill_height=900) 后生成的 TCH_OPENING 仍然暴露 DoorSill=0.0,
不暴露 SillHeight - 与 door 调用产出的对象完全同型。**经验证实 directive 预言:
面板未切到窗模式时, TOpening 沿用门模式, SillHeight 注入被忽略, 仍是门对象。**

### 待后续真机的人工前提 (用户需要做)

请把天正"门窗"面板手动切到窗模式 (Window) 后保留, 不要关闭面板; 然后再次执行:

```
uv run python scripts/itest_35_opening_readback.py window
```

如果窗模式下 readback 显示 `SH=900.0` 且 `DS` 为 catch-all-error, 则 SillHeight 路线
真机闭合, 后续接手者再把 README / docs/T20_COMMANDS.md / warning 更新成
"已验证 SillHeight"。

### 本轮已基于现有证据更新的 LOW_CONFIDENCE_WARNINGS

文件: `src/t20_mcp/tools/tangent.py`

- door: 明确"面板默认门模式下 W/H/DoorSill 已 COM 读回验证 (Handoff 33)";
  保留依赖面板模式的提醒。
- window: 补"Handoff 33 真机证据显示门模式下 TOpening 仍生成 TCH_OPENING 但仅暴露
  DoorSill, SillHeight 注入被忽略; 窗模式下的 SillHeight 复测仍待人工切窗模式"。
- 未取消任何人工前提。

## 4. P2-A - TGColumn 标准柱面板 Gate A inventory

脚本: `scripts/itest_36_column_gate_a_inventory.py` (新增, inventory-only, 严格 ESC-only)
原始抓取: `docs/handoff/33_tgcolumn_gate_a_raw.txt` (578 行)

### 关键事实

```
[reg] cn="_TGCOLUMN"
[baseline] entity_count=0  pre_existing_#32770_modals=[]
[launch] ok=True payload='active=1'
[modals_after_launch] [790400]
# Modal hwnd=790400 class='#32770' title=''
  rect=(80, 120, 255, 566)  enabled=True
  owner_hwnd=1574868  owner_disabled=False
  child_count: 556
  顶层子控件 (节选):
    Static '材料:'/'转角:'/'图库:'
    嵌套 #32770 '柱高' (style 0x50000044)
    Button '柱高'
    Edit (柱高数值)
[post-recover] remaining_#32770_modals=[]
entity_count=0  env={CMDACTIVE:0, CMDDIA:1, FILEDIA:1, OSMODE:0}
```

### 解读

- 标准柱面板的 #32770 顶层 enabled=True, owner_disabled=False: Win32 层面 modeless 风格,
  但 AutoCAD CMDACTIVE=1, 命令行被锁。
- 控件全部经典 Win32 (Static/Button/Edit/嵌套 #32770), **没有 WPF HwndWrapper**。
- ESC-only 恢复 100% 干净, 没有残留模态/未知实体。

---

## 附录 A: window 模式 SillHeight 参数修复 (2026-06-17 真机切窗模式后)

### 问题根因 (前)

Handoff 29/30/31 假定 TCH_OPENING 在窗模式下有独立 `SillHeight` COM 属性,
并在 `_gen_opening` window 分支注入 `SillHeight`。Handoff 33 真机枚举彻底证伪:

```
SillHeight=ERR(ActiveX 服务器返回错误: 未知名称: SillHeight)
WindowSillHeight=ERR(未知名称)
WinSillHeight=ERR(未知名称)
... 所有变体均 ERR
```

**TCH_OPENING 在 door 模式和 window 模式下暴露的 COM 属性集合完全相同**:
`Width` / `Height` / `DoorSill` / `Application` / `AreaRatio` / `Layer` / `Handle`。
门/窗的真正区分是 **DXF group 71**: `0` = 门, `1` = 窗, 由天正面板模式决定。

### 面板切窗模式的实证

```
OSMODE=16384  (天正切窗模式后的非默认值)
新图层: 3T_BAR / 3T_GLASS / 3T_WOOD / _TCH_KEY  (天正切窗模式后自动注册)
DXF group 71=1 (window 调用后产出对象均为组 1)
```

### 修复前 sweep 测试 (面板切窗模式后, sill_height=600/1200/300)

```
ix=1500 sh_in=600  W=1000.0 H=1500.0 DS=900.0 group71=1
ix=3500 sh_in=1200 W=1000.0 H=1500.0 DS=900.0 group71=1
ix=5500 sh_in=300  W=1000.0 H=1500.0 DS=900.0 group71=1
```

全部 DoorSill 固定为 **900** (面板记忆值), 传入 `sill_height` **完全不生效**。
因为 `SillHeight` 注入被 `vl-catch-all-apply` 吞掉了 (ERR), 所以 DoorSill 没被改。

### 修复

**`tangent.py _gen_opening` window 分支**: 把写入属性名从 `SillHeight` 改为 `DoorSill`。
语义上, window 模式的 `DoorSill` 就是"窗台高"。添加 Handoff 33 证据注释。

**`opening.lsp` 模板头注释**: 更新 "注入 SillHeight (窗台高)" 为 "注入 DoorSill (实为窗台高)"。

**`LOW_CONFIDENCE_WARNINGS["window"]`**: 去掉"仍待验证"字样, 改为已验证 + 注明语义共享。

**`docs/T20_COMMANDS.md` 窗模式切换一行**: 更新为 "窗台高走 DoorSill" + 附上 Handoff 33 结论。

### 修复后 sweep 测试 (PASS PASS PASS)

```
ix=1500 sh_in=600  W=1000.0 H=1500.0 DS=600.0 group71=1
ix=3500 sh_in=1200 W=1000.0 H=1500.0 DS=1200.0 group71=1
ix=5500 sh_in=300  W=1000.0 H=1500.0 DS=300.0 group71=1
```

三组 sill_height 全部与传入值精确匹配。PASS。

### 验证的安全边界

- 仅改 `tangent.py` (一行属性名 + 注释) + `opening.lsp` (注释)。
- 未触碰 `_prelude.lsp` / `file_ipc.py` / `mcp_dispatch.lsp` / `dialog_automation.py`。
- 未改动 32 子命令集合, `EXECUTE_DISABLED_SUBCOMMANDS` 仍空。
- pytest 150 passed, 无回归。

---

## 附录 B: 本轮新增脚本说明

| 脚本 | 用途 |
|---|---|
| `scripts/itest_33_tpartsaveas_args_probe.py` | TPartSaveAs 三阶段探针 (reg/path/selection) |
| `scripts/itest_35_opening_readback.py` | door/window Width/Height/DoorSill 读回探针 |
| `scripts/itest_36_column_gate_a_inventory.py` | TGColumn Gate A 子控件抓取 (ESC-only) |

### P2-A 结论

- Handoff 13 / itest_30 BLOCKED 结论复现, 但**第一次拿到完整子控件 inventory**。
- column 子命令保持移除, EXECUTE_DISABLED 仍空。
- 后续 Gate B 探索可基于 raw.txt 控件 hwnd/class/title 做映射, Gate A 不点击不填框
  不改 dialog_automation.py。

## 5. 不在本轮范围内 (留给后续 handoff)

- TRectAxis / 轴网 Gate A inventory: 未做, 优先级同 column。
- TSaveAs / WPF 导出框 Gate A inventory: 未做, 最后手段。
- TBlkMask1 / WIPEOUT / TGirDer / TWINDROSE / TLeader / TPointIndex / TSectIndex /
  TDimRad/Dia/Ang/Arc / TSlab / TElevator / TDrawParallelStair 族:
  directive 列为硬尾巴, 本轮未碰。
- 真机窗模式 SillHeight 验证: 等用户切面板。

## 6. 本轮新增/修改文件清单

新增脚本:
- `scripts/itest_33_tpartsaveas_args_probe.py`
- `scripts/itest_35_opening_readback.py`
- `scripts/itest_36_column_gate_a_inventory.py`

新增证据:
- `docs/handoff/33_tgcolumn_gate_a_raw.txt`
- `docs/handoff/33_p1_p2_p3_evidence.md` (本文件)

修改:
- `src/t20_mcp/tools/tangent.py` LOW_CONFIDENCE_WARNINGS door/window 文案

不动:
- _prelude.lsp / file_ipc.py / mcp_dispatch.lsp / dialog_automation.py / 编码与 IPC 基础设施

## 7. 下一接手者最小可行路径

1. 跑 itest_01_bringup.py + itest_19_mcp_stdio_smoke.py 验证基线
2. 让用户切窗模式后跑 itest_35_opening_readback.py window 闭合 SillHeight
3. 不要尝试 TPartSaveAs / TSingleAxisDim wrapper, 已 STOPPED
4. column / TRectAxis / TSaveAs 的 Gate B (控件映射) 是 P3+ 的事, 当前不动 dialog_automation.py
5. 每次改动后跑: pytest / compileall / diff check / stdio smoke
