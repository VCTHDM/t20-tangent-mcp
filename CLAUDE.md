# 项目目标
开发一个适配 T20 天正建筑（Windows + 完整版 AutoCAD + T20）的 MCP Server。上游项目针对 AutoCAD LT，本项目重点是对其 IPC、绘图与 LISP 调用机制进行天正环境适配，增强其针对建筑类专业实体的能力。

# 目录结构
- `src/t20_mcp/`: MCP Server 核心 Python 代码
- `lisp-code/`: 适配 AutoCAD 与天正的 LISP 代码
- `docs/`: 架构与设计文档
- `vendor/autocad-mcp/`: 上游仓库源码参考

# 编码约定
- 语言环境：Python 3.10+，使用 `uv` 管理依赖
- 类型约束：必须添加完整的 Python Type Hint 注解
- 铁律：**所有天正命令封装必须走 LISP 模板 + 参数注入，不允许硬编码键击序列**。

