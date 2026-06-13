;;; ============================================================================
;;; tangent::step  —  台阶
;;; 命令: TSTEP   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 第一点 → 各转折点... → 回车结束, 生成 TCH_STEP。
;;;       台阶踏步数/宽度等走天正面板记忆值, 本模板只参数化轮廓点列。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-step ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "step"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TSTEP"
               (list {{POINTS}}
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_STEP。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_STEP"))
      (t20mcp:end "step" t20mcp:saved)
      (t20mcp:fail "step" t20mcp:saved "no-TCH_STEP-created"))
  (princ))
(c:t20mcp-step)
