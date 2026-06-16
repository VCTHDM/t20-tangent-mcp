;;; ============================================================================
;;; tangent::wheelchair_diameter  -- wheelchair turning diameter
;;; Command: TWHEELCHAIRDAIM. Verified on real T20 V10 / AutoCAD 2024 (2026-06-15).
;;; Sequence: center point -> radius/direction point -> Enter, creates TCH_RADIUSDIM.
;;; Official command spelling is Daim.
;;; ----------------------------------------------------------------------------
;;; t20_mcp/tools/tangent.py injects placeholders such as {{TOKEN}} before dispatch.
;;; State management lives in _prelude.lsp; do not hand-write setq/setvar here.
;;; ============================================================================
(defun c:t20mcp-wheelchair_diameter ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "wheelchair_diameter"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TWHEELCHAIRDAIM"
               (list (t20mcp:pt {{CENTER_X}} {{CENTER_Y}})
                     (t20mcp:pt {{EDGE_X}} {{EDGE_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; Real-machine entity check: T20 V10 entlast is TCH_RADIUSDIM.
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_RADIUSDIM"))
      (t20mcp:end "wheelchair_diameter" t20mcp:saved)
      (t20mcp:fail "wheelchair_diameter" t20mcp:saved "no-TCH_RADIUSDIM-created"))
  (princ))
(c:t20mcp-wheelchair_diameter)
