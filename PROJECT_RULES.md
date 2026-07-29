# 项目目标

开发一个适配 T20 天正建筑（Windows + 完整版 AutoCAD + T20）的 MCP Server。上游项目针对 AutoCAD LT，本项目重点是对其 IPC、绘图与 LISP 调用机制进行天正环境适配，增强其针对建筑类专业实体的能力。

# 目录结构

- `src/t20_mcp/`: MCP Server 核心 Python 代码
- `lisp-code/`: 适配 AutoCAD 与天正的 LISP 代码
- `scripts/`: 真机探针、回归和恢复脚本
- `tests/`: 不依赖 AutoCAD/T20 的离线测试
- `docs/`: 当前命令编目与历史 handoff 审计记录

# 开发约定

- 运行环境：Python 3.12，使用 `uv` 管理并通过已提交的 `uv.lock` 固定依赖。
- 格式与静态检查：以 `pyproject.toml` 中的 Ruff 配置为唯一来源。
- 类型约束：新增公共生产接口必须有 Python 类型注解；触及既有接口签名时同步补齐。
  历史真机探针与继承自已注解基类的旧 override 按实际维护范围逐步整理。
- 文本文件统一使用 UTF-8 与 LF；发给 AutoCAD/T20 的临时 LISP/JSON 只在 IPC 边界转为 GBK。

# 天正自动化铁律

- 常规子命令必须走 **LISP 模板 + 参数注入**，不得把面板键击序列拼进模板。
- 已有两个受控 GUI 例外：`column` 与 `door/window`。它们只允许使用
  `dialog_automation.py` 中经过真机验证的结构指纹与白名单 Win32 消息。
- GUI 指纹不匹配时必须安全失败；严禁 `WM_CLOSE`；`CMDACTIVE > 0` 期间不得发起 IPC。
- 成功必须由实体类型、数量和关键属性读回证明，不能只看命令返回值或按钮点击。

# 离线门禁

```powershell
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q
uv run python -m compileall -q src scripts tests
uv run python scripts/itest_19_mcp_stdio_smoke.py
git diff --check
```

真机脚本必须串行运行并持有 `scripts/_live_lock.py` 的互斥锁；历史真机结果不能冒充本轮复验。
