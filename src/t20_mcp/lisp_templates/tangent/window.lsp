;;; ============================================================================
;;; tangent::window  —  插入窗 (普通窗)
;;; 命令: TOPENING   置信度: 低 — 真机部分验证 (2026-06-12, T20 V10):
;;;   墙上插入点 → 回车 可生成 TCH_OPENING; Width/Height 可经 ActiveX 注入。
;;;   遗留: ① 插入的门/窗类型取决于门窗面板当前模式 (默认是门, 非窗!);
;;;        ② SillHeight 属性在门模式对象上不存在, 窗台高注入待窗模式真机验证。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 窗需在已有墙体上定位, 插入点必须落在墙段上。
;;; ============================================================================
(defun c:t20mcp-window ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "window"))
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
                          ;; SillHeight 待窗模式验证, 失败由 catch 吞掉不致命。
                          (cons "SillHeight" (float {{SILL_HEIGHT}})))
          (vl-catch-all-apply 'vlax-put-property (list t20mcp:obj (car pv) (cdr pv))))
        (t20mcp:end "window" t20mcp:saved))
      (t20mcp:fail "window" t20mcp:saved "no-TCH_OPENING-created (插入点是否在墙上?)"))
  (princ))
(c:t20mcp-window)
