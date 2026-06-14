# Handoff 27 — double_stair / multi_stair 整体楼梯封装 + 简单候选耗尽确认

执行者: Claude Code lead（主环境亲跑 7 步真机循环），Codex 离线 triage 并行辅助
日期: 2026-06-14
环境: 真机 T20 V10 / AutoCAD 2024（execute=True 真机 E2E）

## 结论

本轮新封 **2 个整体楼梯子命令**（真机 E2E 通过）：

| 子命令 | 命令 | 序列 | 实体 |
|---|---|---|---|
| `double_stair` | `TRStair` | 插入点 → 回车退出循环 | `TCH_RECTSTAIR` |
| `multi_stair` | `TMultiStair` | 起点 → 下一点 → 回车（在"起点<退出>"处空回车收尾） | `TCH_MULTISTAIR` |

跑数/梯段宽/踏步数/楼梯高等构造参数走天正面板记忆值，模板只参数化插入点/方向点
（沿用 line_stair/arc_stair 的"面板记忆值 + 点序列"路线）。

**并且确认：剩余官方命令里的「简单点序列可封」候选已基本耗尽。** 本轮把整张
454 命令表中尚未封装/未探测的候选系统性扫了一遍（codex 离线 triage + claude 真机
侦察），可封的只剩这 2 个整体楼梯。

## Codex 并行分工（离线）

Codex（GPT CLI，`-s workspace-write`，禁真机/禁测试/禁 commit）产出
`docs/research/2026-06-14_remaining_simple_candidates.md`：把全表 454 条对照已封装
31 + 已拒 12，按语义分类（纯造点序列 / 需选已有对象 / 必弹对话框 / 修改已有实体 /
未知），给出 22 条名义候选 + 5 条「强候选」。claude 据此真机侦察，结论见下。

## 真机侦察结果（scripts/itest_42_candidate_recon.py）

新增可复用侦察 harness：最小点序列试驱动 + 实体增量/entlast 类型 + 运行后 CMDACTIVE +
**逐条 ESC 弹框恢复**（绝不 WM_CLOSE，沿用 09/13 崩溃教训），一条命令弹框不会污染整批。

| 命令 | 中文 | 结果 | 处置 |
|---|---|---|---|
| `TRStair` | 双跑楼梯 | delta=1, `TCH_RECTSTAIR`, active=0 | ✅ 封装 `double_stair` |
| `TMultiStair` | 多跑楼梯 | delta=1, `TCH_MULTISTAIR`, active=0（起点→下一点→回车） | ✅ 封装 `multi_stair` |
| `TDrawParallelStair` 等 7 条 Draw 族 | 双分/转角/三跑/交叉/剪刀/三角/自动扶梯 | **先弹 #32770 模态参数面板**（实测"双分平行楼梯"框） | ❌ 墙2 死路，同 column |
| `TGirDer` | 绘制梁 | 两点 0 实体，clean exit（需依附墙/柱/轴线） | ❌ 前置重，非简单 |
| `TWINDROSE` | 风玫瑰 | 弹"风玫瑰"模态框 | ❌ 墙2 死路 |

> 侦察踩坑：Draw 族楼梯弹模态框且 `(command)` 空回车无法关 ARX 模态框，曾使整批
> 后续命令级联"被对话框阻塞"。已用 ESC（PostMessage VK_ESCAPE 给弹窗+主窗）恢复，
> 并把该恢复逻辑固化进 itest_42，后续侦察自带防污染。

## 改动

- 新增模板 `src/t20_mcp/lisp_templates/tangent/double_stair.lsp`、`multi_stair.lsp`
- `src/t20_mcp/tools/tangent.py`：新增 `_gen_double_stair` / `_gen_multi_stair` 并注册
- `tests/test_tangent_lisp_gen.py`：`VALID_CASES` 增 2 条
- 新增 `scripts/itest_42_candidate_recon.py`（候选批量侦察 + 弹框恢复）、
  `scripts/itest_43_double_multi_stair_e2e.py`（真机 E2E 验收）
- `docs/T20_COMMANDS.md`：§1.1/§1.2/§2 更新 2 胜者 + 楼梯 Draw 族/梁/风玫瑰拒收记录
- `docs/research/2026-06-14_remaining_simple_candidates.md`（codex triage 产出）
- `README.md`：文档索引 + itest 范围 `itest_01..43`

## 验证

```powershell
uv run pytest -q tests/test_tangent_lisp_gen.py   # 140 passed
uv run pytest -q                                   # 159 passed
uv run python -X utf8 scripts/itest_43_double_multi_stair_e2e.py
#   double_stair : PASS (count 0->1, TCH_RECTSTAIR)
#   multi_stair  : PASS (count 0->1, TCH_MULTISTAIR)
#   清理还原: PASS (final_count=0)
```

## 安全边界

- 仅对已侦察「命令行点序列、无选对象步、无对话框」的命令开 execute。
- 弹框命令一律 ESC 恢复，**绝不 WM_CLOSE 天正 ARX 框**。
- Codex 全程离线：不碰真机、不跑测试、不碰 .venv/uv、不 commit。

## Next（转硬骨头）

简单候选已耗尽。剩下都是「硬骨头」，按性价比排：
1. **门窗面板路线**：window 窗模式免人工（WPF 面板 UI 自动化），或 door/window 类型
   参数化注入。
2. **#32770 面板放置类**：column（标准柱）/ 楼梯 Draw 族 / axis_grid 的 UI 自动化
   （控件 ID 映射 + 绘图区坐标点击），高风险高工作量。
3. **export_t3**：WPF 导出框 UI 自动化或 TPartSaveAs/TGetXML 替代评估。
