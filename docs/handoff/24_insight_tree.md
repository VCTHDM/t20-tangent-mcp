# Handoff 24 — insight / tree 单点插入构件封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

延续「命令行点序列、无对话框、无选对象步」目标，一轮 E2E 拿下两个单点插入构件：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `insight` | `TInsight` | 标注位置点→回车退出循环 | 0 | `TCH_TDBINSIGHT` |
| `tree` | `TSingleTree` | 插入点→回车退出循环 | 0 | `INSERT`（树木图块, 块名形如 `tree1`） |

两者均为循环式单点插入（每点一个，给完点回到"位置"提示，补一个空回车退出，同 `ramp` 模式）。
`insight` 朝向/编号、`tree` 树种/尺寸均走天正面板记忆值，本工具只参数化插入点。
`tree` 是普通图块，实体类型为通用 `INSERT`（块名 `tree1` 确认是树块，但块名随面板选择
变化，E2E 只断言类型 `INSERT` + 实体增量，不硬断言块名）。

## 真机探测

1. itest_32 空输入提示流（均无弹框、无选对象）：
   - `TSINGLETREE` → 「请点取插入点<退出>」。
   - `TINSIGHT` → 「请点取标注位置<退出>」（循环，每点一个）。
   - `TPOINTINDEX`/`TSECTINDEX` → 「请给出索引节点的位置<退出>」。
2. 点序列试驱动 + entlast 读回（临时探针，用后即删）：
   - `TINSIGHT`：`(pt 0 0) ""` → active=0, count 0→1, `TCH_TDBINSIGHT`，干净。
     （`(p1 p2 "")` 实测 0→2，证实是单点循环放置。）
   - `TSINGLETREE`：`(pt 0 0) ""` → active=0, count 0→1, `INSERT` 块名 `tree1`，干净。
   - 冷态复测 final_count=0。

## 同轮探测但暂不封装（留坑记录）

- **指向索引 `TPointIndex` / 剖切索引 `TSectIndex`**：索引节点位置→参考点后需输入编号文字，
  `(p1 p2 "" "")` 空回车序列 0 实体；属文字依赖类（同 `TLeader`），暂搁置。

## 改动

- `src/t20_mcp/lisp_templates/tangent/{insight,tree}.lsp` — 新模板。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_insight` / `_gen_tree` 与 `_GENERATORS` 注册；
  - 工具 docstring 子命令清单补两行。
- `tests/test_tangent_lisp_gen.py` — VALID_CASES、单点+回车注入断言、缺坐标拒绝断言。
- `scripts/itest_40_insight_tree_e2e.py` — 新增可重复真机 E2E（两命令 + 环境还原）。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态表、子命令表、坑清单；完成度 ~66% → ~68%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_40_insight_tree_e2e.py
# insight/tree 全 PASS; entlast 类型符合; 清理还原 PASS (final_count=0)

uv run pytest -q
# 145 passed

uv run python -m compileall -q src scripts tests
# PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未对任何对话框做强关。探测散落实体
均经受控 UNDO 清空至 0；临时探针脚本（_probe_d/_probe_e.py）已删除。

## 下一步候选

1. 继续薅单点/点序列插入类（先 itest_32 探提示流再判，避开选对象步、#32770 面板、
   内联文字编辑）。候选方向：场地/总图构件（车位、布树成片）、立面构件库等。
2. **文字依赖类的统一处理**（索引/引出/做法标注）：研究编号文字能否经命令行参数或
   COM 注入绕开内联编辑器；通则一开可批量解锁一批标注。
3. **选择对象步注入通则**（硬骨头，多轮搁置）：坡屋顶/平板/竖板/散水/标注族。
