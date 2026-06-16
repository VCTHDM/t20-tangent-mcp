;;; ============================================================================
;;; tangent::line_pattern  -- line pattern
;;; Command: TLINEPATTERN. Verified on real T20 V10 / AutoCAD 2024 (2026-06-15).
;;; Sequence: start point -> end point -> Enter -> Enter, creates TCH_PATH_ARRAY.
;;; The second Enter exits the command loop cleanly.
;;; ----------------------------------------------------------------------------
;;; t20_mcp/tools/tangent.py injects placeholders such as {{TOKEN}} before dispatch.
;;; State management lives in _prelude.lsp; do not hand-write setq/setvar here.
;;; ============================================================================
(defun c:t20mcp-line_pattern ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "line_pattern"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TLINEPATTERN"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     ""
                     ""))
  (setq t20mcp:new (entlast))
  ;; Real-machine entity check: T20 V10 creates TCH_PATH_ARRAY.
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_PATH_ARRAY"))
      (t20mcp:end "line_pattern" t20mcp:saved)
      (t20mcp:fail "line_pattern" t20mcp:saved "no-TCH_PATH_ARRAY-created"))
  (princ))
(c:t20mcp-line_pattern)
