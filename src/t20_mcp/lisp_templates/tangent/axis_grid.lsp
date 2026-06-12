;;; ============================================================================
;;; tangent::axis_grid  —  直线轴网 (绘制轴网)
;;; 命令: TRectAxis (官方命令表 SYS\tchcmd.txt: 绘制轴网=TRectAxis/TArcAxis)
;;; 置信度: 不可执行 — 真机证实 (2026-06-12, T20 V10): 绘制轴网为模态对话框
;;;   (#32770, 上开/下开/左进/右进), 不可命令行驱动; 强制关闭对话框曾导致
;;;   AutoCAD 致命错误。本子命令在工具层禁止 execute, 仅供 dry-run 审阅。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 后续方向: UI 自动化填对话框, 或寻找天正暴露的 LISP/COM 轴网 API。
;;; ============================================================================
(defun c:t20mcp-axis-grid ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "axis_grid"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  ;; 基点 + 开间(横向轴线间距) + 进深(纵向轴线间距) + 旋转角 —— 序列为占位,
  ;; 真机为纯对话框命令, 此调用不会按参数生效 (工具层已禁止下发)。
  (if (t20mcp:call "TRECTAXIS"
                   (list (t20mcp:pt {{BASE_X}} {{BASE_Y}})
                         "H" "{{HSPACE}}"
                         "V" "{{VSPACE}}"
                         "A" "{{ANGLE}}"
                         ""))
      (t20mcp:end "axis_grid" t20mcp:saved)
      (t20mcp:fail "axis_grid" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-axis-grid)
