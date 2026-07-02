# Handoff 36 — B1 闭合: TGColumn 面板 UI 自动化 (项目首例) + `column` 子命令上线

> 日期: 2026-07-02 · 环境: T20 V10 / AutoCAD 2024 (真机)
> 原始证据: docs/handoff/36_tgcolumn_gate_b_raw.txt (探针轮 + 库路径 E2E 轮)
> 控件映射: docs/handoff/36_tgcolumn_control_map.md (opencode 整理, claude 复核)

## 0. 一句话结论

**TGColumn 从"已移除/不可驱动"复活为 `column` 子命令。** 面板 UI 自动化
全链路真机打通: WM_SETTEXT 填参 + 命令行 WM_CHAR 打插入点 + ESC 退出,
五参数 COM 读回精确匹配。这是项目首个面板级自动化范式, 为 A1 (TRectAxis)
提供直接模板。

## 1. 历史结论的修正与保留

| 结论 | 状态 |
|---|---|
| "TGColumn vl-cmdf 点序列打不通" (Handoff 13/33) | **仍成立** — 本路线不走点序列 |
| "#32770 面板命令不可脚本驱动" | **修正** — 点序列不可达, **控件级可达** |
| 禁 WM_CLOSE / ESC-only 退出 | 不变, 全程遵守 |

## 2. 关键机制事实 (Gate A 推论 + Gate B 验证)

1. TGColumn 面板是**无标题 #32770 浮动面板, owner 不被 disable** (非阻塞);
   `vl-cmdf "TGCOLUMN"` 启动后 IPC 正常返回, CMDACTIVE=1 = 命令在等插入点。
2. 面板**没有 确定/取消 按钮** — 参数即时生效, 落地靠画布拾取/坐标输入。
3. **CMDACTIVE=1 窗口期严禁走 IPC** (dispatch 触发文本 `(c:mcp-dispatch)` 会被
   点提示吃掉); launch 之后到 ESC 之前只能纯 Win32。
4. 控件写入生效的组合 (缺一未测, 组合真机验证有效):
   - Edit: `WM_SETTEXT` + 回读校验 + 向父窗补发 `EN_KILLFOCUS` (MFC DDX 提交)
   - DROPDOWN Combo 子 Edit: 同上 + 以 combo 名义补发 `CBN_EDITCHANGE/CBN_KILLFOCUS`
   - DROPDOWNLIST Combo: `CB_SETCURSEL` + 补发 `CBN_SELENDOK/CBN_SELCHANGE`
5. 插入点用 `PostMessageW(command_hwnd, WM_CHAR, ...)` 打 "x,y" + 回车 —
   与 dispatcher 触发同机制, 面板浮起状态下命令行正常吃坐标。
6. 控件 hwnd 会话性, 每次运行按 **class + 标签锚点** 重新发现
   (定位规则见 36_tgcolumn_control_map.md §5)。

## 3. 真机证据摘要

探针轮 (原始 Win32 原语, 2026-07-02 11:16):

```
[locate] 初值: height=3000 rotation=0 sec=600x600
         材料=['金属','钢筋砼','混凝土','石材','毛石','砖','耐火砖'] cur=1
[set]    height/rotation/sec_w/sec_h/material 全部回读 True
[readback] TCH_COLUMN: Height=3300.0 Rotation=45.0 Width=500.0 Deep=400.0
           Style="金属"  (写入 3300/45/500/400/金属 → 五参数精确匹配)
cleanup: rounds=1 final=0 env 全复位 residual_modals=[]
```

TCH_COLUMN (TDbColumn) COM dump 共 62 属性, 关键可写项:
Height / Rotation / Width / Deep / Style(材料) / Elevation / ColumnNumber /
SectionShapeText(矩形) 等 — 完整清单见 raw 文件。

库路径 E2E 轮 (itest_39 重写为走 execute_column, 2026-07-02 11:23):

```
[PASS] full 五参数精确匹配 (H/R/W/D/S 六项 checks 全 True)
[PASS] minimal 仅坐标 (其余走面板记忆值)
[PASS] badmat ParamError 拒绝 (合法值清单回显, 不触面板)
```

## 4. 落地清单

- `src/t20_mcp/dialog_automation.py` — 新增通用原语 (get_window_text /
  set_edit_text / combo_items / combo_select / notify_combo_edit /
  all_descendants / post_escape / type_to_command_line / find_acad_popups)
  + TGColumn 专用 (COLUMN_MATERIALS / find_column_panel /
  locate_column_controls / drive_column_panel)。安全边界从"标题白名单"
  扩展为"标题白名单 或 结构指纹白名单 (含 title='柱高' 子面板)"。
- `src/t20_mcp/tools/tangent.py` — `column` 子命令 (32→33):
  `{x, y, height?, material?, rotation?, sec_w?, sec_h?}`;
  `_gen_column` 只产出启动 LISP (dry-run 可见), 真执行走 `execute_column`
  编排 (启动→drive→复位→delta/类型校验→五属性读回); 全失败路径 ESC+undo 回滚。
  T20 强制 COLUMN 图层, 故无 layer 参数。
- `scripts/itest_39_column_gate_b_e2e.py` — 库路径 E2E (full/minimal/badmat)。
- 离线测试 171 → **183 passed** (column 校验 12 case)。

## 5. 复跑命令

```bash
uv run python scripts/itest_39_column_gate_b_e2e.py   # 真机 E2E 三例
```

## 6. 对 backlog 的影响

- B1: **DONE** (本文档)。
- A1 (TRectAxis Gate B): 优先级上调 — 本范式直接可迁移 (面板发现/控件写入/
  通知补发原语全部复用), 差异点是动态开间行的状态机 + 真"确定"按钮 (bm_click)。
- 协作模式: Gate A raw → opencode 整理控件映射 → claude 复核+设计+真机攻坚,
  本轮验证有效, A1 沿用。
