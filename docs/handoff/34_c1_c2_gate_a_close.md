# Handoff 34 — C1/C2 Gate A inventory 闭合

> 日期: 2026-06-17
> 关联: TODO_BACKLOG.md §C1 (TRectAxis) + §C2 (TSaveAs)
> 接续: docs/handoff/34_window_sillheight_close.md (D1/D2)
> 状态: PASS — C1/C2 双双闭合, 可启动 B 级

## 0. TL;DR

| 探针 | 入口 | 结论 | exit | 子控件 | WPF? |
|---|---|---|---|---|---|
| C1 | itest_37_trectaxis_gate_a_inventory.py | BLOCKED-by-#32770 | 0 | 247 | n/a |
| C2 | itest_38_tsaveas_gate_a_inventory.py | BLOCKED-Win32-modal | 0 | 37 | NO 证伪 |

**关键发现**: TSaveAs 不是 WPF 寄宿, 是纯经典 Win32 文件保存对话框
(Static / Button / ComboBox / SHELLDLL_DefView / SysListView32 /
ToolbarWindow32 / ComboBoxEx32 / Edit)。这与 Handoff 09 顶层 #32770 一致,
但**否定了任务书 §C2 "WPF 内嵌"假说**, 直接影响 A2 优先级。

完整子控件树见:
- `docs/handoff/34_trectaxis_gate_a_raw.txt` (34 KB, 247 ctrl)
- `docs/handoff/34_tsaveas_gate_a_raw.txt` (6 KB, 37 ctrl)

## 1. C1 — TRectAxis Gate A inventory

verdict (任务书 §C1 闭合判据):
```
TRectAxis 弹 #32770 面板                    : YES
ESC 后无残留模态 (remaining_#32770=[])       : YES
环境恢复 (CMDACTIVE=0)                       : YES
无实体生成 (entity delta=0)                  : YES
baseline / final entity_count = 0 / 0
-> 结论: BLOCKED-by-#32770 (Gate A inventory captured)
```

顶层模态: hwnd=5374562, class=#32770, title=空, owner_hwnd=657366 (主窗),
owner_disabled=False (表面 modeless, 实际占用命令行通道), 247 子控件,
SysTabControl32 含"直线轴网"/"弧线轴网" 2 Tab + 多个内嵌 #32770 子页。

A1 (Gate B) 关键控件锚点 (raw 子树证实存在):
- Static 标签: 上开/下开/左进/右进 (参数列表方向)
- Edit: 开间/进深字符串输入
- Button: 添加行/删除行 (任务书"动态行状态机"), 确定/取消

控件量级 247 (vs itest_36 TGColumn 556), A1 工作量介于 B1 与更复杂任务之间。

## 2. C2 — TSaveAs Gate A inventory

verdict:
```
TSaveAs 弹 #32770                            : YES
WPF 内嵌存在 (HwndWrapper/...)               : no   ← 关键证伪
FILEDIA=0 未拦住模态                         : YES
ESC 后无残留 (modal+top)                     : YES
环境恢复 (CMDACTIVE=0)                       : YES
无实体生成 (entity delta=0)                  : YES
baseline / final entity_count = 0 / 0
-> 结论: BLOCKED-Win32-modal
```

顶层模态: hwnd=2887390, class=#32770, title="图形导出", owner_hwnd=657366,
owner_disabled=**True** (真模态, 主窗禁用), 37 子控件, **WPF 子控件数 = 0**。

关键控件 (raw):
- Static "保存在(&I):"
- ComboBox 目录下拉, 文件名 ComboBox/Edit, "保存类型", "CAD版本", "导出内容"
- ToolbarWindow32 (导航条)
- SHELLDLL_DefView + SysListView32 (文件列表)
- Button "保存(&S)", "取消" (IDCANCEL=2)

重要安全发现:
- owner_disabled=True 与 Handoff 09 "主窗口 IsWindowEnabled=False"
  信号对齐, A2 守卫扩展依据进一步强化。
- `[launch] ok=False Timeout` 是 modal 接管命令行的副作用, 不是 bug
  (任务书 §S-1 强制模态典型表现)。
- ESC 6 轮 PostMessage 干净退出, 主窗 enabled 恢复, env 全部归位 —
  ESC-only 路线对 TSaveAs **可行**。WM_CLOSE 仍禁止 (Handoff 09)。

§S-1 回填:
- TSaveAs (整图导出): 本次已 Gate A 证伪 WPF, 仍 BLOCKED-Win32-modal,
  STOPPED 不变。

## 3. 对 TODO_BACKLOG 推进路径的影响

```
D1 -> D2     DONE (上一份 Handoff 34, commit 46575e1)
        |
        v
   C1 + C2   DONE (本份)
        |
        v
   B2        <-- 下一轮: COM 文本注入二选一
        |
        v
   B1        (TGColumn Gate B)
        |
        v
   A1 -> A2  (A2 的 WPF 假说已证伪, 优先级可下调)
```

A2 优先级建议下调: 任务书 §A2 原始假设是 TSaveAs WPF 寄宿; C2 证伪后,
A2 "IsWindowEnabled 信号统一恢复路径分支"仍有意义 (覆盖未来未知真 WPF
模态), 但**触发场景待验证**, 不再阻塞。建议 B1/A1 过程中遇到具体 WPF
模态再回头做 A2, 不预先空转。

## 4. 资产清单

| 文件 | 用途 |
|---|---|
| scripts/itest_37_trectaxis_gate_a_inventory.py | C1 探针, ESC-only |
| scripts/itest_38_tsaveas_gate_a_inventory.py | C2 探针, ESC-only + FILEDIA=0 + WPF 检测 |
| docs/handoff/34_trectaxis_gate_a_raw.txt | C1 真机日志 (247 控件全树) |
| docs/handoff/34_tsaveas_gate_a_raw.txt | C2 真机日志 (37 控件全树) |
| docs/handoff/34_c1_c2_gate_a_close.md | 本文 |

src/t20_mcp/ 与 tests/ 完全没动, pytest 不需要变更。

## 5. 经验回填

- Gate A 探针的"timeout 不是 bug"原则: 模态弹出后 dispatcher 等不到 LISP
  返回是正常的; 判定要看实际窗口枚举与 entity_count, 不被
  `[launch] ok=False Timeout` 误导。
- ESC vs IDCANCEL/WM_CLOSE 安全分级:
  - ESC PostMessage: Windows 标准对话框关闭信号, 全部 #32770 都接受, 首选。
  - WM_COMMAND IDCANCEL: 等价点取消按钮, 仅白名单标题安全 (itest_11
    KNOWN_CANCELABLE_TITLES), 非白名单强发风险高。
  - WM_CLOSE: ARX 致命崩溃 (Handoff 09), 永久禁止。
- WPF 检测三关键词: HwndWrapper (WPF 主窗类前缀) / System.Windows.*
  (PresentationFramework 内部类) / Microsoft.* (XAML 自定义类)。
  三者都不命中 = 经典 Win32。
