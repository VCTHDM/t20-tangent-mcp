;;; ============================================================================
;;; tangent::dimension  —  逐点标注 (两点尺寸)
;;; 命令推测: TDim / 逐点标注   置信度: 中 — 命令名较可靠, 拾取序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 以两个标注点 + 一个尺寸线位置点驱动, 多点连续标注待扩展。
;;; ============================================================================
(defun c:t20mcp-dimension ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "dimension"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  ;; 尺寸线位置点 -> 第一标注点 -> 第二标注点 -> 回车结束
  (if (t20mcp:call "TDim"
                   (list (t20mcp:pt {{POS_X}} {{POS_Y}})
                         (t20mcp:pt {{P1_X}} {{P1_Y}})
                         (t20mcp:pt {{P2_X}} {{P2_Y}})
                         ""))
      (t20mcp:end "dimension" t20mcp:saved)
      (t20mcp:fail "dimension" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-dimension)
