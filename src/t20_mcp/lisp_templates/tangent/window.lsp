;;; ============================================================================
;;; tangent::window  —  插入窗 (普通窗)
;;; 命令推测: TOpening / TWindow / 门窗   置信度: 低 — 门窗为强对话框命令, 序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 注: 窗需在已有墙体上定位, 这里以插入点近似拾取所在墙段, 真机行为待验证。
;;; ============================================================================
(defun c:t20mcp-window ( / *cmddia* *cmdecho* *osmode* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *osmode*  (getvar "OSMODE"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
{{SET_LAYER}}
  ;; 类型=窗 / 宽 / 高 / 窗台高, 再在插入点拾取墙段
  (command "TOpening"
           "C"
           "W" "{{WIDTH}}"
           "H" "{{HEIGHT}}"
           "S" "{{SILL_HEIGHT}}"
           "{{INS_X}},{{INS_Y}}"
           "")
  (setvar "OSMODE"  *osmode*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK window")
  (princ)
)
(c:t20mcp-window)
