# Handoff 02 — Tangent (天正 T20) 命令编目与封装骨架

执行人：codex ｜ 日期：2026-06-12 ｜ 分支：master

## 1. 任务范围

天正 T20 命令的**脚本化编目**与**封装骨架**。明确约束：**未改动 dispatcher、IPC 层与
`server.py`**，仅新增 LISP 模板生成与 `tangent` consolidated 工具（独立模块，按需挂载），
复用现有 `execute_lisp` 通道下发。

## 2. 交付物

| 文件 | 说明 |
|---|---|
| `docs/T20_COMMANDS.md` | 30 条 T20 常用命令编目（轴网/墙体/门窗/柱/楼梯/房间/标注/文字/导出），含命令行别名、是否弹框、CMDDIA 可绕过性、参数序列推测、置信度 |
| `src/t20_mcp/lisp_templates/tangent/*.lsp` | 6 个 LISP 模板（`axis_grid/wall/door/window/dimension/export_t3`），占位符 `{{TOKEN}}` 注入 |
| `src/t20_mcp/tools/tangent.py` | `tangent` 工具 + 纯生成逻辑（`generate_lisp` / `is_paren_balanced`）+ 全量参数类型/范围校验 |
| `src/t20_mcp/tools/__init__.py` | 子包导出 |
| `tests/test_tangent_lisp_gen.py` | 43 个离线测试，不连 AutoCAD |
| `pyproject.toml` | 追加 dev 组 `pytest` 与 `[tool.pytest.ini_options]`（`pythonpath=src`） |

> **注**：`tangent.py` 完全独立，**未改动 `server.py`**（dispatcher/IPC 自然也未动）。
> 需要挂载到 MCP server 时，在 `server.py` 调用一次
> `from t20_mcp.tools.tangent import register_tangent_tool; register_tangent_tool(mcp)` 即可，
> 该函数已就绪但默认不自动注册。

## 3. 设计要点

- **铁律遵守**：无任何硬编码键击/SendKeys；全部走「模板 + 参数注入」。Python 侧只做
  校验与数值/字符串格式化，命令交互序列写在 `.lsp` 模板里。
- **参数校验**：坐标有限性 + 绝对值上限；墙宽/高/洞口宽/窗台高分别独立范围；轴网间距为
  非空数字列表且逐项范围校验、段数上限 200；角度 ±360；图层名/路径做长度、空串、控制字符
  与 LISP 转义处理（防注入逃逸）。`bool` 被显式拒绝（避免 `True` 当 1）。
- **安全自检**：渲染后校验「无残留占位符」+「括号平衡」（`is_paren_balanced` 忽略字符串与
  `;` 注释内的括号），任一不过抛 `ParamError`。
- **可测试性**：生成逻辑与 backend 解耦，测试直接调 `generate_lisp(...)`，无需 AutoCAD。

## 4. 测试结果

```
uv run --group dev pytest tests/test_tangent_lisp_gen.py -q
43 passed
```

覆盖：括号平衡器正/反例、6 子命令均生成平衡 LISP、参数注入正确性（坐标/间距/宽高/图层/
路径转义/浮点紧凑格式）、非法参数拒绝（缺参/类型错/bool/NaN/inf/越界/零长墙/重合点/空间距/
非列表/段数超限/角度越界/扩展名错/版本错/控制字符注入/图层超长）。

## 5. ⚠️ 置信度「中 / 低」条目 —— reviewer 重点审查

> 作者**无 T20 真机**。以下命令名、命令行别名、参数交互序列均为**推测**，
> 已在文档与模板注释中标注「待真机验证」。请有 T20 环境者逐条核验。

### 5.1 置信度「中」（命令名较可靠，参数序列待验证）

| 子命令 / 命令 | 风险点 | 需真机确认 |
|---|---|---|
| `wall` 绘制墙体 (`TGWall?`) | 命令名与「左宽/右宽/高/类型/起点/终点」的输入顺序均为推测 | 命令行别名、参数 prompt 顺序、是否弹参数面板 |
| `dimension` 逐点标注 (`TDim?`) | 「尺寸线位置点 → 标注点序列 → 回车」顺序推测 | 实际拾取顺序、是否需先选对象 |
| `export_t3` 图形导出天正3 (`T20_Export?`) | 命令名、是否可用 `FILEDIA=0`+路径静默导出、版本选项写法全推测 | 真实命令名、静默导出可行性、目标版本参数值 |

### 5.2 置信度「低」（命令名/别名/序列高度不确定）

| 子命令 / 命令 | 风险点 |
|---|---|
| `axis_grid` 绘制轴网 (`HZZW?/TGAxisGrid?`) | 天正自有对话框，`CMDDIA=0` **大概率无法绕过**；上/下开间、左/右进深、`H/V/A` 子选项均为臆测 |
| `door` 普通门 (`TOpening?/TDoor?`) | 门窗为强对话框命令且须依附已有墙体；`"D"`、`W/H/O` 子项与拾取插入点的序列为臆测 |
| `window` 普通窗 (`TOpening?/TWindow?`) | 同上，`"C"`、`W/H/S` 子项序列臆测 |

### 5.3 文档表中其余「低」置信条目

`docs/T20_COMMANDS.md` 中**未被工具覆盖**但已编目的命令（圆弧轴网、单线变墙、标准柱、
双跑楼梯、搜索房间、标高标注、门窗表等）置信度均为「低」，仅作清单与可驱动性初判，
**参数序列一律标「待真机验证」，未冒充确定**。

## 6. 关键技术判断（供 reviewer 评估，高置信度领域知识）

**`CMDDIA=0` 对天正自有对话框命令多半无效。** 天正轴网/门窗/楼梯用的是基于 ObjectARX 的
自有对话框引擎，`CMDDIA` 主要影响 AutoCAD 原生命令（`-INSERT`/`PLOT`/`-LAYER`）。
因此「对话框绕过」的真实路径更可能是：命令行版别名、天正「记忆上次参数」机制、或天正暴露的
`c:` LISP 接口——三者均待真机验证。模板已以 `(command "<cmd>" ...)` 占位，便于真机校正而
无需改动 Python 生成逻辑。

## 7. 下一步建议

1. 真机回填 `docs/T20_COMMANDS.md` 的别名与参数序列，置信度升「高」。
2. 校正 6 个 `.lsp` 模板的命令名与参数顺序；新增柱/楼梯/房间/符号标注子命令。
3. 真机验证后，在集成测试层补「生成 → execute_lisp → 结果」端到端用例。
