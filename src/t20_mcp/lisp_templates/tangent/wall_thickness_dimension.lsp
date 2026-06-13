;;; ============================================================================
;;; tangent::wall_thickness_dimension  —  墙厚标注
;;; 命令: TDIMWALL   置信度: 高 — 真机验证 (2026-06-13, T20 V10 / AutoCAD 2024)
;;; 序列: 直线第一点 → 直线第二点, 生成 TCH_DIMENSION2。
;;;   两点连线穿过墙体, 天正自动标注穿过的墙厚。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-wall-thickness-dimension ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "wall_thickness_dimension"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TDIMWALL"
               (list (t20mcp:pt {{P1_X}} {{P1_Y}})
                     (t20mcp:pt {{P2_X}} {{P2_Y}})))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (wcmatch (cdr (assoc 0 (entget t20mcp:new))) "TCH_DIM*"))
      (t20mcp:end "wall_thickness_dimension" t20mcp:saved)
      (t20mcp:fail "wall_thickness_dimension" t20mcp:saved "no-TCH_DIM-created"))
  (princ))
(c:t20mcp-wall-thickness-dimension)
