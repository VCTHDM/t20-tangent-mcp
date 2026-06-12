;;; ============================================================================
;;; tangent::door  —  插入门 (普通门)
;;; 命令: TOPENING   置信度: 中 — 真机部分验证 (2026-06-12, T20 V10):
;;;   墙上插入点 → 回车 可生成 TCH_OPENING (非模态参数面板, 不阻塞);
;;;   Width/Height/DoorSill 可经 ActiveX 注入 (真机回读验证)。
;;;   遗留: 门/窗类型取决于门窗面板当前模式 (默认门), 命令行/COM 强制切换待验证。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 门需在已有墙体上定位, 插入点必须落在墙段上。
;;; ============================================================================
(defun c:t20mcp-door ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "door"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TOPENING"
               (list (t20mcp:pt {{INS_X}} {{INS_Y}}) ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: 以新增 TCH_OPENING 为成功判据 (插入点不在墙上时无实体)。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_OPENING"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
        (foreach pv (list (cons "Width" (float {{WIDTH}}))
                          (cons "Height" (float {{HEIGHT}}))
                          (cons "DoorSill" (float {{SILL_DISTANCE}})))
          (vl-catch-all-apply 'vlax-put-property (list t20mcp:obj (car pv) (cdr pv))))
        (t20mcp:end "door" t20mcp:saved))
      (t20mcp:fail "door" t20mcp:saved "no-TCH_OPENING-created (插入点是否在墙上?)"))
  (princ))
(c:t20mcp-door)
