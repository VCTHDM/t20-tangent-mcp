;;; ============================================================================
;;; tangent::section_symbol  —  剖切符号
;;; 命令: TSECTION   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 第一剖切点 → 第二剖切点 → 剖视方向点 → 回车退出循环, 生成 TCH_SYMB_SECTION。
;;;       命令是循环式: 给完三点后会回到"第一个剖切点", 必须补空回车退出。
;;;       剖切编号文字走天正面板记忆值 (本模板只参数化几何)。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-section_symbol ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "section_symbol"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TSECTION"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     (t20mcp:pt {{DIR_X}} {{DIR_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_SYMB_SECTION。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_SYMB_SECTION"))
      (t20mcp:end "section_symbol" t20mcp:saved)
      (t20mcp:fail "section_symbol" t20mcp:saved "no-TCH_SYMB_SECTION-created"))
  (princ))
(c:t20mcp-section_symbol)
