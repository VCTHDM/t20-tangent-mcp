;;; ============================================================================
;;; tangent::cusp_roof  —  攒尖屋顶
;;; 命令: TCUSPROOF   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 屋顶中心位置 → 第二点(定半径/朝向), 两点即收尾 (active=0), 生成 TCH_CUSPROOF。
;;;       边数/屋顶高等构造参数走天正面板记忆值, 本模板只参数化中心点与半径点。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-cusp_roof ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "cusp_roof"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TCUSPROOF"
               (list (t20mcp:pt {{CENTER_X}} {{CENTER_Y}})
                     (t20mcp:pt {{BASE_X}} {{BASE_Y}})))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_CUSPROOF。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_CUSPROOF"))
      (t20mcp:end "cusp_roof" t20mcp:saved)
      (t20mcp:fail "cusp_roof" t20mcp:saved "no-TCH_CUSPROOF-created"))
  (princ))
(c:t20mcp-cusp_roof)
