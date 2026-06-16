# Handoff 09 — P1-2 补盲: 模态对话框探测 (含 WPF/跨线程)

执行人：fable ｜ 日期：2026-06-13 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024（Drawing1.dwg）

## 1. 问题

`_autocad_modal_dialog_present` 原实现只认 `#32770` 类名，且只枚举**主 UI 线程**
（`GetLastActivePopup` + `EnumThreadWindows`）。Handoff 05 记录的盲区：`TSaveAs`
天正导出框探测不到，dispatch 会傻等超时。

## 2. 修复（file_ipc.py）

新增第一信号：**主窗口被禁用**（`IsWindowEnabled(main_hwnd) == FALSE`）。
任何模态循环（原生 `#32770`、ObjectARX、WPF `ShowDialog`）都会禁用 owner 窗口，
该信号与对话框类名、所属线程无关。

刻意**不做** `HwndWrapper[...]` 类名匹配：天正非模态 WPF 面板（门窗面板等）同为
HwndWrapper，类名匹配会把正常状态误判为阻塞，堵死全部 dispatch。
「owner 被禁用」正是模态/非模态的判别式。

原 `#32770` 枚举保留为第二信号。

## 3. 真机验收（scripts/itest_21_wpf_dialog_guard.py）

| 检查项 | 结果 |
|---|---|
| 基线（天正非模态面板在场）探测=False，无误报 | PASS |
| `TGETXML` 弹框期间探测=True | PASS |
| `TSAVEAS` 弹框期间探测=True | PASS |
| 弹框期间 `_dispatch` 立即拒绝（"AutoCAD 正被对话框阻塞"） | PASS |
| ESC-only 恢复（无 WM_CLOSE），探测回 False | PASS |
| 收尾 `CMDACTIVE=0 / CMDDIA=1 / FILEDIA=1 / OSMODE=0`，ping 通 | PASS |

离线：`uv run pytest -q` 78 passed；`compileall` 通过。

## 4. 实测勘误

`TSAVEAS` 弹出的「图形导出」对话框顶层窗口类名**实测为 `#32770`**（EnumWindows
按进程枚举可见），并非裸 HwndWrapper 顶层窗。原盲区的更可能成因是该对话框
**不在主 UI 线程**，`EnumThreadWindows(main_tid)` 枚举不到。新信号对此免疫。
（WPF 内容可能寄宿于 #32770 内，不影响结论。）

## 5. 影响

- 弹框命令误下发时不再等满 IPC 超时，立即获得明确错误信息；
- 误报风险已用基线断言覆盖：非模态面板不触发。
- 遗留：若用户主动打开对话框期间发起 MCP 调用，将收到阻塞错误——预期行为。
