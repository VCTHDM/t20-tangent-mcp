;;; ============================================================================
;;; tangent::dimension  —  逐点标注 (两点尺寸)
;;; 命令: TDIMMP   置信度: 高 — 真机已验证 (2026-06-12, T20 V10 / AutoCAD 2024)
;;; 序列: 尺寸线位置点 → 标注点1 → 标注点2 → 回车, 生成 TCH_DIMENSION2。
;;;   (顺序 [点1 点2 回车 位置] 真机证实无效: 0 实体假成功。)
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 多点连续标注待扩展。
;;; ============================================================================
(defun c:t20mcp-dimension ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "dimension"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TDIMMP"
               (list (t20mcp:pt {{POS_X}} {{POS_Y}})
                     (t20mcp:pt {{P1_X}} {{P1_Y}})
                     (t20mcp:pt {{P2_X}} {{P2_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: 以新增 TCH_DIM* (T20 V10 实测 TCH_DIMENSION2) 为成功判据。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (wcmatch (cdr (assoc 0 (entget t20mcp:new))) "TCH_DIM*"))
      (t20mcp:end "dimension" t20mcp:saved)
      (t20mcp:fail "dimension" t20mcp:saved "no-TCH_DIM-created"))
  (princ))
(c:t20mcp-dimension)
