;;; ============================================================================
;;; tangent::symmetry  —  画对称轴
;;; 命令: TSYMMETRY   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 起点 → 终点, 两点即收尾 (active=0), 生成 TCH_SYMMETRY。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-symmetry ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "symmetry"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TSYMMETRY"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_SYMMETRY。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_SYMMETRY"))
      (t20mcp:end "symmetry" t20mcp:saved)
      (t20mcp:fail "symmetry" t20mcp:saved "no-TCH_SYMMETRY-created"))
  (princ))
(c:t20mcp-symmetry)
