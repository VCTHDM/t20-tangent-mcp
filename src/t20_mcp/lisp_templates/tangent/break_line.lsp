;;; ============================================================================
;;; tangent::break_line  —  加折断线 (单折断线)
;;; 命令: TSYMBCUT   置信度: 高 — 真机已验证 (2026-06-14, T20 V10 / AutoCAD 2024)
;;; 序列: 折断线起点 → 折断线终点 → 回车 (接受 <不切割> 默认), 生成 TCH_RUPTURE。
;;;       两点后命令仍 active, 必须补一个空回车跳过"选择保留范围"步骤才收尾。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-break_line ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "break_line"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TSYMBCUT"
               (list (t20mcp:pt {{X1}} {{Y1}})
                     (t20mcp:pt {{X2}} {{Y2}})
                     ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: T20 V10 实测新实体类型为 TCH_RUPTURE。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_RUPTURE"))
      (t20mcp:end "break_line" t20mcp:saved)
      (t20mcp:fail "break_line" t20mcp:saved "no-TCH_RUPTURE-created"))
  (princ))
(c:t20mcp-break_line)
