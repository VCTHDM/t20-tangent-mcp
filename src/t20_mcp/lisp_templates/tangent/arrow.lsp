;;; ============================================================================
;;; tangent::arrow  —  箭头引注
;;; 命令: TARROW   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 箭头起点 → 直段下一点 → 回车(结束本引线) → 回车(退出循环), 生成 TCH_ARROW。
;;;       两点连出引线后命令仍 active, 必须补两个空回车: 第一个结束当前引线的
;;;       "直段下一点<结束>"循环, 第二个退出"箭头起点<退出>"外层循环。
;;;       引注文字可经 ActiveX 注入 Text(上标)/Text2(下标) (Handoff 35 真机
;;;       验证, itest_40); 未提供参数时走天正面板记忆值; 样式仍走面板。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-arrow ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "arrow"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TARROW"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     ""
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_ARROW。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_ARROW"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
{{COM_INJECT}}
        (t20mcp:end "arrow" t20mcp:saved))
      (t20mcp:fail "arrow" t20mcp:saved "no-TCH_ARROW-created"))
  (princ))
(c:t20mcp-arrow)
