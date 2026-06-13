# Handoff 19 — symmetry / north_arrow / break_line 三符号标注封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

按封装方法论五步管线，一轮 E2E 拿下三个符号标注命令，全部无对话框、命令行点序列可干净收尾：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `symmetry` | `TSymmetry` | 起点→终点 | 0 | `TCH_SYMMETRY` |
| `north_arrow` | `TNorthThumb` | 位置点→方向点 | 0 | `TCH_NORTHTHUMB` |
| `break_line` | `TSymbCut` | 起点→终点→回车 | 0 | `TCH_RUPTURE` |

`break_line` 比另两个多一步：两点后命令仍 active 并问“选择保留范围 `<不切割>`”，
必须补一个空回车接受默认才收尾（模板内尾随 `""`，同 `coordinate`）。

## 真机探测（itest_32 提示捕获）

1. 空输入捕获首个提示（均无 `#32770` 弹框，命令行驱动）：

```text
TSYMBCUT     点取折断线起点或 [选多段线(S)\绘双折断线(Q)，当前：绘单折断线]<退出>:
TSYMMETRY    起点或 [参考点(R)]<退出>:
TNORTHTHUMB  指北针位置<退出>:
```

2. 两点驱动捕获完整序列：

```text
TSYMMETRY    起点→终点 → 命令: (active=0)
TNORTHTHUMB  指北针位置→指北针方向<90.0> → 命令: (active=0)
TSYMBCUT     起点→终点→"当前切除外部，请选择保留范围或 [改为切除内部(Q)]<不切割>:" (active=1, 需补回车)
```

3. 临时类型探针（驱动 + 读回 `entlast` 类型 + UNDO 还原，用后即删）：

```text
TSYMMETRY    exec=True active_after=0 count 0->1 entlast_type='TCH_SYMMETRY'
TNORTHTHUMB  exec=True active_after=0 count 0->1 entlast_type='TCH_NORTHTHUMB'
TSYMBCUT     exec=True active_after=0 count 0->1 entlast_type='TCH_RUPTURE'  (尾随空回车后)
```

## 改动

- `src/t20_mcp/lisp_templates/tangent/{symmetry,north_arrow,break_line}.lsp`
  - 新模板，照 `coordinate.lsp` 骨架：点序列 + 实体增量 + `TCH_*` 类型校验。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_symmetry` / `_gen_north_arrow` / `_gen_break_line` 与三个 `_GENERATORS` 注册；
  - 工具 docstring 子命令清单补三行（均标 [已验证]）。
- `tests/test_tangent_lisp_gen.py`
  - 三组合法参数 VALID_CASES、序列注入断言、重合点拒绝断言；`north_arrow` 缺省北向断言。
- `scripts/itest_35_symbol_e2e.py`
  - 新增可重复真机 E2E（三命令一把跑 + 环境还原校验）。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态表、子命令表、遗留清单；完成度 ~50% → ~54%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_35_symbol_e2e.py
# symmetry/north_arrow/break_line 全 PASS; count 0->1 类型符合; 清理还原 PASS

uv run pytest -q
# 108 passed

uv run python -m compileall -q src scripts tests
# PASS

uv run python -X utf8 scripts/itest_19_mcp_stdio_smoke.py
# PASS: 9 tools listed; tangent.axis_lines dry-run PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未碰任何面板型（#32770/WPF）命令，
未对对话框做强关。三命令均冷状态可复现，临时探针脚本已删除。

## 下一步候选

同批官方表「符号标注」段仍有：引出标注 `TLeader`、剖切符号 `TSection`、
指向/剖切索引 `TPOINTINDEX`/`TSECTINDEX`、索引图名 `TIndexDim`、图名标注 `TDrawingName`。
其中 `TLeader`/索引类大概率需文字输入（可能弹框或要键入文本），下一轮先 itest_32 探提示流再判。
