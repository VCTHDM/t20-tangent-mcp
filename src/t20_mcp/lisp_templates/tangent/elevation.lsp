;;; ============================================================================
;;; tangent::elevation  —  标高标注
;;; 命令: TMELEV   置信度: 低 — 2026-06-12 仅一次双点序列生成 TCH_ELEVATION
;;; 序列: 标高基准点 → 标注放置点 → 回车。
;;;   注意: 单点序列真机会挂起等待输入, 且该事故后 AutoCAD 闪退; 本模板永远注入
;;;   两个点, 以避免点不足的交互状态。
;;;   标高文字可经 ActiveX 注入 Text (Handoff 35 真机验证, itest_40);
;;;   未提供参数时由天正按基准点自动计算 (如 "0.00000")。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-elevation ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "elevation"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TMELEV"
               (list (t20mcp:pt {{BASE_X}} {{BASE_Y}})
                     (t20mcp:pt {{LABEL_X}} {{LABEL_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: 2026-06-12 实测新实体类型为 TCH_ELEVATION。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_ELEVATION"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
{{COM_INJECT}}
        (t20mcp:end "elevation" t20mcp:saved))
      (t20mcp:fail "elevation" t20mcp:saved "no-TCH_ELEVATION-created"))
  (princ))
(c:t20mcp-elevation)
