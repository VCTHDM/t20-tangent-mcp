# Handoff 03 — Fable 架构审查

执行人：Fable（架构师/reviewer）｜ 日期：2026-06-12 ｜ 审查对象：Gemini 适配清单（`docs/T20_ADAPTATION_PLAN.md`）+ Codex tangent 模块（commit d0ee486）

## 0. 总评

- **Codex 模块纪律良好**：置信度诚实标注、参数校验完整、离线测试齐全。但存在一个结构性矛盾：**编目文档承认序列是推测，模板却把推测序列写成了默认可执行的代码**，叠加 `(command)` 对未知命令的级联失控特性，"待验证"会变成"必然执行的破坏"。
- **Gemini 清单方向正确但停留在草案**，且其声称的 `lisp-code/` 目录实际**不存在**（CLAUDE.md、config.py 均引用它，dispatcher 只活在 vendor 里）——引导链路当前是断的。
- **全链路编码是最大盲区**：三处（LISP 代码写出、结果文件读取、params JSON）全部按英文 Windows 假设处理，在中文系统 + 天正环境下必乱码，且 cp1252 兜底会把乱码**静默放行**而非报错。
- 已由本人定稿 `src/t20_mcp/lisp_templates/tangent/_prelude.lsp`：环境保存/静默/恢复、局部 `*error*` 兜底、UNDO 组回滚、命令存在性预检（`t20mcp:call`）、`vl-cmdf` 防级联、编码契约注释。**模板与传输层必须按它迁移（见 P0-4/P0-2）。**

## P0 — 合入真机验证前必须完成（链路断裂 / 静默错误 / 环境破坏）

### P0-1 结果文件解码链错误
- **文件**：`src/t20_mcp/backends/file_ipc.py:166-173`
- **问题**：utf-8 失败后回退 cp1252。中文 Windows 上 AutoLISP `write-line` 写出 ANSI=cp936；cp1252 对任意字节几乎不抛 `UnicodeDecodeError`，中文 payload/error 会变乱码并被当作正常结果接受。
- **改法**：解码顺序改为 utf-8 → cp936（或 `locale.getpreferredencoding(False)`）→ 才允许 cp1252；注释同步改（"Windows-1252" 的说法仅对西文系统成立）。
- **验收**：单测——把含中文的 JSON 以 GBK 字节写入临时结果文件，`_dispatch` 读回后中文无损；纯 ASCII 路径不回归。
- ✅ done — `file_ipc._decode_result_bytes` 按 utf-8→cp936→系统 ANSI→cp1252 顺序解码，cp1252 退到最后；新增 `TestDecodeResultBytes` 验证 GBK 中文无损且 ASCII 不回归。

### P0-2 LISP 代码文件以 UTF-8 写出
- **文件**：`src/t20_mcp/backends/file_ipc.py:306`
- **问题**：AutoCAD `(load)` 在 2021 前只按 ANSI 代码页读 .lsp。模板含中文字符串（`wall_type` 默认值"砖墙"、中文图层名、潜在中文命令名），UTF-8 写出 → 加载即乱码 → 参数错/命令找不到，且无报错。
- **改法**：写出时 `encoding="gbk", errors="strict"`，捕获 `UnicodeEncodeError` 转为带字段提示的明确错误；仓库内模板保持 UTF-8，转码只发生在传输层（契约已写入 `_prelude.lsp` 头部，照它执行）。
- **验收**：渲染含"砖墙"的 wall 模板写出后以 GBK 读回逐字一致；注入 GBK 外字符（如 emoji）时报错信息含"GBK"与该参数内容。
- ✅ done — `execute_lisp` 改 `code.encode("gbk", errors="strict")` 后 `write_bytes`，`UnicodeEncodeError` 转含"GBK"+违规字符的明确错误；模板仍 UTF-8 存储，`TestExecuteLispGbk` 验证砖墙往返一致、emoji 被拒。

### P0-3 `lisp-code/` 目录缺失，dispatcher 引导链断裂
- **文件**：`src/t20_mcp/config.py:14`（`LISP_DIR` 指向项目根 `lisp-code/`，目录不存在）；`file_ipc.py:110-120` 的引导提示让用户加载一个不存在的文件。
- **改法**：建立项目自有 `lisp-code/`，从 `vendor/autocad-mcp/lisp-code/mcp_dispatch.lsp` 拷贝为适配起点，首批适配项：① 文件本身存为 ANSI/GBK 可加载；② 结果写出编码与 P0-1 约定一致；③ 顶部注释声明天正环境假设。`attribute_tools.lsp` 暂不迁移。
- **验收**：全新 clone 后，按 `initialize()` 失败提示中的 `(load ...)` 路径操作，ping 往返成功。
- ✅ done — 新建 `lisp-code/mcp_dispatch.lsp`（从 vendor 拷贝）：转为纯 ASCII 可在任意代码页 `(load)`，IPC 文件名前缀对齐 Python 侧 `t20_mcp_cmd_/result_`，IPC 目录改为读 env 否则 `%TEMP%/t20_mcp`（与 config.py 对齐），结果仍用 `(open "w")` 写 ANSI=GBK，顶部声明 T20 环境与编码契约；`config.LISP_DIR` 已指向该目录。（真机 ping 往返待 T20 环境实测）

### P0-4 六个模板迁移到 prelude 骨架（消除状态污染与级联失控）
- **文件**：`src/t20_mcp/lisp_templates/tangent/{axis_grid,wall,door,window,dimension,export_t3}.lsp`；`src/t20_mcp/tools/tangent.py` 的 `_render`（tangent.py:174）
- **问题**：①全部模板把 setvar 恢复写在主体尾部、**无 `*error*`**——命令中途失败（低置信序列下是常态）即把用户环境永久留在 CMDDIA/FILEDIA/OSMODE=0；②直接 `(command "推测命令名" ...)`，未知命令时后续参数被当命令行输入级联执行（wall 模板的 "L" 会触发 LINE 画垃圾实体），同时 OK 标记照常打印（假成功）。
- **改法**：每个模板改写为 `_prelude.lsp` 文末骨架形态（`t20mcp:begin` / 局部 `*error*` 接 `t20mcp:on-error` / `t20mcp:call` / `end`/`fail` 分支），删除全部手写 setq/setvar；`_render`（或 file_ipc 下发层，二选一并写明）把 prelude 拼接在渲染产物之前；export_t3 不再单独管 FILEDIA（prelude 已覆盖）。
- **验收**：离线测试——渲染产物括号平衡、含 `t20mcp:begin` 且不含裸 `setvar "CMDDIA"`；真机测试——故意改错命令名执行，命令行出现 `T20MCP-ERR`，且 CMDDIA/FILEDIA/OSMODE 三值与执行前一致、图中无新增垃圾实体。
- ✅ done — 6 模板全部改写为 `t20mcp:begin`/局部 `*error*`/`t20mcp:call`/`end`/`fail` 骨架，删尽手写 setq/setvar，坐标走 `t20mcp:pt`，export_t3 不再单独管 FILEDIA；`_render` 在产物前拼接 `_prelude.lsp`；`test_generates_balanced_lisp` 断言含 `t20mcp:begin`、无裸 `setvar "CMDDIA"`、括号平衡。（真机 T20MCP-ERR/环境一致性待实测）

### P0-5 未验证序列默认不下发（dry-run 默认开）
- **文件**：`src/t20_mcp/tools/tangent.py`（工具入口，约 tangent.py:340 之后的 MCP 工具函数）
- **问题**：序列全为推测，当前工具一调用就真发 AutoCAD。
- **改法**：加 `execute: bool = False` 参数：默认只返回渲染后的 LISP（dry-run）；`execute=True` 才走 `execute_lisp`，且对置信度"低"的子命令（axis_grid/door/window）在返回 payload 附 `warning: 未经真机验证`。docstring 同步说明。
- **验收**：默认调用不产生任何 IPC 文件；`execute=True` 时行为不变；低置信子命令返回含 warning 字段。
- ✅ done — `tangent` 工具加 `execute: bool = False`，默认返回 `{dry_run, lisp, ...}` 不触碰 backend；`execute=True` 才走 `execute_lisp`；`axis_grid/door/window` 在 dry-run 与执行成功 payload 均附 `warning`；docstring 同步；`TestTangentDryRun` 5 例验证（含 backend 不被调用、warning 字段）。

## P1 — 真机联调开始前应完成

### P1-1 窗口识别改为进程名主判据
- **文件**：`src/t20_mcp/backends/file_ipc.py:34-53`
- **问题**：现在要求标题同时含 "autocad" 和 ("drawing"|".dwg")。天正启动器可能把主窗标题改成 "T20天正建筑 Vxx…"（不含 autocad）；标题方案对多实例也不确定（`windows[0]`）。Gemini 清单第 1 点方向认可，给具体判据如下。
- **改法**：`EnumWindows` 后用 `GetWindowThreadProcessId` 取 PID → 进程映像名等于 `acad.exe`（可配置）为主判据；标题含 "autocad"/"天正"/"tarch" 为辅；多命中时优先含 ".dwg" 者并记 warning 日志；错误文案去掉 "LT" 字样（file_ipc.py:89）。
- **验收**：T20 环境下能找到窗口；同机再开一个普通 AutoCAD 时日志给出多实例警告且选择可解释。
- ✅ done — `find_autocad_window` 改用 `GetWindowThreadProcessId` + `QueryFullProcessImageNameW`，进程映像名等于 `acad.exe`（env `AUTOCAD_MCP_ACAD_PROCESS` 可配）为主判据，标题 autocad/天正/tarch 为辅，多命中优先 .dwg 并记 `multiple_autocad_windows` 警告；window-not-found 与 dispatcher 引导文案去掉 "LT"。（真机多实例选择待实测）

### P1-2 dispatch 触发前的模态对话框防护
- **文件**：`src/t20_mcp/backends/file_ipc.py:216-237`
- **问题**：每次 dispatch 无条件向 MDIClient 发 ESC×2 再发触发串。天正模态对话框打开时：ESC 可能取消用户正在进行的操作；触发串被对话框消息循环吞掉 → 只剩超时，无诊断。
- **改法**：发送前检测目标进程是否有启用的模态弹窗（`GetLastActivePopup` / 枚举同线程可见对话框类 `#32770`），有则直接返回明确错误"AutoCAD 正被对话框阻塞，请关闭后重试"；ESC 改为仅在上一次请求超时后的首次重发前注入。
- **验收**：手动打开天正"绘制轴网"对话框后调用任意工具，秒级返回阻塞错误，对话框保持原状；正常空闲时行为不回归。
- ✅ done — dispatch 前 `_autocad_modal_dialog_present`（GetLastActivePopup + 同线程 `#32770` 枚举）命中即返回"AutoCAD 正被对话框阻塞，请关闭后重试"且不发触发串；ESC 改为仅在 `_needs_cancel`（上次超时）时注入；`TestModalDialogGuard` 两例验证阻塞短路与 ESC 时机。（天正自绘框非 #32770 时为 best-effort，已注明）

### P1-3 参数层加 GBK 可编码校验
- **文件**：`src/t20_mcp/tools/tangent.py`（`_require_str`，约 tangent.py:80-100 区域）
- **改法**：校验 `value.encode("gbk")` 可行，失败抛 `ParamError` 并指明字段名与违规字符；作为 P0-2 `errors="strict"` 之前的友好防线。
- **验收**：现有 43 测试不回归；新增用例 `layer="测试🔥"` 被拒且报错含字段名。
- ✅ done — `_require_str` 末尾加 `value.encode("gbk")` 校验，失败抛含字段名与违规字符的 `ParamError`；`test_non_gbk_layer_rejected_with_field`（match "layer"）+ `test_gbk_chinese_layer_accepted` 验证；原有用例全绿。

### P1-4 真机验证执行顺序与文档回填
- **文件**：`docs/T20_COMMANDS.md`、6 个模板
- **改法**：按"中置信先行"排程：wall、dimension → export_t3 → axis_grid、door、window。每条核实后回填别名/序列、升置信度、同步改模板命令名；`export_t3` 在 §1.9 的"CMDDIA绕过=部分(FILEDIA=0)"与综合置信度"中"应下调为"低"并交叉引用 §0 坑 1（天正自绘导出框大概率不理会 FILEDIA）——文档当前自相矛盾。
- **验收**：表中无"待验证"且置信度为高的条目，对应模板在真机各跑通一次并截图存档。
- ✅ done（文档部分）— T20_COMMANDS.md §1.9 与 §2 的 export_t3 统一下调为「低」并交叉引用 §0 坑 1（消除"中"的自相矛盾）；新增 §3.1「中置信先行」验证排程（wall/dimension → export_t3 → axis_grid/door/window）。真机录制别名/序列、升置信度、截图存档仍需 T20 环境，留待执行排程。

## P2 — 排期内改进

- **P2-1** `file_ipc.py:157`：params JSON 用默认 `ensure_ascii=True`，中文参数变 `\uXXXX`，LISP 简易解析器不会解码。tangent 路径不经 params 暂不致命；后续要么 dispatcher 解析器支持 `\u`，要么 `ensure_ascii=False` + 按 P0 编码约定写出。验收：经 params 通道传中文图层名往返无损。
  - ✅ done — 命令文件改 `json.dumps(ensure_ascii=False)` + `encode("gbk", errors="replace")` 写出（与 .lsp 同走系统 ANSI=GBK 契约）；`test_chinese_params_written_as_gbk_not_unicode_escape` 验证无 `\u` 转义且 GBK 解码出中文。（真机经 dispatcher 往返待实测）
- **P2-2** `tangent.py:142-171`：`is_paren_balanced` 不识别 `;| ... |;` 块注释。已在 prelude 中以规范禁止块注释；可再加一条 lint（模板含 `;|` 即拒绝）。验收：含块注释的模板渲染时被明确拒绝。
  - ✅ done — `_render` 在 token 替换前 `if ";|" in body: raise ParamError`；`test_block_comment_template_rejected` 验证含块注释模板被拒。
- **P2-3** `tangent.py:321` 附近：`out_path` 建议在校验后统一 normalize 为正斜杠再注入，消除 FILEDIA=0 命令行交互下的反斜杠歧义。验收：传入反斜杠路径，渲染产物中为正斜杠。
  - ✅ done — `_gen_export_t3` 校验后 `out_path.replace("\\", "/")`；`test_export_path_backslash_normalized_to_slash` 验证产物为正斜杠。
- **P2-4** IPC 目录默认 `C:/temp`（`config.py:15`）：采纳 Gemini 清单第 4 点，默认改 `%TEMP%` 下子目录，保留环境变量覆盖。验收：无 C 盘根写权限的账户可正常往返。
  - ✅ done — `config.IPC_DIR` 默认改 `%TEMP%/t20_mcp`（`AUTOCAD_MCP_IPC_DIR` 仍可覆盖），dispatcher `t20mcp:resolve-ipc-dir` 用同规则解析，两端一致。
- **P2-5** 模板头注释把 `{{TOKEN}}` 写成"«TOKEN» (双花括号)"，表述自相矛盾，统一为 `{{TOKEN}}`（6 个模板同改，P0-4 迁移时顺手完成）。
  - ✅ done — 6 模板头注释统一为"占位符形如 `{{TOKEN}}`"（随 P0-4 重写完成）；`_render` 残留占位符自检改为忽略注释，避免误判该说明文字。
- **P2-6** Gemini 清单第 3 点（TExplode 分解天正对象供 ezdxf 读取）批注：方向可行，但 `T81_TExplode` 命令名同属未验证推测，且分解是**破坏性**操作——方案必须限定在临时副本文件上执行，禁止在用户当前图纸上分解。落地前先在 T20_COMMANDS.md 补该命令条目。
  - ✅ done — T20_COMMANDS.md §1.9 新增 `T81_TExplode`（置信度低）条目 + 批注，明确"未验证命令名 + 破坏性 + 仅在临时副本上执行、禁止分解当前图纸"。

## 边界声明

- prelude 中 `vl-cmdf` 对未知命令的级联拦截效果、`getcname` 对天正 ARX 命令的可见性，均标注"待真机确证"——预检 + cancel + UNDO 组是三层互补防线，不依赖单点成立。
- 本审查未通读仓库（按预算约束），结论基于：两份 handoff、T20_COMMANDS.md、diff stat、`file_ipc.py`/`tangent.py`/`wall.lsp`/`export_t3.lsp`/`T20_ADAPTATION_PLAN.md` 的定点片段与全仓 grep。若 dispatcher 实际下发机制与 vendor 版有出入，P0-1/P0-2 的编码结论不变（取决于 AutoCAD 行为，与 dispatcher 实现无关）。
