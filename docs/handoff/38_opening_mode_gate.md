# Handoff 38 — 门窗两阶段模式门禁

> 历史基线：本文件记录“错误实体回滚 + 人工切换重试”阶段。
> 2026-07-24 的 Handoff 39 已在保留 group71 最终门禁的前提下完成面板模式自动切换；
> 当前行为以 Handoff 39、README 和 `docs/T20_COMMANDS.md` 为准。

## 问题

`TOpening` 的门/窗类型由天正非模态门窗面板决定，同一坐标序列无法切换类型。
仅写 `DoorSill` 或图层不能把门变成窗；权威判据是 `TCH_OPENING` 的 DXF group71：
`0=门`，`1=窗`。

## 管线协议

1. `door`/`window` 按当前面板模式尝试创建一个实体。
2. `opening.lsp` 立即读取 group71，与请求类型比较。
3. 匹配：注入 Width/Height/DoorSill/Layer，返回 `T20MCP-OPENING-OK`。
4. 不匹配：删除刚创建的错误实体，返回单行
   `T20MCP-OPENING-MODE-MISMATCH` 状态。
5. Python 工具把状态转成结构化 `OPENING_MODE_MISMATCH`，包含
   `requires_user_action`、`retry_operation`、`retry_data` 和回滚结果。
6. 模型必须暂停，请用户切换到门或窗模式；用户确认后原参数重试。

这允许建筑平面按“门阶段 → 用户切换 → 窗阶段”分批生成，且模式错误不会留下
伪装图层或错误类型的实体。全自动切换仍可沿 Handoff 36 的控件级 UI 自动化路线继续研究。

## 实现范围

- `opening.lsp` 在属性注入前读取 group71；模式错时优先 COM 删除，并以 `entdel`
  兜底，状态中明确 `rollback=ok|failed`。
- `parse_opening_status()` 把单行 LISP 状态解析为稳定 Python 结构。
- `CommandResult.to_dict()` 在失败时也保留 payload，MCP 调用方因此能收到
  `retry_operation`、`retry_data` 和回滚结果。
- `scripts/_opening_retry.py` 为真机脚本提供统一的“检测 → 提示切换 → 安全取消
  面板启动的 TOpening → 原参数重试”流程；非交互终端不会等待输入。
- `scripts/itest_opening_mode_gate.py` 是窄探针，每次只验证一个请求类型和一个预期，
  并在结束时回滚临时墙和门窗。

## 2026-07-24 真机证据

环境：T20 天正建筑 V10.0 / AutoCAD 2024，`Drawing1.dwg`。

| 请求 | 面板模式 | 预期 | 实测 |
|---|---|---|---|
| `window` | 门 | mismatch | `actual=0`，错误门删除，实体数不变 |
| `door` | 门 | success | group71=0，图层 `DOOR_FIRE`，清理后实体数归零 |
| `window` | 窗 | success | group71=1，图层 `WINDOW`，清理后实体数归零 |
| `door` | 窗 | mismatch | `actual=1`，错误窗删除，实体数不变 |

随后再次切回门模式，使用原参数重试 `door` 成功。双向失败路径的
`wrong_entity_rolled_back=true`，每轮前后实体数量均对账。

## 回归结果

- 离线：`190 passed`；`compileall`、`git diff --check`、MCP stdio 冒烟通过。
- 标注精度探针：6/6 通过，包含非整数坐标、三墙 `TDimTP` 和墙端点读回。
- 门窗图层探针：门为 `DOOR_FIRE`、窗为 `WINDOW`，属性读回通过。
- 核心 E2E：全部通过，结束后实体数 0。
- 批量 E2E：25/25 通过，结束后实体数 0。
- 户型脚本：35 个实体，全部断言通过。
- 拉丁十字教堂脚本：61 个实体；9 项验收全部通过（门 7、窗 9、尺寸 3、
  家具矩形 11、文字 5、指北针和图名各 1）；最终统一清理后实体数 0。

## 收尾裁定

`scripts/church_cross_entities.json` 与 `scripts/floorplan_entities.json` 含实时 handle
和当次实体清单，属于可重建运行产物，不作为稳定夹具入库；已加入 `.gitignore`。
包版本统一为 `3.1.0`，并由安装元数据提供运行时 `__version__`。
