;;; ============================================================================
;;; tangent::export_t3  —  图形导出 / 导出天正3 (T3 旧版格式)
;;; 命令: TSAVEAS (真机存在)
;;; 置信度: 不可执行 — 真机证实 (2026-06-12, T20 V10): TSAVEAS 弹出天正自绘
;;;   导出框 (WPF HwndWrapper 窗口), 不理会 FILEDIA=0 (即编目 §0 坑 1),
;;;   IPC dispatch 会被阻塞直至人工关框。本子命令在工具层禁止 execute,
;;;   仅供 dry-run 审阅; 导出请人工操作或后续走 UI 自动化。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp (含 FILEDIA=0), 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-export-t3 ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "export_t3"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  ;; 目标版本=天正3 / 输出文件路径 —— 序列为占位, 真机为对话框命令 (见头注)。
  (if (t20mcp:call "TSAVEAS"
                   (list "{{TARGET_VER}}"
                         "{{OUT_PATH}}"
                         ""))
      (t20mcp:end "export_t3" t20mcp:saved)
      (t20mcp:fail "export_t3" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-export-t3)
