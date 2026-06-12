;;; ============================================================================
;;; tangent::dimension  —  逐点标注 (两点尺寸)
;;; 命令推测: TDim / 逐点标注   置信度: 中 — 命令名较可靠, 拾取序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 注: 以两个标注点 + 一个尺寸线位置点驱动, 多点连续标注待扩展。
;;; ============================================================================
(defun c:t20mcp-dimension ( / *cmddia* *cmdecho* *osmode* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *osmode*  (getvar "OSMODE"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
{{SET_LAYER}}
  ;; 尺寸线位置点 -> 第一标注点 -> 第二标注点 -> 回车结束
  (command "TDim"
           "{{POS_X}},{{POS_Y}}"
           "{{P1_X}},{{P1_Y}}"
           "{{P2_X}},{{P2_Y}}"
           "")
  (setvar "OSMODE"  *osmode*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK dimension")
  (princ)
)
(c:t20mcp-dimension)
