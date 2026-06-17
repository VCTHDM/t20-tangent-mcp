;;; ============================================================================
;;; tangent::opening  —  插入门窗 (TOpening)
;;; 命令: TOPENING   置信度: 中 — 真机部分验证 (T20 V10):
;;;   墙上插入点 → 回车 可生成 TCH_OPENING (非模态参数面板, 不阻塞);
;;;   Width/Height/DoorSill 可经 ActiveX 注入 (Handoff 33 真机 sweep 验证)。
;;;   door 模式: 注入 DoorSill (距墙垛距离); 面板默认门模式; DXF group 71 = 0。
;;;   window 模式: 注入 DoorSill (实为窗台高 — TCH_OPENING 不暴露独立 SillHeight,
;;;     门/窗共用 DoorSill, 模式由面板 + DXF group 71 决定); group 71 = 1。
;;;     需先人工切面板到窗模式, 否则 TOpening 沿用门模式生成门对象。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-opening ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "{{MODE}}"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TOPENING"
               (list (t20mcp:pt {{INS_X}} {{INS_Y}}) ""))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_OPENING"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
{{COM_INJECT}}
        (t20mcp:end "{{MODE}}" t20mcp:saved))
      (t20mcp:fail "{{MODE}}" t20mcp:saved "no-TCH_OPENING-created (插入点是否在墙上?)"))
  (princ))
(c:t20mcp-opening)
