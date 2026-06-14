# Handoff 22 — ramp / arrow 点序列构件封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

延续「命令行点序列、无对话框」目标，一轮 E2E 拿下两个：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `ramp` | `TAscent` | 点取位置→回车退出循环 | 0 | `TCH_ASCENT` |
| `arrow` | `TArrow` | 起点→终点→回车→回车 | 0 | `TCH_ARROW` |

`ramp` 是循环插入式（放一个回到「点取位置」，补空回车退出），单点参数化插入位置，
坡道宽度/坡长走面板记忆值。`arrow` 是双层循环：两点连出引线后需补**两个**空回车——
第一个结束当前引线的「直段下一点<结束>」循环，第二个退「箭头起点<退出>」外层循环
（补完 Handoff 18 未确认的退出语义）；引注文字走面板记忆值，附 warning（同 `drawing_name`）。

## 真机探测

1. itest_32 空输入提示流：
   - `TASCENT` → 「点取位置或 [转90度/左右翻/...]<退出>」，无弹框，插入式。
   - `TARROW` → 「箭头起点或 [点取图中曲线/点取参考点]<退出>」→「直段下一点<结束>」。
2. 点序列试驱动 + entlast 类型读回（临时探针，用后即删）：
   - `TASCENT`：`(pt 0 0) ""` → active=0, count 0→1, `TCH_ASCENT`，UNDO 干净。
   - `TARROW`：`(p1 p2 "")` 仍 active=1；`(p1 p2 "" "")` → active=0, `TCH_ARROW`，干净。
   - 冷态复测 final_count=0。

## 同轮探测但暂不封装（留坑记录）

- **平板 `TSlab`**：提示「选择一封闭的多段线或圆<退出>」。建闭合 LWPOLYLINE 后，
  `ssget "_L"` 注入选择集 → 命令滞留 active=1，0 平板；改传多段线边上拾取点
  `(pt 2000 0)` → 命令默认退出，0 平板。选对象步不吃脚本点/选择集，同标注族
  选择步坑（Handoff 21 §标注族）。竖板 `TVertSlab` 预计同类，一并搁置。
- **地下坡道 `TUndergroundRamp`**：提示「请点取坡道起点<退出>」→「下一点」。
  两点+回车可出几何，但 count 0→3 且 entlast 是裸 `LWPOLYLINE`（非干净 TCH_ 实体），
  难以稳定断言产物类型，暂不封装。

## 改动

- `src/t20_mcp/lisp_templates/tangent/{ramp,arrow}.lsp` — 新模板。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_ramp` / `_gen_arrow` 与 `_GENERATORS` 注册；
  - `arrow` 加入 `LOW_CONFIDENCE_WARNINGS`（引注文字取面板记忆值）；
  - 工具 docstring 子命令清单补两行。
- `tests/test_tangent_lisp_gen.py` — VALID_CASES、序列/双空回车注入断言、
  缺坐标/起终点重合 拒绝断言。
- `scripts/itest_38_ramp_arrow_e2e.py` — 新增可重复真机 E2E（两命令 + 环境还原）。
- `README.md` / `docs/T20_COMMANDS.md` — 同步状态表、子命令表、坑清单；完成度 ~62% → ~64%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_38_ramp_arrow_e2e.py
# ramp/arrow 全 PASS; entlast 类型符合; 清理还原 PASS (final_count=0)

uv run pytest -q
# 133 passed

uv run python -m compileall -q src scripts tests
# PASS

uv run python -X utf8 scripts/itest_19_mcp_stdio_smoke.py
# PASS: 9 tools listed; tangent.axis_lines dry-run PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未对任何对话框做强关。探测散落实体
（平板试验遗留的 LWPOLYLINE、地下坡道杂实体）均经受控 UNDO/ERASE 清空至 0；
临时探针脚本（_probe_ascent/slab/slab2/batch/arrow.py）已删除。

## 下一步候选

1. **标注族 / 平板选择步通则**：天正「选择对象」步统一不吃脚本点/选择集，
   是当前最大的批量封装阻碍（影响半径/直径/角度/弧弦标注、平板、竖板、散水等）。
   待研究 `(sssetfirst)` 预选 / COM `SendCommand` 配合夹点 / 其他注入路线。
2. 继续薅纯点序列/插入式构件：先 itest_32 探提示流再判，避开选对象步与 #32770 面板。
