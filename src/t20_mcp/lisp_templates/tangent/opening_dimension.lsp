;;; ============================================================================
;;; tangent::opening_dimension  —  门窗标注
;;; 命令: TDIM3   置信度: 高 — 真机验证 (2026-06-13, T20 V10 / AutoCAD 2024)
;;; 序列: 线选起点 → 线选终点 → 回车, 生成 TCH_DIMENSION2。
;;;   线选段应穿过需要标注的墙体/门窗。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-opening-dimension ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "opening_dimension"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TDIM3"
               (list (t20mcp:pt {{P1_X}} {{P1_Y}})
                     (t20mcp:pt {{P2_X}} {{P2_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (wcmatch (cdr (assoc 0 (entget t20mcp:new))) "TCH_DIM*"))
      (t20mcp:end "opening_dimension" t20mcp:saved)
      (t20mcp:fail "opening_dimension" t20mcp:saved "no-TCH_DIM-created"))
  (princ))
(c:t20mcp-opening-dimension)
