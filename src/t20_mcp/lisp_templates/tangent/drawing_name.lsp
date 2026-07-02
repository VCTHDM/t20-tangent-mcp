;;; ============================================================================
;;; tangent::drawing_name  —  图名标注
;;; 命令: TDRAWINGNAME   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 插入位置点 → 回车退出循环, 生成 TCH_DRAWINGNAME。
;;;       命令是循环式: 给完一点后回到"插入位置", 必须补空回车退出。
;;;       图名文字/比例文字可经 ActiveX 注入 NameText/ScaleText (Handoff 35
;;;       真机验证, itest_40); 未提供参数时走天正面板记忆值。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-drawing_name ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "drawing_name"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TDRAWINGNAME"
               (list (t20mcp:pt {{INS_X}} {{INS_Y}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_DRAWINGNAME。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_DRAWINGNAME"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
{{COM_INJECT}}
        (t20mcp:end "drawing_name" t20mcp:saved))
      (t20mcp:fail "drawing_name" t20mcp:saved "no-TCH_DRAWINGNAME-created"))
  (princ))
(c:t20mcp-drawing_name)
