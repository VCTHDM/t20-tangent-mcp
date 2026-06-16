# Handoff 23 — rect_roof / cusp_roof 屋顶构件封装

执行者：Claude（lead，真机亲跑） ｜ 日期：2026-06-14 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

延续「命令行点序列、无对话框、无选对象步」目标，一轮 E2E 拿下两个屋顶：

| 子命令 | 天正命令 | 序列 | active 后 | 实体类型 |
|---|---|---|---|---|
| `rect_roof` | `TRectRoof` | 左下角点→右下角点→右上角点→回车退出循环 | 0 | `TCH_MOUNTROOF` |
| `cusp_roof` | `TCuspRoof` | 屋顶中心位置→第二点(定半径/朝向) 两点即收尾 | 0 | `TCH_CUSPROOF` |

`rect_roof` 三角点定底面矩形(左下/右下/右上)，循环式补空回车退出；坡角/出檐走面板记忆值。
`cusp_roof` 中心点+半径点两点即收尾(无尾随回车)，缺省半径点取中心右侧 3000mm；
边数/屋顶高走面板记忆值。

## 真机探测

1. itest_32 空输入提示流(均无弹框、无选对象)：
   - `TRECTROOF` → 「点取主坡墙外皮的左下角点<退出>」(实测要 3 个角点)。
   - `TCUSPROOF` → 「请输入屋顶中心位置<退出>」(中心+第二点)。
2. 点序列试驱动 + entlast 类型读回(临时探针，用后即删)：
   - `TRECTROOF`：`(ll lr ur "")` → active=0, count 0→1, `TCH_MOUNTROOF`，UNDO 干净。
   - `TCUSPROOF`：`(center radius)` → active=0, count 0→1, `TCH_CUSPROOF`，干净。
   - 冷态复测 final_count=0。

## 同轮探测但暂不封装(留坑记录)

- **单轴绘制 `TSingleAxis`**：起点→终点→回车可成，但产物是裸 `LINE`(非天正智能轴线)，
  价值不比已有 `axis_lines` 高，暂不封装。
- **引出标注 `TLeader`**：第一点→引线位置→文字基线位置；文字基线给空回车会放弃(0 实体)，
  正常完成需内联文字编辑(挂死风险)，暂不封装(同 leader/text 系列定位)。
- **墙体造型 `TAddPatch`**：外凸/内凹关键字→轮廓点列→结束；无依附墙体时 0 实体(造型须附墙)，
  前置重，暂不封装。
- **任意/人字坡顶 `TSlopeRoof`/`TDualSlopeRoof`**：预计为「选闭合多段线」选对象步(同 `TSlab` 坑)，
  未探先记，待选择集注入通则解决。

## 改动

- `src/t20_mcp/lisp_templates/tangent/{rect_roof,cusp_roof}.lsp` — 新模板。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_rect_roof` / `_gen_cusp_roof` 与 `_GENERATORS` 注册；
  - 工具 docstring 子命令清单补两行。
- `tests/test_tangent_lisp_gen.py` — VALID_CASES、三角点/中心半径点序列注入断言、
  角点重合/中心半径重合 拒绝断言。
- `scripts/itest_39_roof_e2e.py` — 新增可重复真机 E2E(两命令 + 环境还原)。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态表、子命令表、坑清单；完成度 ~64% → ~66%。

## 验证

```powershell
uv run python -X utf8 scripts/itest_39_roof_e2e.py
# rect_roof/cusp_roof 全 PASS; entlast 类型符合; 清理还原 PASS (final_count=0)

uv run pytest -q
# 139 passed

uv run python -m compileall -q src scripts tests
# PASS
```

## 安全边界

本轮未触碰 `_prelude.lsp` / IPC / dispatcher，未对任何对话框做强关。探测散落实体
均经受控 UNDO 清空至 0；临时探针脚本(_probe_b/_probe_c.py)已删除。

## 下一步候选

1. 继续薅纯点序列/插入式构件：先 itest_32 探提示流再判，避开选对象步与 #32770 面板。
   候选方向：符号/构件库里的单点插入类(老虎窗除外，多需依附屋顶)。
2. **选择对象步注入通则**(硬骨头，已多轮搁置)：打通可批量解锁坡屋顶/平板/竖板/散水/
   半径直径角度弧弦标注一大批。待研究 `(sssetfirst)` 预选 / 夹点 / 其他路线。
