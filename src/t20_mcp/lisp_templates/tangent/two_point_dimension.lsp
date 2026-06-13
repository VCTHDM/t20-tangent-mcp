;;; ============================================================================
;;; tangent::two_point_dimension  —  两点标注
;;; 命令: TDIMTP   置信度: 高 — 真机验证 (2026-06-13, T20 V10 / AutoCAD 2024, Handoff 13)
;;; 序列: 起点 → 终点 → 标注位置 → 回车, 生成 TCH_DIMENSION2。
;;;   起点/终点连成一条"栏选/穿越线", 天正标注该线穿过的一排对象 (墙/柱/门窗/轴线)
;;;   的间距; 第三点定尺寸线位置; 末尾回车结束"增删尺寸对象"循环。
;;;   注意: 穿过的对象不足 (如单墙沿中线) 会报"对象数目太少", 不进标注位置步。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-two-point-dimension ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "two_point_dimension"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TDIMTP"
               (list (t20mcp:pt {{P1_X}} {{P1_Y}})
                     (t20mcp:pt {{P2_X}} {{P2_Y}})
                     (t20mcp:pt {{POS_X}} {{POS_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (wcmatch (cdr (assoc 0 (entget t20mcp:new))) "TCH_DIM*"))
      (t20mcp:end "two_point_dimension" t20mcp:saved)
      (t20mcp:fail "two_point_dimension" t20mcp:saved "no-TCH_DIM-created"))
  (princ))
(c:t20mcp-two-point-dimension)
