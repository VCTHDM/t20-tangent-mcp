;;; ============================================================================
;;; tangent::door  —  插入门 (普通门)
;;; 命令推测: TOpening / TDoor / 门窗   置信度: 低 — 门窗为强对话框命令, 序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 门窗需在已有墙体上定位, 这里以插入点近似拾取所在墙段, 真机行为待验证。
;;; ============================================================================
(defun c:t20mcp-door ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "door"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  ;; 类型=门 / 宽 / 高 / 距墙垛距离, 再在插入点拾取墙段
  (if (t20mcp:call "TOpening"
                   (list "D"
                         "W" "{{WIDTH}}"
                         "H" "{{HEIGHT}}"
                         "O" "{{SILL_DISTANCE}}"
                         (t20mcp:pt {{INS_X}} {{INS_Y}})
                         ""))
      (t20mcp:end "door" t20mcp:saved)
      (t20mcp:fail "door" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-door)
