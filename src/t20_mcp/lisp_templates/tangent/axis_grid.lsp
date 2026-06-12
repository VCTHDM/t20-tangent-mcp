;;; ============================================================================
;;; tangent::axis_grid  —  直线轴网 (绘制轴网)
;;; 命令推测: TGAxisGrid / 直线轴网   置信度: 低 — 命令名与交互序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理 (环境保存/静默/恢复、*error*、UNDO 回滚、命令预检) 全部走 _prelude.lsp,
;;; 模板内禁止手写 setq/setvar。铁律: 仅做 模板 + 参数注入, 不硬编码键击序列。
;;; ============================================================================
(defun c:t20mcp-axis-grid ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "axis_grid"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  ;; 基点 + 开间(横向轴线间距) + 进深(纵向轴线间距) + 旋转角
  (if (t20mcp:call "TGAxisGrid"
                   (list (t20mcp:pt {{BASE_X}} {{BASE_Y}})
                         "H" "{{HSPACE}}"
                         "V" "{{VSPACE}}"
                         "A" "{{ANGLE}}"
                         ""))
      (t20mcp:end "axis_grid" t20mcp:saved)
      (t20mcp:fail "axis_grid" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-axis-grid)
