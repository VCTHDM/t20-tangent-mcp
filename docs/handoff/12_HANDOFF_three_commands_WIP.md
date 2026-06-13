# Handoff 12 — TGColumn / TDimTP / TSWall 提示捕获与封装（进行中，未提交）

执行人：fable（额度用尽中断）｜ 日期：2026-06-13 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

> **接手者必读**：本轮在真机上**破译了三个卡住命令的命令行提示序列**（之前两轮调研+
> LASTPROMPT 法都失败，本轮用 **LOGFILEMODE 日志法**成功）。TGColumn 已完成封装
> 并通过 E2E；TDimTP / TSWall 提示已知但最小成功序列还差一步。**本轮所有改动尚未 commit**，
> 工作树里有一批 `scripts/_probe_*.py` 临时探针（下划线前缀，**提交前必须删除**）。

## 0. 当前 git 状态

- 最后一个正式提交：`188b8e2 [fable] close LASTPROMPT capture route`（已 push 到的历史）。
- 此后**未提交任何东西**。工作树新增的临时文件（都要删，不要提交）：
  - `scripts/_probe_harness.py`（WM_CHAR 打字 + 截图）
  - `scripts/_probe_state.py`（查/清实体类型、查环境）
  - `scripts/_probe_recover.py`（卡死恢复）
  - `scripts/_probe_cmd.py`（候选序列批量试 + 截图）
  - `scripts/_probe_launch.py`（启动命令留活动 + 截图）
  - `scripts/_probe_cmdline.py`（开命令行窗，**有副作用见 §4**）
  - `scripts/_probe_fixshot.py`（还原+置前修截图）
  - `scripts/_probe_log.py`（**核心工具**：LOGFILEMODE 日志法捕获提示——这个值得保留/转正）

## 1. 关键方法论突破：LOGFILEMODE 日志法（务必沿用）

读天正命令行提示的**唯一可靠办法**（截图/LASTPROMPT/动态输入全失败）：

```
1. execute_lisp: (setvar "LOGFILEMODE" 1)，读 (getvar "LOGFILENAME") 得日志路径
   本机日志: C:\Users\Administrator\documents\codex\2026-05-28\...\Drawing1_<hash>.log
2. execute_lisp 里设 (setvar "CMDECHO" 1)  ← 关键！CMDECHO=0 会让提示不写日志
3. vl-cmdf 启动命令（参数不足则命令留活动），不立即取消
4. Python 端 sleep ~0.6s 让日志刷新，直接读日志文件（按 GBK 解码）增量段
5. Python 端发 ESC（PostMessage 到 MDIClient）取消命令
6. execute_lisp: (setvar "LOGFILEMODE" 0)
```

`scripts/_probe_log.py` 已实现这套，用法：
```
uv run python -X utf8 scripts/_probe_log.py path                      # 看日志路径
uv run python -X utf8 scripts/_probe_log.py run <CMD> <arglist|场景名> <wall|line|none>
```
内置命名场景（避开 PowerShell 引号地狱）：`tswall_ss` / `tswall_ss_w` /
`tdimtp_fence` / `tdimtp_cross` / `empty`。验证过原生 LINE 提示能抓到
（"指定第一个点: *取消*"），机制可靠。

## 2. ★ TGColumn（标准柱）—— 已封装并 E2E 验收

`scripts/_probe_cmd.py tgcolumn` 真机结果（4 组候选全成）：
```
[pt]              newtype=TCH_COLUMN active=0 delta=1   ← 最简序列
[pt+enter]        newtype=TCH_COLUMN active=0 delta=1
[pt+angle+enter]  newtype=TCH_COLUMN active=0 delta=1
[pt+pt]           newtype=TCH_COLUMN active=0 delta=2   （两点=两根柱，连续放置）
```
**结论**：`(vl-cmdf "TGCOLUMN" (t20mcp:pt X Y))` → 生成 1 个 `TCH_COLUMN`，
命令自动结束（active=0）。点驱动 + 面板记忆截面/尺寸，**与 wall/door 同模式**。
上一轮（handoff 08）报"0 实体"是序列/格式问题，**已推翻**。

**本轮完成（Codex，2026-06-13）**：
1. 已新增 `src/t20_mcp/lisp_templates/tangent/column.lsp`：
   - 走 prelude 骨架（`t20mcp:begin`/`*error*`/`t20mcp:end`/`t20mcp:fail`）；
   - `{{SET_LAYER}}`；记 `entlast`；`(t20mcp:call "TGCOLUMN" (list (t20mcp:pt {{X}} {{Y}})))`；
   - 成功判据：新增实体且类型 `= "TCH_COLUMN"`，否则 fail；
   - `angle` 仅尝试 `Angle` / `Rotation` 候选 COM 属性，失败吞掉，不影响建柱成功。
2. 已在 `tangent.py` 加 `_gen_column(data)`（data: `{x, y, layer?}`，可选 `angle?`），
   注册进 `_GENERATORS`（键名 `column`），更新 tool docstring 的 operations 列表。
3. 已加离线测试到 `tests/test_tangent_lisp_gen.py`：
   `VALID_CASES["column"] = {"x":0,"y":0}`，并断言 `TGCOLUMN` 点序列、图层与类型校验注入。
4. 已新增 `scripts/itest_30_column_e2e.py`，真机结果：
   `entities 0->1 type='TCH_COLUMN'`，`column: PASS`，`清理还原: PASS`。
5. 已回填 README / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`。

**后续可选增强**：
1. 真机探测 TCH_COLUMN 的 COM 属性名（截面宽/高/转角/材料），
   仿 `itest_29_opening_kind_probe.py`，用 `vlax-dump-object` 或属性候选名清单。
   官方 ARX 线索（docs/research/2026-06-13_install_dir_prompt_strings.md §7.3）：
   `tch10_com24.dll` 暴露 `GetHeight/SetHeight@TColumnData`、`SetSectionShape@TColumnData`、
   `SetMaterial@TColumnData`、`TDbColumn` —— 但这些是内部符号，ActiveX 属性名需真机确认。

## 3. TDimTP（两点标注）—— 提示已知，语义已明，差正确场景

LOGFILEMODE 抓到的提示流（真机）：
```
请选择起点<退出>:        ← 给点1
请选择终点<退出>:        ← 给点2
选中的对象数目太少, 不能进行两点标注!   ← 单面墙 + 沿中线的两点 → 对象不足
```
**语义判定**：两点定义一条**栏选/穿越线**，命令标注该线穿过的一排天正对象
（柱/墙/门窗/轴线）的**间距**。不是"标注两点间距离"，而是"穿过哪些对象就标注它们"。
单个对象会报"对象数目太少"。

**待办 B（接手者，先用 `_probe_log.py` 验证场景再封装）**：
1. 搭**多对象一排**场景再测。建议：先放 3 根柱 `TGCOLUMN` 于 (0,0)/(3000,0)/(6000,0)，
   再 `_probe_log.py run TDIMTP tdimtp_fence none`（场景 `tdimtp_fence` = 两点
   (-500,0)→(6500,0)，横穿三柱）。预期标注三柱间距，生成 `TCH_DIMENSION2`。
   - 备选场景 `tdimtp_cross` = (1500,-800)→(1500,800) 竖向穿单墙，试墙厚向。
   - 注意：`_probe_cmd.py`/`_probe_log.py` 的 prereq 目前只支持单 wall/line，
     多柱场景需要在脚本里加，或手动先建好柱再跑（柱已可由 column 封装生成）。
2. 找到能生成 `TCH_DIMENSION2` 的最小点序列后，照 `wall_thickness_dimension.lsp`
   套路写 `two_point_dimension.lsp`（命令 `TDIMTP`），data 形如 `{p1_x,p1_y,p2_x,p2_y,layer?}`。
3. 同样补 VALID_CASES、tool docstring、itest E2E。
4. **若多对象场景仍失败**：把 LOGFILEMODE 完整提示流贴进本文档，标记"需更多线索"，
   不要硬猜超过两轮（PROJECT_RULES 铁律）。

## 4. TSWall（单线变墙）—— 提示已知，选择成功但未转换（卡点）

LOGFILEMODE 抓到的提示：
```
选择要变成墙体的直线、圆弧或多段线:  找到 1 个
选择要变成墙体的直线、圆弧或多段线:        ← 我的 "" 结束选择
@@@AFTER active=0@@@                        ← 命令结束, 但没生成 TCH_WALL (delta=0)
```
**卡点**：选择集成功传入（"找到 1 个"），回车结束选择后命令**直接结束、未转换**
（无新实体、原 LINE 也没变 TCH_WALL）。`_probe_cmd.py tswall` 三组（含带 "240" 宽度）
全部 delta=0 / newtype=none。

**怀疑方向（接手者优先验证）**：
1. **选择后可能弹模态/参数对话框**（墙宽/对齐/材料），CMDDIA=0 对天正框无效，
   vl-cmdf 的后续 "" 没喂到框上 → 框被默默取消 → 不转换。
   - **下一步**：用 `_probe_log.py run TSWALL tswall_ss line` 看选择后**完整日志**
     （我中断前正要看，没看到）。**如果日志在"找到1个"之后没有更多文字提示，
     极可能是弹了对话框**（对话框不写命令行日志）。
   - 验证弹框：仿 `itest_28_rectaxis_recon.py`，启动 TSWALL + 喂选择集后，
     枚举 acad.exe 顶层窗口找 `#32770`，dump 子控件。若有框 → 用
     `src/t20_mcp/dialog_automation.py`（已有的白名单 BM_CLICK 原语，handoff 10 建的）
     驱动"确定"。**严禁 WM_CLOSE**。
2. 若不是弹框：可能选择集要用**交互式 ssget（pause）**而非预构造 pickset，
   或转换前需指定基线对齐关键字。再用日志法逐步试。

**注意**：`dialog_automation.py` 已有 `click_dialog_buttons(title, buttons)` 白名单原语，
TSWall 若弹框，加一个场景白名单即可（标题需先 recon 确认）。

## 5. 真机踩坑教训（接手者避雷）

1. **交互式打字进"已激活命令"会搞丢 dispatcher**：本轮把 `(c:mcp-dispatch)` ping
   在 TGColumn 活动时触发 → 嵌套命令 → dispatcher 失效，得 `itest_01_bringup.py`
   重新引导。**规则**：execute_lisp / dispatch 前必须确保 `CMDACTIVE=0`；
   读提示时只用"启动留活动 → 读日志 → **ESC**（纯 ESC 安全）"，不要在活动命令里再 dispatch。
2. **`COMMANDLINE` 命令会浮出命令行窗并破坏 PrintWindow 截图**（截出全黑）。
   `_probe_cmdline.py` 干过这事。恢复：`COMMANDLINEHIDE` + `_probe_fixshot.py`
   （ShowWindow SW_RESTORE + SetForegroundWindow 后截图才正常）。**别再用 COMMANDLINE 读提示**，
   用 LOGFILEMODE 日志法。
3. **CMDECHO=0 会让命令行提示不写进日志**——日志法务必先 `(setvar "CMDECHO" 1)`。
   （prelude 的 `t20mcp:begin` 会设 CMDECHO=0，所以读提示的探针**不要**用 begin 包，
   或读完恢复。）
4. 这套界面**命令行窗口是隐藏的**，动态输入提示 PrintWindow 抓不到 → 必须靠日志。
5. TGColumn 启动会弹**非模态**标准柱面板（不阻塞 dispatch），探测后可能残留，
   单发 ESC 关掉即可。

## 6. 收尾状态（中断时）

- 真机：probe 都带 UNDO 清理 + 环境复位；中断前最后一次跑的是 TSWALL tswall_ss，
  **可能残留**：建议接手第一步先 `uv run python -X utf8 scripts/_probe_state.py clean`
  再 `... types` 确认图面为空、`CMDACTIVE=0`。若 dispatcher ping 失败，先
  `uv run python -X utf8 scripts/itest_01_bringup.py` 重新引导。
- LOGFILEMODE 中断时应已被探针关回 0，但**请确认** `(getvar "LOGFILEMODE")` = 0，
  避免日志持续写盘（用 `_probe_state.py env` 加查或单独 execute_lisp）。
- 离线测试基线：`uv run pytest -q` = **90 passed**（未含本轮新增）。

### 2026-06-13 Codex 接手补记

- 已从当前 `main` 切出分支 `codex/tgcolumn-three-commands`。
- TGColumn 已转正为 `column` 子命令，新增模板、生成器、离线测试、E2E 脚本和文档回填。
- 本轮验证：
  - `uv run pytest -q` = **92 passed**。
  - `uv run python -X utf8 scripts/itest_01_bringup.py` 曾通过，随后
    `uv run python -X utf8 scripts/itest_30_column_e2e.py` 真机通过：
    `entities 0->1 type='TCH_COLUMN'`，`column: PASS`，`清理还原: PASS`。
- 后续复测时 AutoCAD/T20 换到另一个窗口句柄，dispatcher 未加载/未响应：
  - `itest_30_column_e2e.py` 初始化失败：`mcp_dispatch.lsp not loaded`。
  - `itest_01_bringup.py` 尝试从 `%TEMP%/t20_mcp/mcp_dispatch.lsp` 引导后 ping 超时。
  - `itest_11_force_recover.py` 未发现 `#32770` 对话框，恢复验证仍失败。
  - `_probe_recover.py` 发 ESC 后初始化仍报 `mcp_dispatch.lsp not loaded`。
- 按 README 规则 2，当前 **ping 不通，停止 TDimTP/TSWall 真机探索**。接手者请先人工确认
  AutoCAD 当前图纸/命令行状态，或按提示手动 `(load ".../lisp-code/mcp_dispatch.lsp")`
  恢复 dispatcher，再继续 §7.3/§7.4。

## 7. 接手推荐顺序

1. 清理真机 + 确认 dispatcher（§6）。
2. ~~先把 TGColumn 转正~~ **已完成**（见 §2，本轮应以 `[assist]` 提交）。
3. TDimTP 多柱场景验证（§3 待办 B），通了就封装。
4. TSWall 弹框 recon（§4），定性后再决定封装或记录停手。
5. 全部完成后：**删除所有 `scripts/_probe_*.py` 临时探针**（除非决定把 `_probe_log.py`
   转正为 `itest_30_prompt_capture_log.py` —— 它确实有长期价值，可保留并改名去掉下划线）。
6. 回填三处权威待办（README 路线图 / README tangent 子命令表 + 完成度 /
   docs/T20_COMMANDS.md §2 子命令表 + §3）。同步更新 `docs/handoff/05 §6`。
