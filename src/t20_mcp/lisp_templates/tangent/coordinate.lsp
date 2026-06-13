;;; ============================================================================
;;; tangent::coordinate  —  坐标标注
;;; 命令: TCOORD   置信度: 高 — 真机已验证 (2026-06-13, T20 V10 / AutoCAD 2024)
;;; 序列: 标注点 → 坐标标注方向点 → 回车, 生成 TCH_COORD。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-coordinate ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "coordinate"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TCOORD"
               (list (t20mcp:pt {{POINT_X}} {{POINT_Y}})
                     (t20mcp:pt {{LABEL_X}} {{LABEL_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_COORD。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_COORD"))
      (t20mcp:end "coordinate" t20mcp:saved)
      (t20mcp:fail "coordinate" t20mcp:saved "no-TCH_COORD-created"))
  (princ))
(c:t20mcp-coordinate)
