;;; ============================================================================
;;; tangent::export_t3  —  图形导出 / 导出天正3 (T3 旧版格式)
;;; 命令推测: T20_Export / 图形导出 / 导出T3   置信度: 低 — 天正自绘导出框大概率
;;;   不理会 FILEDIA=0 (见 docs/T20_COMMANDS.md §0 坑 1), 静默导出路径写法待真机验证。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp (含 FILEDIA=0), 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-export-t3 ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "export_t3"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  ;; 目标版本=天正3 / 输出文件路径 (FILEDIA 已由 prelude 置 0)
  (if (t20mcp:call "T20_Export"
                   (list "{{TARGET_VER}}"
                         "{{OUT_PATH}}"
                         ""))
      (t20mcp:end "export_t3" t20mcp:saved)
      (t20mcp:fail "export_t3" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-export-t3)
