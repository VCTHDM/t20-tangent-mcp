;;; ============================================================================
;;; tangent::door  —  插入门 (普通门)
;;; 命令推测: TOpening / TDoor / 门窗   置信度: 低 — 门窗为强对话框命令, 序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 注: 门窗需在已有墙体上定位, 这里以插入点近似拾取所在墙段, 真机行为待验证。
;;; ============================================================================
(defun c:t20mcp-door ( / *cmddia* *cmdecho* *osmode* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *osmode*  (getvar "OSMODE"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
{{SET_LAYER}}
  ;; 类型=门 / 宽 / 高 / 距墙垛距离, 再在插入点拾取墙段
  (command "TOpening"
           "D"
           "W" "{{WIDTH}}"
           "H" "{{HEIGHT}}"
           "O" "{{SILL_DISTANCE}}"
           "{{INS_X}},{{INS_Y}}"
           "")
  (setvar "OSMODE"  *osmode*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK door")
  (princ)
)
(c:t20mcp-door)
