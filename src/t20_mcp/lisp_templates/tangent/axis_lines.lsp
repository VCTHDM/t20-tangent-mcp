;;; ============================================================================
;;; tangent::axis_lines  —  轴网替代路径 (原生 LINE 网格)
;;; 命令: 无天正命令; 使用 entmake 创建普通 LINE。
;;; 置信度: 中 — 作为 TRectAxis 弹框命令的安全替代, 不生成 TCH 轴网智能对象。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-axis-lines ( / t20mcp:saved *error* t20mcp:made t20mcp:seg)
  (setq t20mcp:saved (t20mcp:begin "axis_lines"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:made 0)
  (foreach t20mcp:seg (list {{SEGMENTS}})
    (if (entmake
          (list (cons 0 "LINE")
                (cons 10 (list (nth 0 t20mcp:seg) (nth 1 t20mcp:seg) 0.0))
                (cons 11 (list (nth 2 t20mcp:seg) (nth 3 t20mcp:seg) 0.0))))
        (setq t20mcp:made (1+ t20mcp:made))))
  (if (= t20mcp:made {{EXPECTED_COUNT}})
      (t20mcp:end "axis_lines" t20mcp:saved)
      (t20mcp:fail "axis_lines" t20mcp:saved "line-count-mismatch"))
  (princ))
(c:t20mcp-axis-lines)
