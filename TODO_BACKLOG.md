# 执行清单 (TODO_BACKLOG)

> 生成日期: 2026-06-17
> 最后校准: 2026-07-24 (Handoff 39 / 门窗模式自动化)
> 依据: Handoff 33 真机证据 + tangent.py::LOW_CONFIDENCE_WARNINGS + docs/T20_COMMANDS.md
> 当前基线: 33 子命令有历史真机 E2E 证据, pytest 198 passed, EXECUTE_DISABLED_SUBCOMMANDS={}
> 进度: D1 / D2 / C1 / C2 / B1 / B2 / Handoff 38 / Handoff 39 均已闭合；
> B3 / A2 仅按触发条件重开

---

## 难度分级约定

| 等级 | 含义 | 工时估计 |
|---|---|---|
| D | 最易, 仅需用户配合 + 跑现成脚本 | < 0.5 天 |
| C | 容易, 文档/低风险代码, 不动 dispatcher | 0.5-1 天 |
| B | 中等, dialog_automation.py 首次扩展 | 1-3 天 |
| A | 困难, 机制不友好但理论可行 | >= 3 天 |
| S | 机制级不可自动化, 永久 STOPPED, 不要再投入工时 | - |

状态字段: OPEN 待做 / DEFERRED 无当前触发场景 / BLOCKED 等外部条件 / STOPPED 不再尝试

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

### B1 - TGColumn Gate B 控件映射封装  ✅ DONE (Handoff 36)

- 状态: DONE — 2026-07-02, `column` 子命令上线 (32→33), 项目首例面板 UI 自动化
- 证据: docs/handoff/36_tgcolumn_gate_b_close.md + 36_tgcolumn_gate_b_raw.txt
  + 36_tgcolumn_control_map.md (opencode 整理 Gate A raw, claude 复核)
- 真机结果 (itest_39 探针轮 + 库路径 E2E 轮, cleanup 全绿):
  - 五参数 (height/rotation/sec_w/sec_h/material) COM 读回精确匹配
    (超出原判据的三参数)
  - 实际形态与预设不同: 面板无 "确定" 按钮 (非模态即时生效式),
    落地走 命令行 WM_CHAR 打插入点, 退出走 ESC — bm_click 未用上
  - 关键机制: WM_SETTEXT + EN_KILLFOCUS 补发 / CB_SETCURSEL + CBN 补发;
    CMDACTIVE=1 窗口期严禁走 IPC
- API 落位: dialog_automation.py 通用原语 + drive_column_panel;
  tangent.execute_column 编排 (失败全路径 ESC+undo 回滚)
- 离线 171 → 183 passed (+12 column case)

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

### B3 - window 占位 + 延迟替换工作流

- 状态: **DEFERRED / OPTIONAL** — Handoff 39 已解决自动切换主流程；仅在需要“离线
  先布置占位、跨墙体修改后延迟绑定、最后统一替换”时重开
- 背景:
  - Handoff 33+34 只证明 COM/DXF 不能直接改 group71；Handoff 39 证明
    `ToolbarWindow32` 控件级 UI 自动化可以切换插门/插窗，旧 §S-4 结论已撤销
  - Handoff 38 的 group71 双向门禁与错误实体回滚继续作为最终安全层；
    `_opening_retry.py` 已改为自动调用核心 `execute_opening`
  - 因此 B3 不再承担“绕开人工面板”的职责，只保留“离线占位 + 延迟绑定”
    的独立工程价值
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
  2. **`tangent.window_replace` (新)** — 最终替换阶段批量绑定:
     - **preflight**: 复用 Handoff 39 自动切窗 + group71 最终门禁；
     - **替换循环**: ssget 拣回所有 PLACEHOLDER, 逐个 handent(wall_handle) 找墙
       (容忍墙体 STRETCH/MOVE/COPY 后的位置漂移), 在原位置插真天正窗,
       COM 注入 Width/Height/DoorSill, 校验 group71=1 + type=TCH_OPENING 后 erase 占位;
     - **失败容忍**: 墙已删除 → 跳过 + warn; 单条替换失败 → 单条回滚 + 占位保留, 不污染整批。
- 工程价值矩阵:
  | 维度 | 当前 Handoff 39 路径 | B3 占位+替换 |
  |---|---|---|
  | 切面板时机 | 每次请求前自动选择目标模式 | 最终替换阶段统一切换 |
  | 切错代价 | group71 门禁删除错误实体并结构化失败 | preflight 失败时保留占位 |
  | Agent UX | 按门阶段/窗阶段直接生成真实对象 | 先布置占位，最后统一替换 |
  | 跨墙变换 | 一调即定, 改墙后漂移 | xdata wall_handle 延迟绑定, 跟得上 |
- 风险:
  - preflight 探针实体如果 cleanup 不彻底, 会污染图纸 — 必须严格 try/finally + entity 计数对账
  - xdata App ID 需注册并持久化 — 注意跨重启的 (regapp ...) 调用
  - 替换过程的 "撤销/重做" 一致性 — 整批替换最好包在一对 (command "_undo" "_begin"/"_end") 里, 一键 undo 退回到全部占位状态
  - 现有 `tangent.window` 不删除, 保留兼容路径; 用户可以在 docstring 里看到二选一
- 闭合判据 (真机):
  - `itest_window_placeholder_smoke.py` — 单占位插入, xdata 读回校验, 撤销干净
  - `itest_window_replace_preflight.py` — 自动切窗 + group71 preflight + cleanup
  - `itest_window_replace_e2e.py` — 5 个占位批量替换, 全部 group71=1, 占位全部 erase
  - `itest_window_replace_wall_moved.py` — 占位插入后用 STRETCH 改墙, 替换仍能命中正确位置
  - `itest_window_replace_wall_deleted.py` — 墙删除后单条跳过 + warn, 其它占位继续
  - `itest_window_replace_undo.py` — 批量替换后单次 undo 回到全占位状态
  - 至少 8 个新 LISP/参数校验 pytest case
- 难度评估: B 级偏上, 估时 2~3 天 (介于 B1 与 A1 之间)
- 触发条件: 用户明确需要在不切换 T20 面板时先规划大量窗位，或要求墙体
  MOVE/STRETCH 后仍通过 wall_handle 延迟绑定；单纯批量插窗不触发 B3
- 落地顺序建议: B1 / B2 / Handoff 38 / Handoff 39 均已完成；只有满足上述触发条件才重开 B3
- 与旧 §S-4 关系: Handoff 39 已撤销“不可自动化”判定；B3 现在只是独立的延迟绑定功能

---

## A 级 - 困难但理论可行

### A1 - TRectAxis Gate B 矩形轴网封装  🛑 STOPPED (Handoff 37, 价值裁定)

- 状态: STOPPED — 2026-07-02, Gate B 机制打通但**不封装** (WON'T-SHIP)
- 证据: docs/handoff/37_rectaxis_gate_b_close.md + 37_rectaxis_gate_b_raw.txt
  + 37_trectaxis_control_map.md (opencode 整理, claude 复核)
- 机制侧 (全部真机 PASS, 复用 Handoff 36 范式):
  - bind: 选方向 radio + 键入 `个数*轴间距` (COUNT*SPACING) + Enter → 总开间/
    总进深联动; commit: **WM_COMMAND(IDOK)** 关框 (owner-draw 按钮点击全无效) →
    命令行打插入点 → 确定性落图 (3*3000+2*4500 稳定 7 根 LINE)
- **裁定原因 (非机制失败)**: TRectAxis 本配置产物 = 纯 LINE @ DOTE, **无 xdata /
  无 TCH_AXIS / 无轴号**, 与既有 axis_lines (entmake 纯 LINE) 同类。A1 原判据
  "生成 TCH_AXIS 系而非普通 LINE"前提被证伪 → 封装只得更慢更脆的 axis_lines,
  净负收益。需 DOTE 轴网直接 `axis_lines` + `layer="DOTE"`。
- 重启条件: 若发现 T20 有产 TCH_AXIS 的轴网命令 / 本命令有产轴号开关, 复用
  itest_41 机制重启。
- 排查经验: `"3000*2"` 被读成 3000 跨×2mm (COUNT*SPACING 语法) 曾致 3003 实体
  假象, 正确写法 `"3*3000"`; 封装前先验产物实体类型是否优于既有替代。

### A2 - WPF #32770 寄宿场景的通用守卫扩展

- 状态: **DEFERRED** — C2 已证伪当前 TSaveAs 的 WPF 假说，尚无真实 WPF 模态触发场景
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

### S-4 - 已撤销：门窗面板模式并非不可自动化

- Handoff 33+34 的窄结论仍成立：DXF group71 由面板决定，COM 不暴露直接 setter。
- Handoff 39 证明控件级 UI 自动化可达：强结构指纹定位 `ToolbarWindow32`，
  后台切换插门/插窗，空回车退出，再由 group71 最终验真。
- 因此门窗模式不再属于 S 级；真正的 S 级仍限于上面的强模态、entsel 和
  directive 硬尾巴命令。

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
        B1                               ✅ DONE (Handoff 36, 2026-07-02, column 上线)
            |
            v
        A1                               🛑 STOPPED (Handoff 37, 机制通但产物无增益, 不封装)
            |
            v
        Handoff 39                       ✅ DONE (门窗模式自动切换)
            |
            v
        B3 (DEFERRED, 仅占位/延迟绑定场景触发)
            |
            v
        A2 (DEFERRED)                    (WPF 假说已被 C2 证伪, 待真 WPF 模态出现)
```

> B3 不在主线必经路径上。Handoff 39 已覆盖常规门窗自动切换；只有需要占位、
> 跨墙修改后的延迟绑定和最终统一替换时才重开。

S 级不在路径上, 任何时候出现 "再试一次" 的诱惑请回看 Handoff 33。

---

## 每次改动前后必跑 (铁律)

```bash
uv run pytest -q                                   # 离线测试
python -m compileall -q src scripts tests          # 编译检查
git diff --check                                   # 行尾/空白
uv run python scripts/itest_19_mcp_stdio_smoke.py  # 9 tools 注册
uv run python scripts/itest_01_bringup.py          # 真机引导 (需 AutoCAD)
```

任意一项失败 -> 回滚到上一绿点, 不要带伤前进。
