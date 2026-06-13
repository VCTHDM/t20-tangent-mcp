# Handoff 21 — rectangle / balcony / step 简单几何构件封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

离开符号标注段，转向「纯几何点序列、无文字依赖、无对话框」目标。一轮 E2E 拿下三个：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `rectangle` | `TRect` | 第一角点→第二角点→回车 | 0 | `TCH_RECT` |
| `balcony` | `TBalcony` | 各轮廓点→回车 | 0 | `TCH_BALCONY` |
| `step` | `TStep` | 各轮廓点→回车 | 0 | `TCH_STEP` |

`rectangle` 固定两角点；`balcony`/`step` 接受变长轮廓点列（≥2 点），新增 `_require_point_list`
helper 与 `{{POINTS}}` 渲染。阳台/台阶按轮廓可能生成多个实体（4 点矩形轮廓实测 +2），
故 E2E 只校验「实体增加 且 entlast 类型符合」。三命令均无 #32770 面板、无文字输入，
文字/构造参数（阳台类型、台阶踏步数等）走天正面板记忆值。

## 真机探测

1. itest_32 空输入：`TRECT`/`TSTEP`/`TBALCONY` 首个提示均为命令行点取，无弹框。
2. 点序列试驱动 + entlast 类型读回（临时探针，用后即删）：
   - `TRECT` 两角点后 active=1（循环式），补 `""` → active=0, `TCH_RECT`。
   - `TBALCONY`/`TSTEP` 各轮廓点 + `""` → active=0，2 点/4 点均成（4 点 +2 实体）。
   - 冷态复测 final_count=0，UNDO 清理干净。

## 标注族探测（暂不封装，留坑记录）

同轮探了半径/直径/角度/弧弦标注 `TDimRad`/`TDimDia`/`TDimAng`/`TDimArc`：

- 均命令行驱动、无弹框；首个提示是「请选择待标注的圆弧/直线/弧段」。
- **选择步打不通**：vl-cmdf 传 ename 选中 → 报「点无效」；传曲线上的拾取点（如圆周上
  `(500,0)`）同样不生效，命令滞留 `active=1`，未生成标注实体（entlast 仍是前置圆/弧/线）。
- 结论：这些天正标注的对象选择不吃脚本点序列，需另找「选择集预置 / ssget 注入」路线，
  本轮暂搁置。详见 docs/T20_COMMANDS.md §1.2 与遗留 §6.12。

## 改动

- `src/t20_mcp/lisp_templates/tangent/{rectangle,balcony,step}.lsp` — 新模板。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_require_point_list` / `_pt_list_lisp` helper 与 `POINT_LIST_COUNT_MAX` 常量；
  - 新增 `_gen_rectangle` / `_gen_balcony` / `_gen_step` 与 `_GENERATORS` 注册；
  - 工具 docstring 子命令清单补三行。
- `tests/test_tangent_lisp_gen.py` — VALID_CASES、序列/点列注入断言、零面积/点数不足/
  点格式/相邻重合/非列表 拒绝断言。
- `scripts/itest_37_geom_e2e.py` — 新增可重复真机 E2E（三命令 + 环境还原）。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态表、子命令表、遗留清单；完成度 ~58% → ~62%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_37_geom_e2e.py
# rectangle/balcony/step 全 PASS; entlast 类型符合; 清理还原 PASS

uv run pytest -q
# 127 passed

uv run python -m compileall -q src scripts tests
# PASS

uv run python -X utf8 scripts/itest_19_mcp_stdio_smoke.py
# PASS: 9 tools listed; tangent.axis_lines dry-run PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未对任何对话框做强关。探测累积的散落实体
（标注族失败遗留的圆/弧/线）已经受控 UNDO 清空至 0；临时探针脚本已删除。

## 下一步候选

1. **标注族选择步**：研究天正标注命令的对象选择能否经预置选择集 / `(sssetfirst)` /
   `ssget` 注入；通则一开，半径/直径/角度/弧弦/内门标注等一批可批量封装。
2. 继续薅纯点序列构件：坡道 `TAscent`、散水 `TOutlna`（需选墙体，前置稍重）、
   平板 `TSlab` 等；先 itest_32 探提示流再判。
