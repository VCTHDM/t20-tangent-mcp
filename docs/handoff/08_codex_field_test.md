# Handoff 08 — Codex 真机联调记录

执行人：Codex ｜ 日期：2026-06-13 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024（Drawing1.dwg）

## 1. 基线

```text
uv run python scripts/itest_01_bringup.py
```

结果：

- 窗口识别：PASS
- dispatcher ping：PASS
- 中文图层编码往返：PASS
- 环境复位后：`CMDDIA=1 / FILEDIA=1 / OSMODE=0 / CMDACTIVE=0`

## 2. 已知 E2E 回归

```text
uv run python scripts/itest_12_e2e.py
```

结果：

- `wall`: PASS，`TCH_WALL`，回读 `LeftWidth=240 / RightWidth=120 / Height=3300 / Style=砖`
- `dimension`: PASS，`TCH_DIMENSION2`
- `door`: PASS，`TCH_OPENING`，回读 `Width=1000 / Height=2000 / DoorSill=0`
- 清理还原：PASS

## 3. elevation / TMElev

```text
uv run python scripts/itest_15_elevation.py
```

结果：

- `elevation`: PASS
- 实体增量：`0 -> 1`
- 实体类型：`TCH_ELEVATION`
- UNDO 后实体数：`0`
- 收尾环境：`CMDACTIVE=0 / CMDDIA=1 / FILEDIA=1 / OSMODE=0`

另走 MCP 工具注册路径：

```text
tangent(operation="elevation", data={base_x:0, base_y:0, label_x:1000, label_y:1000}, execute=True)
```

结果：`ok=true`，生成 1 个 `TCH_ELEVATION`，返回 warning，UNDO 后环境干净。

## 4. TCH_OPENING 属性探测

```text
uv run python scripts/itest_16_opening_props_safe.py
```

结果：

- 当前 TOpening 面板模式生成 `TCH_OPENING`，表现为门。
- 可读/可写：`Width=1000.0`、`Height=2000.0`、`DoorSill=0.0`
- 不可读或不可写：`SillHeight`、`WindowSillHeight`、`OpType`、`Kind`、`Type`、`WinType`
- `UpLevel` 可读但值为乱码样式的 `·ñ`，暂不用于封装。
- 清理还原：PASS，实体数回 `0`，环境干净。

## 5. 安全修正

以下脚本已移除 `WM_CLOSE` 兜底，只保留 ESC 或提示改走按钮点击恢复：

- `scripts/itest_08_dialog_recover.py`
- `scripts/itest_09_opening_axis.py`
- `scripts/itest_10_opening_props.py`

仓库扫描：

```text
rg -n "win32con\\.WM_CLOSE|PostMessage\\([^\\n]*WM_CLOSE" scripts src lisp-code
```

无命中。

## 6. 离线验证

```text
uv run pytest -q
68 passed

uv run python -m compileall -q src scripts tests
```

均通过。

## 7. 后续命令探测

以下命令已按“两轮不成即停”原则探测，均未留下实体，环境复位干净：

- `TGColumn`
  - 点→回车：0 实体
  - 点→点→回车：0 实体
- `TDimWall`
  - 先创建 `TCH_WALL`，选择墙体→回车：0 新实体
  - 选择墙体→回车→标注位置→回车：0 新实体
- `TSWall`
  - 先创建原生 `LINE`，选择线→回车：未转换，仅保留原 `LINE`
  - 选择线→回车→`240`→回车：未转换，仅保留原 `LINE`

结论：以上命令不进入 `tangent` 子命令，等待新的可靠交互序列或官方 API 线索。

## 8. E2E 清理修正

`scripts/itest_12_e2e.py` 已修正收尾逻辑：

- 删除测试图层改用 COM 删除，避免命令行残留。
- 清理后执行 `CMDACTIVE` 退栈循环并复位 `CMDDIA/FILEDIA/OSMODE`。
- 验收条件新增环境干净断言。

复跑结果：

```text
wall: PASS
dimension: PASS
door: PASS
清理还原: PASS
env={'CMDDIA': 1, 'FILEDIA': 1, 'OSMODE': 0, 'CMDACTIVE': 0}
```
