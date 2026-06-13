;;; ============================================================================
;;; tangent::column  —  标准柱
;;; 命令: TGCOLUMN   置信度: 高 — 真机最小序列验证 (2026-06-13, Handoff 12):
;;;   插入点 -> 生成 1 个 TCH_COLUMN, 命令自动结束。截面尺寸使用标准柱面板
;;;   当前记忆值; 角度属性名尚未确认, 仅做非致命候选注入。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-column ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "column"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TGCOLUMN"
               (list (t20mcp:pt {{X}} {{Y}})))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: TGColumn 点序列已验证, 仍以新增 TCH_COLUMN 为成功判据。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_COLUMN"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
        ;; 角度 ActiveX 属性名待真机确认; 候选写入失败不影响柱创建成功。
        (foreach p (list "Angle" "Rotation")
          (vl-catch-all-apply 'vlax-put-property (list t20mcp:obj p (float {{ANGLE}}))))
        (t20mcp:end "column" t20mcp:saved))
      (t20mcp:fail "column" t20mcp:saved "no-TCH_COLUMN-created"))
  (princ))
(c:t20mcp-column)
