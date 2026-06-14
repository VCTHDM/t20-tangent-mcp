;;; ============================================================================
;;; tangent::multi_stair  —  多跑楼梯
;;; 命令: TMULTISTAIR   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 起点 → 下一点 → 回车退出, 生成 TCH_MULTISTAIR。
;;;       命令是循环式: 起点→下一点 定义一跑后回到"起点<退出>", 必须补空回车退出
;;;       整个命令 (在"起点<退出>"处空回车走 <退出> 默认收尾)。
;;;       跑数/梯段宽/踏步数/楼梯高等构造参数走天正面板记忆值, 只参数化起点与方向点。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-multi_stair ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "multi_stair"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TMULTISTAIR"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_MULTISTAIR。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_MULTISTAIR"))
      (t20mcp:end "multi_stair" t20mcp:saved)
      (t20mcp:fail "multi_stair" t20mcp:saved "no-TCH_MULTISTAIR-created"))
  (princ))
(c:t20mcp-multi_stair)
