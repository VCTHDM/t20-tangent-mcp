;;; ============================================================================
;;; tangent::wall  —  绘制墙体 (单段)
;;; 命令推测: TGWall / 绘制墙体   置信度: 中 — 命令名较可靠, 参数序列待真机验证
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; 注: 当前模板仅生成单段墙体 (两点), 多段墙体待扩展。
;;; ============================================================================
(defun c:t20mcp-wall ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "wall"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  ;; 左宽 / 右宽 / 高度 / 墙类型, 再给出起点与终点
  (if (t20mcp:call "TGWall"
                   (list "L" "{{LEFT_WIDTH}}"
                         "R" "{{RIGHT_WIDTH}}"
                         "H" "{{HEIGHT}}"
                         "T" "{{WALL_TYPE}}"
                         (t20mcp:pt {{X1}} {{Y1}})
                         (t20mcp:pt {{X2}} {{Y2}})
                         ""))
      (t20mcp:end "wall" t20mcp:saved)
      (t20mcp:fail "wall" t20mcp:saved "command-failed-or-unknown"))
  (princ))
(c:t20mcp-wall)
