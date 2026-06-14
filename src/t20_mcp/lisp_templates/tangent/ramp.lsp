;;; ============================================================================
;;; tangent::ramp  —  坡道
;;; 命令: TASCENT   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 点取位置 → 回车退出循环, 生成 TCH_ASCENT。
;;;       命令是循环式插入: 给完插入点后回到"点取位置", 必须补空回车退出。
;;;       坡道宽度/坡长等构造参数走天正面板记忆值, 本模板只参数化插入点。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-ramp ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "ramp"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TASCENT"
               (list (t20mcp:pt {{X}} {{Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_ASCENT。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_ASCENT"))
      (t20mcp:end "ramp" t20mcp:saved)
      (t20mcp:fail "ramp" t20mcp:saved "no-TCH_ASCENT-created"))
  (princ))
(c:t20mcp-ramp)
