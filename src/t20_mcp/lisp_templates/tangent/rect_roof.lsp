;;; ============================================================================
;;; tangent::rect_roof  —  矩形屋顶
;;; 命令: TRECTROOF   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 左下角点 → 右下角点 → 右上角点 → 回车退出循环, 生成 TCH_MOUNTROOF。
;;;       命令是循环式: 给完三角点后回到"左下角点", 必须补空回车退出。
;;;       坡角/出檐/屋顶高等构造参数走天正面板记忆值, 本模板只参数化三角点。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-rect_roof ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "rect_roof"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TRECTROOF"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     (t20mcp:pt {{X3}} {{Y3}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_MOUNTROOF。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_MOUNTROOF"))
      (t20mcp:end "rect_roof" t20mcp:saved)
      (t20mcp:fail "rect_roof" t20mcp:saved "no-TCH_MOUNTROOF-created"))
  (princ))
(c:t20mcp-rect_roof)
