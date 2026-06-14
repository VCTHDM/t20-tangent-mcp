;;; ============================================================================
;;; tangent::tree  —  任意布树 (单棵)
;;; 命令: TSINGLETREE   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 插入点 → 回车退出循环, 插入树木图块 (INSERT, 块名形如 "tree1")。
;;;       命令是循环式: 每点一棵, 给完插入点后回到"插入点", 必须补空回车退出。
;;;       树种/尺寸走天正面板记忆值; 树是普通图块, 实体类型为通用 INSERT。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-tree ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "tree"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TSINGLETREE"
               (list (t20mcp:pt {{X}} {{Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: 树为普通图块, T20 V10 实测新实体类型为 INSERT (块名形如 "tree1")。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "INSERT"))
      (t20mcp:end "tree" t20mcp:saved)
      (t20mcp:fail "tree" t20mcp:saved "no-INSERT-created"))
  (princ))
(c:t20mcp-tree)
