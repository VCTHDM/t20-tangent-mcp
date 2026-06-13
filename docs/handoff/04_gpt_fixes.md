# Handoff 04 — GPT 按 Fable 审查整改

执行人：GPT ｜ 日期：2026-06-12 ｜ 依据：`docs/handoff/03_fable_review.md`（逐条 ✅ done 回填于该文档）

按 P0 → P1 → P2 顺序逐条整改，无跳过、无降级。`uv run pytest` 全绿：**60 passed**
（原 43 + 新增 17）。下列「真机待验」项为审查本身已声明需 T20 环境者，代码侧均已就位。

## P0 — 链路断裂 / 静默错误 / 环境破坏

| 项 | 改动 | 验证 |
|---|---|---|
| P0-1 结果解码链 | `file_ipc._decode_result_bytes`：utf-8 → cp936 → 系统 ANSI → cp1252（cp1252 退到最后，不再静默放行 GBK 乱码） | `TestDecodeResultBytes` GBK 中文无损 + ASCII/utf-8 不回归 |
| P0-2 LISP 写出 GBK | `execute_lisp` 改 `encode("gbk", errors="strict")` + `write_bytes`；`UnicodeEncodeError` 转含"GBK"+违规字符的明确错误；模板仍 UTF-8 存储 | `TestExecuteLispGbk` 砖墙往返一致、emoji 被拒 |
| P0-3 lisp-code/ | 新建 `lisp-code/mcp_dispatch.lsp`（从 vendor 拷贝）：转纯 ASCII 可任意代码页 `(load)`；IPC 前缀对齐 `t20_mcp_cmd_/result_`；IPC 目录 env 否则 `%TEMP%/t20_mcp`；结果仍 `(open "w")` 写 ANSI=GBK；顶部声明 T20 环境与编码契约 | 引导链修复（`config.LISP_DIR` 指向该文件）；真机 ping 往返待实测 |
| P0-4 模板迁移骨架 | 6 模板改写为 `t20mcp:begin`/局部 `*error*`/`t20mcp:call`/`end`/`fail`，删尽手写 setq/setvar，坐标走 `t20mcp:pt`，export_t3 不再单独管 FILEDIA；`_render` 在产物前拼接 `_prelude.lsp` | `test_generates_balanced_lisp` 含 `t20mcp:begin`、无裸 `setvar "CMDDIA"`、括号平衡 |
| P0-5 dry-run 默认 | `tangent` 工具加 `execute=False`：默认仅返回渲染 LISP 不下发；`execute=True` 才执行；`axis_grid/door/window` 附 `warning` | `TestTangentDryRun` 5 例（含 backend 不被调用、warning 字段） |

## P1 — 真机联调前

| 项 | 改动 | 验证 |
|---|---|---|
| P1-1 进程名识别窗口 | `find_autocad_window` 用 `GetWindowThreadProcessId` + `QueryFullProcessImageNameW`，`acad.exe`（env 可配）为主判据，标题 autocad/天正/tarch 为辅，多命中优先 .dwg 并记警告；去掉 "LT" 文案 | 逻辑就位；真机多实例选择待实测 |
| P1-2 模态框防护 | dispatch 前 `_autocad_modal_dialog_present`（GetLastActivePopup + 同线程 `#32770`）命中即返回阻塞错误且不发触发串；ESC 仅在上次超时（`_needs_cancel`）时注入 | `TestModalDialogGuard` 阻塞短路 + ESC 时机 |
| P1-3 参数 GBK 校验 | `_require_str` 末尾 `value.encode("gbk")` 校验，失败抛含字段名+违规字符的 `ParamError` | `test_non_gbk_layer_rejected_with_field` / `test_gbk_chinese_layer_accepted` |
| P1-4 文档回填 | T20_COMMANDS.md export_t3 §1.9/§2 统一下调「低」+ 交叉引用 §0 坑 1；新增 §3.1「中置信先行」验证排程 | 文档自相矛盾消除；真机录制序列待执行排程 |

## P2 — 排期内改进

| 项 | 改动 | 验证 |
|---|---|---|
| P2-1 params 编码 | 命令文件改 `ensure_ascii=False` + GBK 写出（与 .lsp 同契约） | `test_chinese_params_written_as_gbk_not_unicode_escape` |
| P2-2 块注释 lint | `_render` token 替换前 `if ";|" in body` 拒绝 | `test_block_comment_template_rejected` |
| P2-3 路径归一化 | `_gen_export_t3` 校验后 `out_path` 反斜杠转正斜杠 | `test_export_path_backslash_normalized_to_slash` |
| P2-4 IPC 目录默认 | `config.IPC_DIR` 默认 `%TEMP%/t20_mcp`，dispatcher 同规则解析 | 导入检查打印 `…/Temp/t20_mcp` |
| P2-5 占位符记法 | 6 模板头注释统一 `{{TOKEN}}`；`_render` 残留检查忽略注释 | 随 P0-4 完成 |
| P2-6 TExplode 批注 | T20_COMMANDS.md §1.9 新增 `T81_TExplode`（低）+ 破坏性/临时副本/禁分解当前图纸批注 | 文档 |

## 测试与文件改动

- 测试：`tests/test_tangent_lisp_gen.py`（更新骨架断言 + 新增 P1-3/P2-2/P2-3 用例）、
  新增 `tests/test_encoding_and_tool.py`（P0-1/P0-2/P0-5/P1-2/P2-1）。
- 代码：`src/t20_mcp/backends/file_ipc.py`、`src/t20_mcp/tools/tangent.py`、`src/t20_mcp/config.py`、
  6 个 `lisp_templates/tangent/*.lsp`、新增 `lisp-code/mcp_dispatch.lsp`。
- 文档：`docs/T20_COMMANDS.md`、本文件、`docs/handoff/03_fable_review.md`（逐条 ✅ done）。

## 仍需 T20 真机的后续（非本次整改可关闭）

1. ping 往返、`(load lisp-code/mcp_dispatch.lsp)` 引导（P0-3 验收）。
2. 故意改错命令名验证 `T20MCP-ERR` + 环境三值一致 + 无垃圾实体（P0-4 真机验收）。
3. 多 AutoCAD 实例下窗口选择可解释（P1-1）；天正自绘框是否被 `#32770` 命中（P1-2）。
4. 按 §3.1 排程逐条录制真实别名/序列、升置信度、截图存档（P1-4）；天正自绘导出框是否理会 FILEDIA=0。
