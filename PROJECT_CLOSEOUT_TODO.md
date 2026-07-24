# tangent 天正 T20 MCP — 项目收尾 TODO

> 状态快照：2026-07-24（Asia/Shanghai）
>
> **收尾状态：已完成。** 本文件保留为审计清单；最终结果见 §10。
>
> **阅读说明：§0–§9 是收尾前的历史快照，旧分支名和测试数字按当时证据保留；
> 当前基线以 §11、README 和 Handoff 39 为准。**
>
> 用途：新对话先完整阅读本文件、`README.md`、`TODO_BACKLOG.md` 和最新 handoff，
> 然后直接按顺序执行收尾。不要使用、安装或重新初始化 VibeTrace。

## 0. 当前结论

- 按“安全封装高价值 T20 命令”的既定范围，项目约完成 **90%**。
- 核心 MCP 已可用：9 个工具可列出，33 个 `tangent` 子命令有历史真机 E2E 证据。
- 收尾前工作区离线门禁已通过：`185 passed`、`compileall` 通过、
  `git diff --check` 通过、MCP stdio 冒烟通过。
- 尚未收尾的重点不是继续扩命令，而是：**拆清改动边界、补门窗模式门禁真机证据、
  修正文档漂移、整理提交，并决定是否合并/推送 `main`**。

## 1. Git 与工作区快照

当前分支：

```text
fix/dim-precision-and-e2e-verification
```

相对 `main`：领先 2 个提交、落后 0 个：

```text
b0a23b2 fix: 门窗图层分离 — door->DOOR_FIRE, window->WINDOW
56875cb fix: t20mcp:pt 精度 8->2 位小数修复标注歪斜 + E2E 验证加固
```

当前未提交文件：

```text
 M README.md
 M docs/T20_COMMANDS.md
 M scripts/itest_floorplan_draw.py
 M src/t20_mcp/backends/base.py
 M src/t20_mcp/lisp_templates/tangent/opening.lsp
 M src/t20_mcp/tools/tangent.py
 M tests/test_encoding_and_tool.py
 M tests/test_tangent_lisp_gen.py
?? docs/handoff/38_opening_mode_gate.md
?? scripts/church_cross_entities.json
?? scripts/floorplan_entities.json
?? scripts/itest_church_cross_plan.py
```

注意：

- 上述改动不能整体盲提交，先按 §2 分组审查。
- `.vibe/` 和仅含 VibeTrace 规则的 `AGENTS.md` 已删除，不要恢复。
- 不要覆盖或删除来源不明的用户改动；生成物也要先确认是否需要保留证据。

## 2. 先拆清未提交改动

### A. 门窗模式门禁（主线收尾项）

预期相关文件：

```text
README.md
docs/T20_COMMANDS.md
docs/handoff/38_opening_mode_gate.md
src/t20_mcp/backends/base.py
src/t20_mcp/lisp_templates/tangent/opening.lsp
src/t20_mcp/tools/tangent.py
tests/test_encoding_and_tool.py
tests/test_tangent_lisp_gen.py
```

目标：

- `door` 创建后必须校验 DXF group 71 为 `0`。
- `window` 创建后必须校验 DXF group 71 为 `1`。
- 模式不符时删除错误实体，返回结构化 `OPENING_MODE_MISMATCH`。
- 返回值包含 `requires_user_action`、`retry_operation`、`retry_data` 和回滚状态。
- 模型必须暂停，请用户切换门/窗模式；确认后用原参数重试。

### B. 户型/教堂十字平面脚本（独立审查）

相关文件：

```text
scripts/itest_floorplan_draw.py
scripts/itest_church_cross_plan.py
scripts/church_cross_entities.json
scripts/floorplan_entities.json
```

要做：

1. 判断两个 JSON 是应入库的稳定证据、测试夹具，还是一次性运行产物。
2. 若是生成物，先向用户说明，再决定删除或加入 `.gitignore`；不要直接删。
3. 确认两个脚本是否属于本次发布范围。若与门窗门禁无关，单独提交或留到后续，
   不要混进门窗修复提交。

## 3. 修正文档和版本漂移

- `README.md` 仍写“183 测试”，当前实际为 185；可更新数字，或改为不易漂移的表述。
- README 的 9 工具列表写的是 `variable / screenshot`，当前服务实际注册的是
  `view / system`；以 `src/t20_mcp/server.py` 和 stdio 实测为准统一。
- README handoff 索引写 `01..37`，应纳入 Handoff 38。
- 核对 `pyproject.toml` 的 `version = "0.1.0"` 与服务启动日志中的 `3.1.0`，
  确立唯一版本来源后统一；不要只改显示字符串。
- `README.md`、`docs/T20_COMMANDS.md`、工具 docstring、测试数量和实际行为必须一致。

## 4. 离线门禁

每轮代码/文档整理完成后执行：

```powershell
uv run pytest -q
uv run python -m compileall -q src scripts tests
git diff --check
uv run python scripts/itest_19_mcp_stdio_smoke.py
```

当前已知基线：

```text
pytest: 185 passed
compileall: PASS
git diff --check: PASS（只有 LF/CRLF 提示）
stdio smoke: 9 tools，tangent.axis_lines dry-run PASS
```

任一门禁失败都先修复，不进入 Git 合并/推送阶段。

## 5. AutoCAD/T20 真机复验

新对话开始时必须重新检查现场，不能复用本文件中的进程状态。

预检：

```powershell
Get-Process -Name acad -ErrorAction SilentlyContinue |
  Select-Object Id,MainWindowHandle,MainWindowTitle,Path

uv run python scripts/itest_01_bringup.py
uv run python scripts/itest_19_mcp_stdio_smoke.py
```

随后按顺序：

1. `uv run python scripts/itest_dim_precision_verify.py`
2. `uv run python scripts/itest_opening_layer_fix.py`
3. 为 Handoff 38 增加或整理一个窄的真机门禁探针，至少覆盖：
   - 请求 `window`、面板处于门模式：返回 mismatch，错误门实体已删除。
   - 请求 `door`、面板处于窗模式：返回 mismatch，错误窗实体已删除。
   - 用户切到正确模式后，用原参数重试成功。
   - 每轮前后实体数量对账，失败路径不污染图纸。
4. `uv run python scripts/itest_12_e2e.py`
5. `uv run python scripts/itest_e2e_suite.py`
6. 若决定发布户型/教堂脚本，再分别运行其窄测试并核对实体类型、图层和 cleanup。

真机停止条件：

- `mcp_dispatch.lsp not loaded`、ping timeout 或 bringup/recover 失败。
- `CMDACTIVE > 0` 无法通过既有安全恢复路径归零。
- 天正对话框残留、实体数量出现无法解释的增长，或清理失败。
- 不要把 clean exit、`vl-cmdf` 返回值或“生成了某个实体”当成功；
  必须核对实体类型、关键属性、数量增量和回滚结果。

## 6. Backlog 裁定

本次收尾默认不扩展以下项目：

- B3 `window_placeholder/window_replace`：可选批量工作流，不是主线必经项。
- A2 WPF 通用守卫：真实触发场景尚未出现，继续保持低优先级。
- A1 `TRectAxis`：已经 WON'T-SHIP；产物只是普通 LINE，与 `axis_lines` 无增益。
- S 级命令：保持 STOPPED，不重新试探。

只有真机回归明确暴露依赖时，才允许把 B3/A2 拉回当前范围。

## 7. Git 收尾

1. `git diff` 逐文件审查，确认没有秘密、临时路径、运行日志或无关生成物。
2. 按主题拆提交，建议至少分为：
   - 门窗模式门禁及其测试/文档。
   - 户型/教堂脚本（仅在确认纳入发布时）。
   - 文档/版本漂移修正（若不适合并入前两项）。
3. 重跑 §4 全部门禁，并记录 §5 真机证据。
4. 确认工作区只剩明确保留的用户文件；目标是 `git status` 干净。
5. 向用户汇报提交列表和验证结果。
6. **只有用户明确同意后**，才合并到 `main`、推送远端或创建发布标签。

## 8. 完成标准

以下全部满足才算项目收尾完成：

- 33 个现有子命令的文档、代码、测试口径一致。
- 当前 2 个已提交修复和门窗模式门禁均有离线证据。
- 门窗门禁具备双向 mismatch、回滚、正确模式重试的真机证据。
- 核心 E2E 与批量 E2E 通过，图纸无残留污染。
- 工具名、测试数、handoff 索引和版本号不再漂移。
- 生成物去留已明确，提交按主题拆分，没有秘密或临时文件。
- 工作区干净；是否合并/推送 `main` 已由用户明确决定。

## 9. 新对话开场指令

可直接对新对话说：

```text
读取 PROJECT_CLOSEOUT_TODO.md、README.md、TODO_BACKLOG.md 和最新 handoff，
按清单直接开始收尾。不要使用 VibeTrace。先审查当前未提交改动的归属，
再跑离线门禁；真机验证前重新确认 AutoCAD/T20 与 dispatcher 健康。
不要盲删 JSON 证据，也不要未经我同意合并或推送 main。
```

## 10. 2026-07-24 收尾结果

- 门窗模式门禁已完成：双向 mismatch、错误实体回滚、正确模式原参数重试均有真机证据。
- 包版本统一为 `3.1.0`；README 工具名、handoff 索引和测试表述已与代码一致。
- 最终离线门禁：`190 passed`；`compileall`、`git diff --check`、MCP stdio 冒烟通过。
- 真机回归：标注精度 6/6、门窗图层、核心 E2E、批量 E2E 25/25 均通过。
- 户型与拉丁十字教堂脚本纳入发布；分别通过 35 实体断言和 61 实体 9 项验收。
- 两个实体清单 JSON 被裁定为可重建运行产物，已加入 `.gitignore`，不入库。
- 真机测试图元已统一清理，最终实体数为 0。
- 用户已授权自主提交、切换主分支并完成必要发布操作；按主题拆提交后快进 `main`。

## 11. 2026-07-24 强模型复核与增量修正

- 增量修正后的离线门禁：`198 passed`；`compileall`、`git diff --check`、
  MCP stdio 9-tools 冒烟通过。
- Handoff 38 的“人工切换门窗面板后重试”已被 Handoff 39 的控件级自动化取代。
- 正式链路会启动 `TOpening`、按强结构指纹识别「门窗参数」工具栏、后台切换
  插门/插窗，并以空回车退出；创建后的 DXF group71 门禁和错误实体回滚继续保留。
- 真机窄探针 `scripts/itest_42_opening_panel_mode_auto.py` 已依次验证：
  - window：`TCH_OPENING / WINDOW / group71=1`；
  - door：`TCH_OPENING / DOOR_FIRE / group71=0`；
  - 两轮实体增量均为 `+1`，面板均关闭，最终实体数回到 `0`。
- 旧 `_opening_retry.py` 保留兼容入口，但已不再请求终端人工输入。
- 核心 `itest_12_e2e.py` 与批量 `itest_e2e_suite.py` 已接入同一自动入口并通过；
  后者 `25/25`，两者均清理到实体数 `0`、`CMDACTIVE=0`。
- B3 占位/替换方案继续 DEFERRED / OPTIONAL，只保留离线占位与墙体变更后延迟绑定
  的独立价值；A2 仍 DEFERRED；其它 S 级强模态/选择注入命令继续 STOPPED。
