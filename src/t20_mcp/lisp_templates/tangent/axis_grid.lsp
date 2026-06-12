;;; ============================================================================
;;; tangent::axis_grid  —  直线轴网 (绘制轴网)
;;; 命令推测: TGAxisGrid / 直线轴网   置信度: 低 — 命令名与交互序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 铁律: 仅做 模板 + 参数注入, 不得在 Python 侧硬编码键击序列。
;;; ============================================================================
(defun c:t20mcp-axis-grid ( / *cmddia* *cmdecho* *osmode* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *osmode*  (getvar "OSMODE"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
{{SET_LAYER}}
  ;; 基点 + 开间(横向轴线间距) + 进深(纵向轴线间距) + 旋转角
  (command "TGAxisGrid"
           "{{BASE_X}},{{BASE_Y}}"
           "H" "{{HSPACE}}"
           "V" "{{VSPACE}}"
           "A" "{{ANGLE}}"
           "")
  (setvar "OSMODE"  *osmode*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK axis_grid")
  (princ)
)
(c:t20mcp-axis-grid)
