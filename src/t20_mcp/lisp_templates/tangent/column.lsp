;;; ============================================================================
;;; tangent::column  —  标准柱
;;; 命令: TGCOLUMN   状态: 仅 dry-run — 真机复测 (2026-06-13, Handoff 13):
;;;   TGCOLUMN 弹 #32770 标准柱面板且命令保持 active=1, vl-cmdf 点序列到不了
;;;   绘图区"放置"处理器 -> 0 实体。Handoff 12 记录的 delta=1 不可复现 (面板恰好
;;;   开着的顺序依赖假成功)。本模板仅供 dry-run 展示意图, execute 已在 tangent.py
;;;   的 EXECUTE_DISABLED_SUBCOMMANDS 禁用; 真正放置需面板 UI 自动化方案。
;;;   保留点序列骨架, 待 UI 自动化打通后复用。
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
