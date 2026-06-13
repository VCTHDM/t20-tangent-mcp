;;; ============================================================================
;;; tangent::rectangle  —  矩形 (天正矩形)
;;; 命令: TRECT   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 第一角点 → 第二角点 → 回车退出循环, 生成 TCH_RECT。
;;;       命令是循环式: 给完两角点后回到"第一个角点", 必须补空回车退出。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-rectangle ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "rectangle"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TRECT"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_RECT。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_RECT"))
      (t20mcp:end "rectangle" t20mcp:saved)
      (t20mcp:fail "rectangle" t20mcp:saved "no-TCH_RECT-created"))
  (princ))
(c:t20mcp-rectangle)
