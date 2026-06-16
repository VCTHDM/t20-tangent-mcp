# Handoff 13 — TGColumn (column) 真机复测：#32770 面板阻塞，降级为 dry-run

执行人：claude（接管 fable 角色）｜ 日期：2026-06-13 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg，acad.exe 启动于 14:36，同一会话）

> **结论先行**：Handoff 12 把 `column`（`TGColumn`）转正为「✅ E2E 验证」**是顺序依赖的假成功**。
> 本轮真机复测证实 `TGCOLUMN` **不能命令行驱动**——它弹 `#32770` 标准柱面板、命令保持
> `active=1`，`vl-cmdf` 喂入的点串到不了「绘图区放置」处理器，**0 实体**。已把 `column`
> 移入 `EXECUTE_DISABLED_SUBCOMMANDS`（与 `axis_grid`/`export_t3` 同类），仅 dry-run。

## 1. 复测怎么做的

1. `itest_01_bringup.py` → dispatcher 自 `%TEMP%` 引导，`ping=pong`，`CMDDIA/FILEDIA=1`，图面空。
2. `itest_30_column_e2e.py`（Handoff 12 留下的 E2E）→ **FAIL**：`entities 0->0 type='none'`。
3. `_probe_cmd.py tgcolumn`（Handoff 12 §2 说「4 组候选全成 delta=1」的同一脚本）
   → 现在 **4 组全部 delta=0 / newtype=none**。
4. 对照：同环境 `wall`（`TgWall`，命令行驱动）`count 0->1 type=TCH_WALL` **正常**
   → 排除「图面/IPC/dispatcher 退化」，问题是 **column 专属**。
5. 枚举 acad.exe 顶层窗口：`vl-cmdf "TGCOLUMN" "2000,2000"` 之后
   → `count` 不变、`CMDACTIVE=1`、**新出现 `#32770` 面板**（enabled=1，非模态）；
   取消（发空 `(command)`）后 `#32770` 消失、仍 0 实体。

## 2. 为什么 Handoff 12 会「看到」delta=1

`_probe_cmd.py` 在 `vl-cmdf` 之后调 `t20mcp:cancel-pending`（发空命令取消活动命令）
**再**读 `entlast`。`TGCOLUMN` 把命令留活动 + 开 `#32770` 面板；只有当**面板此前已被
某次探测打开并停在"放置"态**时，喂点才落柱。Handoff 12 那轮大概率是前序探测把面板
留开了，于是单点落柱、`active=0`、`delta=1`。新会话面板关着 → 首个 `TGCOLUMN` 只是
开面板，点串无处可去 → 0 实体。**这正是 README 铁律里「`vl-cmdf` 返回值会假成功，不可信」
+「同一命令 2 轮 0 实体即停手」要防的坑。**

## 3. 改了什么（本轮提交）

- `tangent.py`：`column` 加入 `EXECUTE_DISABLED_SUBCOMMANDS`；docstring/注释更新；
  execute=True 现返回 `execute 已禁用` 错误，dry-run 仍返回渲染后的 LISP + `execute_disabled`。
- `column.lsp`：头注释改为「仅 dry-run」，保留点序列骨架待 UI 自动化复用。
- README / `docs/T20_COMMANDS.md`：column 行 `✅ E2E` → `⛔ #32770 / 仅 dry-run`；
  完成度 ~50% → ~46%；待办 §2 修正。
- `scripts/itest_30_column_e2e.py` → 重写为 `scripts/itest_30_column_dialog_block.py`：
  断言（a）0 实体（b）命令 active（c）`#32770` 面板 +（对照）wall 正常。真机全 PASS。
- 离线 `uv run pytest -q` = **92 passed**（column 的 generate_lisp 渲染测试仍有效）。

## 4. 后续：要真正放置柱怎么办（未做，待决策）

`TGColumn` 与 `axis_grid` 同类——靠命令行点序列打不通。可选路线（均属探索性，需 claude 决策）：
1. **面板 UI 自动化**：`#32770` 标准柱面板里设参数后，**放置是绘图区点击**（不是按钮）。
   需 recon 面板控件 + 模拟绘图区指定坐标的点击（比 `dialog_automation` 现有的白名单
   `BM_CLICK` 难，后者只点按钮）。**严禁 `WM_CLOSE`**（铁律）。
2. **换命令**：查官方表是否有命令行版插柱 / 直接建 `TCH_COLUMN` 的 COM 构造
   （`tch10_com24.dll` 暴露 `TDbColumn`/`TColumnData`，见 research 2026-06-13 §7.3，
   但为内部符号，ActiveX 可达性需真机确证）。
3. **维持 dry-run**：把「插柱请人工操作」写进使用约定，和 axis_grid/export_t3 一致。

## 5. 给接手者

- TDimTP 已按本节建议改用 `wall` 构造被标注目标并封装为 `two_point_dimension`：
  三道短墙 (x=0/3000/6000, y=-600..600) + 穿越线 (-1000,0)->(7000,0) +
  标注位置 (3000,1500) 可稳定生成 `TCH_DIMENSION2`。对应模板为
  `src/t20_mcp/lisp_templates/tangent/two_point_dimension.lsp`，真机脚本为
  `scripts/itest_31_two_point_dimension_e2e.py`。
- TSWall 仍未推进，仍是 §4（疑似选择后弹框）。
- 2026-06-13 接力收尾：LOGFILEMODE 提示捕获法已转正为
  `scripts/itest_32_prompt_capture_log.py`；其余 `scripts/_probe_*.py` 临时探针已删除。
