;;; ============================================================================
;;; tangent::wall  —  绘制墙体 (单段)
;;; 命令推测: TGWall / 绘制墙体   置信度: 中 — 命令名较可靠, 参数序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 注: 当前模板仅生成单段墙体 (两点), 多段墙体待扩展。
;;; ============================================================================
(defun c:t20mcp-wall ( / *cmddia* *cmdecho* *osmode* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *osmode*  (getvar "OSMODE"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
{{SET_LAYER}}
  ;; 左宽 / 右宽 / 高度 / 墙类型, 再给出起点与终点
  (command "TGWall"
           "L" "{{LEFT_WIDTH}}"
           "R" "{{RIGHT_WIDTH}}"
           "H" "{{HEIGHT}}"
           "T" "{{WALL_TYPE}}"
           "{{X1}},{{Y1}}"
           "{{X2}},{{Y2}}"
           "")
  (setvar "OSMODE"  *osmode*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK wall")
  (princ)
)
(c:t20mcp-wall)
