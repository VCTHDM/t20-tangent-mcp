# 执行清单 (TODO_BACKLOG)

> 生成日期: 2026-06-17
> 依据: Handoff 33 真机证据 + tangent.py::LOW_CONFIDENCE_WARNINGS + docs/T20_COMMANDS.md
> 当前基线: 32 子命令全部 E2E PASS, pytest 159 passed, EXECUTE_DISABLED_SUBCOMMANDS={}
> 进度: D1 / D2 已闭合 (Handoff 34, 2026-06-17)

---

## 难度分级约定

| 等级 | 含义 | 工时估计 |
|---|---|---|
| D | 最易, 仅需用户配合 + 跑现成脚本 | < 0.5 天 |
| C | 容易, 文档/低风险代码, 不动 dispatcher | 0.5-1 天 |
| B | 中等, dialog_automation.py 首次扩展 | 1-3 天 |
| A | 困难, 机制不友好但理论可行 | >= 3 天 |
| S | 机制级不可自动化, 永久 STOPPED, 不要再投入工时 | - |

状态字段: OPEN 待做 / BLOCKED 等外部条件 / STOPPED 不再尝试

---

## D 级 - 仅需用户配合一次

### D1 - window 窗模式 SillHeight 真机闭合复测  ✅ DONE (Handoff 34)

- 状态: DONE — 2026-06-17
- 证据: docs/handoff/34_window_sillheight_close.md
- 真机结果: itest_35 window Exit=0 (group71=1, DS=900 精确), sweep DS=600/1200/300 三组全 PASS, cleanup 全绿
- 顺带修复: itest_35 preflight 字符串比较 bug (`if g71_val not in (1, "1")`)

### D2 - README / T20_COMMANDS.md 同步窗模式结论  ✅ DONE (Handoff 34)

- 状态: DONE — 2026-06-17
- 证据: docs/handoff/34_window_sillheight_close.md §5
- 改动:
  - tangent.py::LOW_CONFIDENCE_WARNINGS["window"] 补 Handoff 34 sweep 三参数表述
  - docs/T20_COMMANDS.md 1.1 门窗行 中→高 (注明 Handoff 33/34) + 2.x 窗模式切换行更新
  - README.md line 70 保留原文 (人工前提不可消除) + line 102 新增 Handoff 34 条目
- 闭合: pytest 159 passed / compileall 静默 / itest_19 + itest_01 全 PASS

---

## C 级 - 文档/低风险代码

### C1 - TRectAxis Gate A inventory 探针

- 状态: OPEN
- 参考: scripts/itest_36_column_gate_a_inventory.py (TGColumn 范式)
- 要求: inventory-only, 严格 ESC-only, 不点击不填框
- 产出:
  - scripts/itest_37_trectaxis_gate_a_inventory.py
  - docs/handoff/34_trectaxis_gate_a_raw.txt
- 闭合判据: entity_count 调用前后均为 0, remaining_#32770_modals=[]

### C2 - TSaveAs / WPF 导出框 Gate A inventory

- 状态: OPEN
- 背景: Handoff 09 记录顶层类名为 #32770 (WPF 寄宿其中); Handoff 33 的 TGColumn 全经典 Win32, 需要 Gate A 一次性证伪/证实 TSaveAs 是否真有 WPF 内嵌
- 产出:
  - scripts/itest_38_tsaveas_gate_a_inventory.py
  - docs/handoff/34_tsaveas_gate_a_raw.txt
- 风险: 若误关 ARX 对话框会导致 AutoCAD 致命崩溃 - 严禁 WM_CLOSE, 仅 ESC

---

## B 级 - dialog_automation.py 首次扩展

### B1 - TGColumn Gate B 控件映射封装

- 状态: OPEN
- 依据: docs/handoff/33_tgcolumn_gate_a_raw.txt (556 子控件 inventory 已就绪)
- 范围: 选取最小可用控件子集 - 柱高 Edit / 材料 Combo / 转角 Edit / "确定" Button
- 新增 API (src/t20_mcp/dialog_automation.py):
  - set_edit_text(hwnd, text) - WM_SETTEXT + 校验回读
  - bm_click(hwnd) - 模拟按钮点击, 不发 WM_CLOSE
- 新增子命令 tangent column: {x, y, height?, material?, rotation?, layer?}
- 闭合判据:
  - 真机生成 1 个 TCH_COLUMN
  - 三参数从面板取值后 COM 读回精确匹配
  - ESC-only 恢复 100% 干净
  - pytest 新增至少 4 个 LISP/参数校验离线 case
- 产出: scripts/itest_39_column_gate_b_e2e.py + Handoff 35 文档
- 回退预案: 任一控件 BM_CLICK/WM_SETTEXT 失败 -> 立即 ESC + 回滚至 EXECUTE_DISABLED

### B2 - drawing_name / arrow / elevation 文本 COM 注入评估

- 状态: OPEN
- 背景: 当前面板记忆值不可参数化, 已带 warning
- 行动:
  1. 用 vlax-dump-object 枚举 TCH_DRAWINGNAME / TCH_ARROW / TCH_ELEVATION 的 COM 属性
  2. 若暴露 Text / Style / Scale 等 -> 真机 vlax-put-property 验证写入
  3. 若全部返回 vl-catch-all-error -> 该项降为 S 级 (面板锁死)
- 产出: scripts/itest_40_label_text_com_probe.py + 决策记录
- 闭合判据: 三命令各自得出二选一结论 (可注入 / 永久 STOPPED)

---

## A 级 - 困难但理论可行

### A1 - TRectAxis Gate B 矩形轴网封装

- 状态: OPEN (依赖 C1)
- 范围: 参数面板 -> 开间/进深字符串拼接 -> "确定" BM_CLICK 端到端
- 复杂度高于 B1 原因: 参数面板含动态行 (开间数量可变), 需要状态机判断 "添加行"/"删除行" 按钮序列
- 新增子命令 tangent rect_axis: {base_x, base_y, h_spacings:[..], v_spacings:[..], layer?}
- 闭合判据: 真机生成天正智能轴网 (而非 axis_lines 的普通 LINE 替代), 实体类型为 TCH_AXIS 系列
- 回退预案: 失败则保留 axis_lines 普通线轴网替代路径不动

### A2 - WPF #32770 寄宿场景的通用守卫扩展

- 状态: OPEN (依赖 C2 / A1 触发)
- 背景: 当前 file_ipc.py 弹框守卫针对外层 #32770; Handoff 09 的 "主窗口 IsWindowEnabled" 信号是单点修复
- 行动: 把 IsWindowEnabled 信号上升为统一的恢复路径分支, 覆盖 WPF 内嵌寄宿
- 闭合判据: itest_19 stdio smoke + itest_e2e_suite 全绿, 新增 WPF 守卫专项 itest 通过
- 风险: 触碰 file_ipc.py 编码链 / 弹框守卫核心, 必须在专门分支推进

---

## S 级 - 机制级不可自动化 · 永久 STOPPED

严禁再次尝试封装。证据全部在 Handoff 33。

### S-1 - 强制模态 + 无 silent 形态

| 命令 | 证据来源 |
|---|---|
| TPartSaveAs (局部导出) | Handoff 33 §1: selection-first 后 FILEDIA=0 仍弹 #32770 "图形导出" 强制模态 |
| TSaveAs (整图导出) | Handoff 09: 天正自绘导出框无视 FILEDIA=0 |
| export_t3 / TGetXML | 同族 |

### S-2 - entsel / 选择注入族 (不接受坐标)

| 命令 | 证据 |
|---|---|
| TSingleAxisDim | Handoff 33 §2: 0,0 在命令退出后被命令行接到, 提示 "未知命令 0,0" |
| TLeader / TPointIndex / TSectIndex | 同族 selection-injection |
| TDimRad / TDimDia / TDimAng / TDimArc | 半径/直径/角度/弧长标注, 均 entsel 风格 |

### S-3 - directive 硬尾巴

TBlkMask1 / WIPEOUT / TGirDer / TWINDROSE / TSlab / TElevator / TDrawParallelStair

### S-4 - 面板记忆值锁死 (参数化无解)

- door / window 的门/窗模式切换 - DXF group 71 由面板决定, COM 不暴露
- drawing_name / arrow / elevation 的文本 - 待 B2 评估; 若 B2 全 ERR 则正式落入此级

---

## 推荐推进顺序

```
D1  ->  D2                              ✅ DONE (Handoff 34, 2026-06-17)
            |
            v
        C1 + C2                          (两份 inventory, 并行可做) <-- 当前
            |
            v
        B2                               (低风险 COM 探针, 二选一即结案)
            |
            v
        B1                               (TGColumn Gate B, 首次面板自动化范式)
            |
            v
        A1  ->  A2                       (TRectAxis 全流程 + WPF 通用守卫)
```

S 级不在路径上, 任何时候出现 "再试一次" 的诱惑请回看 Handoff 33。

---

## 每次改动前后必跑 (铁律)

```bash
uv run pytest -q                                   # 离线 150 case
python -m compileall -q src scripts tests          # 编译检查
git diff --check                                   # 行尾/空白
uv run python scripts/itest_19_mcp_stdio_smoke.py  # 9 tools 注册
uv run python scripts/itest_01_bringup.py          # 真机引导 (需 AutoCAD)
```

任意一项失败 -> 回滚到上一绿点, 不要带伤前进。
