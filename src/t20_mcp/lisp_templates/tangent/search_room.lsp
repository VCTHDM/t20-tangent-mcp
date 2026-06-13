;;; ============================================================================
;;; tangent::search_room  —  搜索房间 (生成天正房间对象)
;;; 命令: TUPDSPACE   置信度: 高 — 真机验证 (2026-06-13, itest_26/27)
;;; 序列: 全图选择 TCH_WALL → 选择集 → 回车, 闭合墙体围合的区域生成
;;;   TCH_SPACE 房间对象。无闭合区域或无墙体时 0 实体 (fail 分支)。
;;; 限制: 对已有房间对象的图执行可能只更新不新建, 当前以新增 TCH_SPACE
;;;   为成功判据 (保守); 更新场景的判据待后续真机补充。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-search-room ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:ss)
  (setq t20mcp:saved (t20mcp:begin "search_room"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (setq t20mcp:ss (ssget "_X" '((0 . "TCH_WALL"))))
  (if (null t20mcp:ss)
      (t20mcp:fail "search_room" t20mcp:saved "no-walls-in-drawing")
      (progn
        (t20mcp:call "TUPDSPACE" (list t20mcp:ss ""))
        (setq t20mcp:new (entlast))
        (if (and t20mcp:new
                 (not (eq t20mcp:prev t20mcp:new))
                 (wcmatch (cdr (assoc 0 (entget t20mcp:new))) "TCH_SPACE*"))
            (t20mcp:end "search_room" t20mcp:saved)
            (t20mcp:fail "search_room" t20mcp:saved "no-TCH_SPACE-created"))))
  (princ))
(c:t20mcp-search-room)
