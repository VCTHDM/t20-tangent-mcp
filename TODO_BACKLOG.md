# 执行清单 (TODO_BACKLOG)

> 生成日期: 2026-06-17
> 依据: Handoff 33 真机证据 + tangent.py::LOW_CONFIDENCE_WARNINGS + docs/T20_COMMANDS.md
> 当前基线: 32 子命令全部 E2E PASS, pytest 159 passed, EXECUTE_DISABLED_SUBCOMMANDS={}
> 进度: D1 / D2 / C1 / C2 已闭合 (Handoff 34, 2026-06-17)

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

### C1 - TRectAxis Gate A inventory 探针  ✅ DONE (Handoff 34)

- 状态: DONE — 2026-06-17
- 证据: docs/handoff/34_c1_c2_gate_a_close.md §1 + docs/handoff/34_trectaxis_gate_a_raw.txt
- 真机结果: itest_37 Exit=0, BLOCKED-by-#32770, 247 子控件全树, baseline/final entity_count = 0/0, ESC 干净
- 核心收获: SysTabControl32 含"直线轴网/弧线轴网"2 Tab + 内嵌 #32770 子页, A1 Gate B 的 Edit/Button 锚点已侦察

### C2 - TSaveAs / WPF 导出框 Gate A inventory  ✅ DONE (Handoff 34, WPF 假说证伪)

- 状态: DONE — 2026-06-17
- 证据: docs/handoff/34_c1_c2_gate_a_close.md §2 + docs/handoff/34_tsaveas_gate_a_raw.txt
- 真机结果: itest_38 Exit=0, BLOCKED-Win32-modal, 37 子控件, **WPF 子控件数 = 0** (证伪 WPF 内嵌假说)
- 重要发现: TSaveAs 是纯经典 Win32 (Static/Button/ComboBox/SHELLDLL_DefView/SysListView32/ToolbarWindow32), FILEDIA=0 仍弹, owner_disabled=True 真模态, ESC-only 路线可干净退出
- 影响: A2 优先级可下调 (WPF 通用守卫的真实落地点暂无, 待未来真 WPF 模态出现再做)

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

### B2 - drawing_name / arrow / elevation 文本 COM 注入评估  ✅ DONE (Handoff 35)

- 状态: DONE — 2026-07-02, 结论: **三命令全部可注入** (S-4 候补判定被证伪)
- 证据: docs/handoff/35_label_text_com_probe.md + 35_label_com_raw.txt
- 真机结果 (itest_40 probe all + inject 两轮, cleanup 全绿):
  - drawing_name: NameText/ScaleText 可写 (IComDrawingName)
  - arrow: Text(上标)/Text2(下标) 可写 (IComSymbArrow)
  - elevation: Text 可写, 覆盖自动计算标高文字 (IComSymbElev)
  - 样式类属性 (NameStyle/ScaleStyle/FontStyle) put ERR, 仍走面板
- 超范围加成: 三子命令的文本参数已一并封装上线
  (name_text/scale_text, text/text2, text), 离线 159 → 171 passed,
  inject E2E 中文读回精确匹配
- 方法论: LOGFILEMODE 捕获 vlax-dump-object (中文版段落标记是 ";特性值:");
  其它"取面板记忆值"命令 (balcony/step/ramp/insight/tree...) 未来可同法评估

### B3 - window 占位 + 切面板后替换 工作流 (绕开 §S-4 面板锁死的工程方案)

- 状态: OPEN — 设计草稿 (用户提出于 2026-06-17 会话, 经 ZCode 评估可行)
- 背景:
  - §S-4 "面板记忆值锁死" 是机制级永久无解 (COM/DXF/PostMessage 均失败, Handoff 33+34 已三方证伪)
  - 但本方案不"破解"机制, 而是把"切面板"这一人工动作从 N 次 (每次 window 调用前)
    降到整个会话 1 次, 让 LLM agent 可以 fire-and-forget 批量画窗占位, 用户随后一键替换
  - 工程价值: 50 个 window 的会话工效提升约 50x, 是 agent 自动化场景刚需
- 设计 (双子命令工作流):
  1. **`tangent.window_placeholder` (新)** — 不依赖面板状态:
     - 用 COM 在墙上插占位"临时块" (自定义图层 `T20MCP_PLACEHOLDER_WINDOW`)
     - 块定义: 窗洞虚线矩形 + `W=xxxx` 文字标注 (用户肉眼可辨)
     - xdata schema (App ID `T20MCP_WIN`, v1):
       ```
       1001 "T20MCP_WIN"
       1000 "v1"                ; schema version
       1011 (ins_x ins_y 0)     ; 插入点世界坐标
       1040 width
       1040 height
       1040 sill_height
       1005 wall_handle         ; 墙的 entity handle (跨命令稳定)
       1000 layer_name          ; 用户指定图层
       ```
  2. **`tangent.window_replace` (新)** — 必须人工切窗模式后调用:
     - **preflight**: 屏幕外 (-100000, -100000) 偷偷建临时墙 + TOpening 探针,
       读 DXF group 71; ≠1 立即报警 "请先切窗模式" + SKIP, 探针整组 undo;
     - **替换循环**: ssget 拣回所有 PLACEHOLDER, 逐个 handent(wall_handle) 找墙
       (容忍墙体 STRETCH/MOVE/COPY 后的位置漂移), 在原位置插真天正窗,
       COM 注入 Width/Height/DoorSill, 校验 group71=1 + type=TCH_OPENING 后 erase 占位;
     - **失败容忍**: 墙已删除 → 跳过 + warn; 单条替换失败 → 单条回滚 + 占位保留, 不污染整批。
- 工程价值矩阵:
  | 维度 | 现状 (直接 tangent.window) | B3 占位+替换 |
  |---|---|---|
  | 切面板时机 | 每次调用前 | 整会话 1 次 |
  | 切错代价 | 沉默生成门 (现 SKIP 兜底) | preflight 报警, 显性 |
  | Agent UX | 每个窗都要停下来求人 | 批量画占位, 最后一键替换 |
  | 跨墙变换 | 一调即定, 改墙后漂移 | xdata wall_handle 延迟绑定, 跟得上 |
- 风险:
  - preflight 探针实体如果 cleanup 不彻底, 会污染图纸 — 必须严格 try/finally + entity 计数对账
  - xdata App ID 需注册并持久化 — 注意跨重启的 (regapp ...) 调用
  - 替换过程的 "撤销/重做" 一致性 — 整批替换最好包在一对 (command "_undo" "_begin"/"_end") 里, 一键 undo 退回到全部占位状态
  - 现有 `tangent.window` 不删除, 保留兼容路径; 用户可以在 docstring 里看到二选一
- 闭合判据 (真机):
  - itest_41_window_placeholder_smoke.py — 单占位插入, xdata 读回校验, 撤销干净
  - itest_42_window_replace_preflight.py — preflight 探针在门模式正确报警 + cleanup 干净
  - itest_43_window_replace_e2e.py — 切窗模式后 5 个占位批量替换, 全部 group71=1, 占位全部 erase
  - itest_44_window_replace_wall_moved.py — 占位插入后用 STRETCH 改墙, 替换仍能命中正确位置
  - itest_45_window_replace_wall_deleted.py — 墙删除后单条跳过 + warn, 其它占位继续
  - itest_46_window_replace_undo.py — 批量替换后单次 undo 回到全占位状态
  - 至少 8 个新 LISP/参数校验 pytest case
- 难度评估: B 级偏上, 估时 2~3 天 (介于 B1 与 A1 之间)
- 触发条件: 当用户开始让 agent 频繁调用 window (例如布置户型批量窗) 时优先级上升;
  当前如果只是手动单次, 现有"切一次面板就别关"路径已够用, 不需要 B3
- 落地顺序建议: B2 (低风险 COM 评估) -> B1 (TGColumn Gate B 范式) -> B3 (复用 B1 的 xdata + 块工具链)
- 与 §S-4 关系: 本方案 **不修改 §S-4 判定** (机制级结论保持 STOPPED), B3 是工程绕道, 不是机制突破

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
- ~~drawing_name / arrow / elevation 的文本~~ — B2 证伪 (Handoff 35):
  三命令文本全部 COM 可注入, 已参数化上线; S-4 仅剩门/窗模式切换一项

---

## 推荐推进顺序

```
D1  ->  D2                              ✅ DONE (Handoff 34, 2026-06-17)
            |
            v
        C1 + C2                          ✅ DONE (Handoff 34, 2026-06-17)
            |
            v
        B2                               ✅ DONE (Handoff 35, 2026-07-02, 结论: 可注入+已封装)
            |
            v
        B1                               (TGColumn Gate B, 首次面板自动化范式) <-- 当前
            |
            v
        B3 (可选, agent 批量化场景触发)  (window 占位+替换 工作流)
            |
            v
        A1  ->  A2                       (A2 的 WPF 假说已被 C2 证伪, 优先级可下调)
```

> B3 不在主线必经路径上, 仅当用户开始用 agent 批量化插窗 (如户型一次 50+ 扇)
> 时才触发推进; 个人手工流可继续走"切一次面板就别关"。

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
