# Handoff 17 — coordinate 坐标标注封装

执行者：Codex ｜ 日期：2026-06-13 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

`TCoord` 是本轮稳定新增封装目标：没有弹框，两点命令行序列可生成 `TCH_COORD`。
已新增 `tangent.coordinate` 子命令。

## 真机探测

1. `uv run python -X utf8 scripts/itest_01_bringup.py`
   - PASS：窗口识别、dispatcher ping、中文编码往返均通过。

2. 首个提示捕获：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TCOORD empty none
```

关键提示：

```text
TCOORD
当前绘图单位:mm,标注单位:M;以世界坐标取值;北向角度90度
请点取标注点或 [设置(S)\批量标注(Q)]<退出>:
```

3. 单点试驱动：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TCOORD '(list (t20mcp:pt 1234 5678))' none
```

关键提示：

```text
请点取标注点或 [设置(S)\批量标注(Q)]<退出>:1234,5678
点取坐标标注方向<退出>:
```

4. 两点试驱动：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TCOORD '(list (t20mcp:pt 1234 5678) (t20mcp:pt 1234 6678))' none
```

关键提示：

```text
请点取标注点或 [设置(S)\批量标注(Q)]<退出>:1234,5678
点取坐标标注方向<退出>:1234,6678
请点取标注点<退出>:
```

5. 临时实体读回探针：
   - `active=0 type=TCH_COORD`
   - 实体数 `21 -> 22 -> 21`，UNDO 清理成功。

## 改动

- `src/t20_mcp/lisp_templates/tangent/coordinate.lsp`
  - 新增模板：标注点 → 方向点 → 回车，实体增量校验 `TCH_COORD`。
- `src/t20_mcp/tools/tangent.py`
  - 新增 `_gen_coordinate` 与 `coordinate` 子命令。
- `tests/test_tangent_lisp_gen.py`
  - 新增合法参数、序列注入断言、重合点拒绝断言。
- `scripts/itest_34_coordinate_e2e.py`
  - 新增可重复真机 E2E。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步状态与索引。

## 验证

```powershell
uv run python -X utf8 scripts/itest_34_coordinate_e2e.py
# PASS: coordinate exec=True, count 21->22, type='TCH_COORD'; 清理还原 PASS

uv run pytest -q
# 98 passed in 0.54s

uv run python -m compileall -q src scripts tests
# PASS

uv run python -X utf8 scripts/itest_19_mcp_stdio_smoke.py
# PASS: 9 tools listed; tangent.axis_lines dry-run PASS

git diff --check
# PASS（仅工作区 LF/CRLF 提示，无空白错误）
```

## 安全边界

本轮未触碰 `_prelude.lsp`、IPC、dispatcher，也未尝试楼梯/屋顶/门窗表等面板型命令。
