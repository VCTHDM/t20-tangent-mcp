# Handoff 06 — GPT TMElev 试驱动后崩溃停手记录

执行人：GPT ｜ 日期：2026-06-12 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024（Drawing1.dwg）

## 1. 停手原因

命中 README 规则 1 / 规则 2 的停手条件：用户反馈 **CAD 闪退**。本次之后 GPT 不再继续任何真机试驱动、恢复脚本或命令封装执行，交由 fable 排查。

## 2. 已执行步骤

1. 读 README / AGENTS / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`，确认 GPT 只能做可复用管线内的体力活，不碰 `_prelude.lsp`、IPC、dispatcher。
2. 离线基线：
   - `uv run pytest -q`
   - 结果：`64 passed in 0.63s`
3. 真机 bringup：
   - `uv run python scripts\itest_01_bringup.py`
   - 结果：窗口识别 PASS，ping PASS，中文编码往返 PASS。
4. `TDimTP` 两轮最小序列试驱动：
   - `[p1 p2 pos 回车]`：`count 0 -> 0`, `type none`
   - `[pos p1 p2 回车]`：`count 0 -> 0`, `type none`
   - 按“两轮仍 0 实体即停”规则，未继续硬猜。
5. `TMElev` 两轮试驱动：
   - `base-pos`: `exec True`, `count 0 -> 1`, `type TCH_ELEVATION`
   - `point-only`: `exec False`, `Timeout waiting for result (request_id=c84031f3a006)`, 后续 `entity_count` / env 读取失败。
6. 超时后尝试安全恢复：
   - 没有使用 `WM_CLOSE`。
   - 仅向 AutoCAD 主窗口及可见子窗口发送 ESC。
   - 输出：`multiple_autocad_windows chose_dwg_title=False chosen_hwnd=1773358 count=2 used_process_match=False`，随后 `sent esc to 4 windows`。
7. 用户随后反馈：`cad闪退了`。

## 3. 现场输出摘要

`TMElev` 试驱动输出：

```text
init True None
tmelev-base-pos exec True  None count 0 1 type TCH_ELEVATION
tmelev-point-only exec False None Timeout waiting for result (request_id=c84031f3a006) count 0 -1 type None
env None
```

ESC 恢复输出：

```text
multiple_autocad_windows chose_dwg_title=False chosen_hwnd=1773358 count=2 used_process_match=False
hwnd 1773358
sent esc to 4 windows
```

崩溃后只读检查：

```text
Get-Process acad -ErrorAction SilentlyContinue
```

无 `acad.exe` 输出。

`git status --short`：

```text
?? AGENTS.md
```

说明：本轮在事故前没有改源码；`AGENTS.md` 是既有未跟踪文件，未触碰。

## 4. 初步判断（仅供 fable 排查）

- `TMElev` 的 `base-pos` 序列可生成 `TCH_ELEVATION`，但未做模板封装、未写代码。
- `point-only` 点不足导致命令挂起等待输入，随后 IPC 超时。
- ESC 恢复阶段出现多 AutoCAD 窗口告警，`find_autocad_window` 选择了非 DWG 标题窗口；这可能导致 ESC 投递目标与实际活动绘图窗口不完全一致。
- 未发送 `WM_CLOSE`，未运行强关对话框脚本。

## 5. 建议 fable 下一步

1. 重启 T20/AutoCAD 后先检查 Drawing Recovery / 自动保存文件，确认用户图纸无损。
2. 检查 AutoCAD 崩溃日志和 Windows 事件查看器中 `acad.exe` 的 fault module。
3. 排查 `TMElev` 点不足挂起时，ESC 对天正标高命令是否安全；后续脚本应优先用命令行句柄或活动文档窗口恢复，避免多窗口误投。
4. 在 fable 审查前，不建议合入 `TMElev` 封装；最多保留“第一序列可生成 `TCH_ELEVATION`，第二序列超时后崩溃”这个调研结论。
