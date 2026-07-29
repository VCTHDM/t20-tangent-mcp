# Handoff 40 — 仓库收敛与 fresh 33/33 真机回归

日期：2026-07-26（Asia/Shanghai）

代码基线：`main` 提交 `75dbc6c`，以及本 handoff 同批、尚未第二次提交的
实机测试加固改动。未推送远端，未保存测试 DWG。

## 1. 结论

本轮先完成仓库级一致性整改并提交，再在 AutoCAD 2024 + T20 V10 上执行
fresh real-machine 回归。33 个 `tangent` 子命令均至少走过一次当前生产执行路径；
所有脚本最终回到实体基线，未发现残留面板或活动命令。

“fresh 33/33”表示每个子命令均通过其当前脚本门禁，不表示所有可选参数组合都被
穷举，也不提升原有 warning 的证据强度。特别是普通 `dimension`、依赖面板记忆值的
构件和已有房间更新场景，仍遵守 README 与 `docs/T20_COMMANDS.md` 的限制。

## 2. 环境与恢复记录

- AutoCAD：2024，`ACADVER=24.3s (LMS Tech)`。
- T20：天正建筑 V10.0，配置 `/p TArch20V10`。
- 图纸：未保存的 `Drawing1.dwg`。
- IPC：默认 `%TEMP%\t20_mcp`；真机脚本全部串行持有 live lock。
- 稳态变量：`CMDACTIVE=0`、`CMDDIA=1`、`FILEDIA=1`、`OSMODE=0`。

第一次 bringup 在旧进程 PID 22360 上发生 dispatcher ping timeout；
PostMessage 加载和 COM fallback 后仍无 result，因此按停止规则没有继续实体测试。
两次尝试之间 AutoCAD 进程变为 PID 20108；Windows Application 日志没有给出可确认
的崩溃记录，本 handoff 不推断进程更换原因。

随后执行无实体副作用的后台 COM 加载探针：

```text
OK||DIR|C:/Users/Administrator/AppData/Local/Temp/t20_mcp/
```

探针证明 dispatcher 能正常加载且两端 IPC 目录一致；`SECURELOAD` 恢复为 1。
正式只读 ping 与第二次 bringup 随即通过。探针文本已删除，IPC 目录最终只保留
正式 `mcp_dispatch.lsp`。

## 3. 同批测试代码收敛

- `_live_lock.py` 统一实机脚本 stdout/stderr 为 UTF-8，中文证据不再依赖调用者临时
  设置 `PYTHONIOENCODING`。
- `find_autocad_window()` 将空标题 `acad.exe` 辅助窗降为最后 fallback，单实例不再
  误报 multiple windows；真正多个带标题主窗仍告警。
- bringup 分离 dispatcher ping 与中文图层 roundtrip，后者不能再替前者伪造 PASS。
- `itest_dim_precision_verify.py` 将只验证实体生成的场景改名为
  `dimension_12000_span_created`；不可读的 `Measurement/Text` 明确只作诊断。
- `itest_12_e2e.py` 把 T20 V10 不暴露的可选门属性降为 diagnostic-only；
  主门禁增加 `result.ok` 与 `DoorSill=0.0`。
- `itest_e2e_suite.py` 的 `wall_thickness_dim` 现在强制检查数量 `+1` 和精确类型
  `TCH_DIMENSION2`，并将 `axis_lines`、`search_room` 纳入统一套件，25 case 扩为
  27 case。
- `itest_25_explode_read_e2e.py` 改为 `finally` 统一回滚；墙体创建或协议失败时也
  不会把测试墙留在图纸。

## 4. fresh 真机证据

| 命令 | 结果 | 关键证据 | 清理 |
|---|---|---|---|
| `itest_01_bringup.py` | PASS | 窗口、ping、中文图层 roundtrip 全 PASS | 无几何实体 |
| `itest_dim_precision_verify.py` | `6/6` | `TCH_DIMENSION2`、两点标注、墙厚标注、墙端点对齐、12000 跨度实体生成 | `0 == 0` |
| `itest_42_opening_panel_mode_auto.py` | 全 PASS | window=`WINDOW/group71=1`；door=`DOOR_FIRE/group71=0`；两轮 panel closed | `0 -> 0` |
| `itest_12_e2e.py` | 全 PASS | wall 属性含 `Style=砖`；dimension=`TCH_DIMENSION2`；door 宽高与 `DoorSill=0.0` | entities=0，环境复位 |
| `itest_e2e_suite.py` | `27/27` | 含 `axis_lines 0->4 LINE`、`wall_thickness_dim 1->2 TCH_DIMENSION2`、`search_room 4->5 TCH_SPACE` | PASS |
| `itest_39_column_gate_b_e2e.py` | 3 项 PASS | full: H=3300/R=45/W=500/D=400/S=金属；minimal；bad material 拒绝 | 每例回 0，无残留 popup |
| `itest_25_explode_read_e2e.py` | 全 PASS | 4 LINE，`rc=True`，`clean=True`，坐标平移门禁通过 | 原墙保留后再清到 0 |

33 个子命令的本轮覆盖由以下不重复集合组成：

1. 27-case suite：`axis_lines`、3 个专项标注、23 个符号/构件命令及
   `search_room`。
2. 核心与门窗脚本新增：`wall`、`dimension`、`door`、`window`。
3. column Gate B：`column`。
4. explode 专项：`explode_read`。

合计 `27 + 4 + 1 + 1 = 33`。

## 5. 离线门禁

- `uv run ruff check src tests scripts`：PASS。
- `uv run ruff format --check src tests scripts`：`52 files already formatted`。
- `uv lock --check`：PASS（56 packages）。
- `uv run pytest -q`：最终重跑 `267 passed in 14.51s`。
- `uv run python -m compileall -q src scripts tests`：PASS。
- `uv build`：sdist 与 wheel 构建成功；wheel 含正式
  `t20_mcp/lisp_code/mcp_dispatch.lsp` 和 dist-info metadata。
- `uv run python scripts/itest_19_mcp_stdio_smoke.py`：9 个工具可列出，
  `tangent.axis_lines` dry-run PASS。
- `git diff --check`：PASS。

## 6. 保留边界

- `dimension_12000_span_created` 证明实体执行、数量与类型，不声称读取到了数值
  `Measurement`；T20 V10 返回 `<no>`。
- `search_room` 本轮证明“无既有房间时，闭合墙体新增 TCH_SPACE”；已有房间的更新
  判据仍未扩展。
- `axis_lines` 是普通 `LINE` 网格，不是天正智能轴网。
- `explode_read` 仍容忍历史已知的 T20 分解起点归零缺陷，但终点侧、平移、内部回滚
  和最终清理均为硬门禁。
- 历史 handoff 保持原样；旧测试数和旧限制仅表示当时证据。
