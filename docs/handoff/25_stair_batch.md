# Handoff 25 — line_stair / arc_stair 楼梯梯段封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

延续「命令行点序列、无对话框、无选对象步」目标，一轮 E2E 拿下两个梯段：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `line_stair` | `TLStair` | 点取位置→回车退出循环 | 0 | `TCH_LINESTAIR` |
| `arc_stair` | `TAStair` | 点取位置→回车退出循环 | 0 | `TCH_ARCSTAIR` |

两者均为循环式单点插入（「点取位置或 [转90度/左右翻/...]」，给完点回到位置提示，补空回车
退出，同 `ramp`/`insight`/`tree` 模式）。梯段宽/踏步数/半径/圆心角等构造参数走天正面板记忆值，
本工具只参数化插入点。注: 这两个是**单梯段**插入，不是带休息平台的整体楼梯（双跑楼梯
`TRStair` 另论）。

## 真机探测

1. itest_32 空输入提示流（均无弹框、无选对象）：
   - `TLSTAIR`/`TASTAIR` → 「点取位置或 [转90度(A)/左右翻(S)/...]<退出>」(插入式)。
   - `TELEVATOR` → 「请给出电梯间的一个角点<退出>」。
2. 点序列试驱动 + entlast 读回（临时探针，用后即删）：
   - `TLSTAIR`：`(pt 0 0) ""` → active=0, count 0→1, `TCH_LINESTAIR`，干净。
   - `TASTAIR`：`(pt 0 0) ""` → active=0, count 0→1, `TCH_ARCSTAIR`，干净。
   - 冷态复测 final_count=0。

## 同轮探测但暂不封装（留坑记录）

- **电梯 `TElevator`**：电梯间角点→对角点→「请点取开电梯门的墙线<退出>」。第三步是
  选墙线（选对象步，需前置墙体），`(c1 c2 "" "")` 空回车序列 0 实体；前置重 + 选对象步，暂搁置。
- **双跑楼梯 `TRStair`** 等：预计带 #32770 面板或需选墙，未探先记。

## 改动

- `src/t20_mcp/lisp_templates/tangent/{line_stair,arc_stair}.lsp` — 新模板。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_line_stair` / `_gen_arc_stair` 与 `_GENERATORS` 注册；
  - 工具 docstring 子命令清单补两行。
- `tests/test_tangent_lisp_gen.py` — VALID_CASES、单点+回车注入断言、缺坐标拒绝断言。
- `scripts/itest_41_stair_e2e.py` — 新增可重复真机 E2E（两命令 + 环境还原）。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态表、子命令表、坑清单；完成度 ~68% → ~70%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_41_stair_e2e.py
# line_stair/arc_stair 全 PASS; entlast 类型符合; 清理还原 PASS (final_count=0)

uv run pytest -q
# 151 passed

uv run python -m compileall -q src scripts tests
# PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未对任何对话框做强关。探测散落实体
均经受控 UNDO 清空至 0；临时探针脚本（_probe_f.py）已删除。

## 下一步候选

1. 继续薅单点/点序列插入类（先 itest_32 探提示流再判，避开选对象步、#32770 面板、
   内联文字编辑）。今日已连封 5 轮 10 个子命令。
2. **文字依赖类统一处理**（索引/引出/做法标注）：编号文字能否经命令行参数或 COM 注入。
3. **选择对象步注入通则**（硬骨头，多轮搁置）：坡屋顶/平板/竖板/散水/电梯选墙/标注族。
