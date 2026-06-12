;;; ============================================================================
;;; tangent::export_t3  —  图形导出 / 导出天正3 (T3 旧版格式)
;;; 命令推测: T20_Export / 图形导出 / 导出T3   置信度: 中 — 命令存在, 静默导出路径写法待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 «TOKEN» (双花括号)。
;;; 注: "图形导出" 通常弹出文件对话框, 这里尝试用 FILEDIA=0 + 路径参数静默导出。
;;; ============================================================================
(defun c:t20mcp-export-t3 ( / *cmddia* *cmdecho* *filedia* )
  (setq *cmddia*  (getvar "CMDDIA"))
  (setq *cmdecho* (getvar "CMDECHO"))
  (setq *filedia* (getvar "FILEDIA"))
  (setvar "CMDDIA" 0)
  (setvar "CMDECHO" 0)
  (setvar "FILEDIA" 0)
  ;; 目标版本=天正3 / 输出文件路径
  (command "T20_Export"
           "{{TARGET_VER}}"
           "{{OUT_PATH}}"
           "")
  (setvar "FILEDIA" *filedia*)
  (setvar "CMDDIA"  *cmddia*)
  (setvar "CMDECHO" *cmdecho*)
  (princ "\nT20MCP-OK export_t3")
  (princ)
)
(c:t20mcp-export-t3)
