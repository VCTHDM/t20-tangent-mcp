;;; ============================================================================
;;; tangent::wall  —  绘制墙体 (单段)
;;; 命令: TGWALL   置信度: 高 — 真机已验证 (2026-06-12, T20 V10 / AutoCAD 2024)
;;; 序列: 起点 → 终点 → 回车 (使用门窗参数面板记忆值), 生成 TCH_WALL。
;;;   注意: 命令行不接受 L/R/H/T 关键字 (真机证实输入被吞掉且 0 实体 = 假成功),
;;;   左/右宽、高度、材料一律经 ActiveX 属性注入: LeftWidth/RightWidth/Height/Style。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; ============================================================================
(defun c:t20mcp-wall ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:obj)
  (setq t20mcp:saved (t20mcp:begin "wall"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
{{SET_LAYER}}
  (setq t20mcp:prev (entlast))
  (t20mcp:call "TGWALL"
               (list (t20mcp:pt {{X1}} {{Y1}}) (t20mcp:pt {{X2}} {{Y2}}) ""))
  (setq t20mcp:new (entlast))
  ;; 实体增量校验: vl-cmdf 返回值不可靠 (假成功见上), 以新增 TCH_WALL 实体为准。
  (if (and t20mcp:new
           (not (eq t20mcp:prev t20mcp:new))
           (= (cdr (assoc 0 (entget t20mcp:new))) "TCH_WALL"))
      (progn
        (setq t20mcp:obj (vlax-ename->vla-object t20mcp:new))
        (foreach pv (list (cons "LeftWidth" (float {{LEFT_WIDTH}}))
                          (cons "RightWidth" (float {{RIGHT_WIDTH}}))
                          (cons "Height" (float {{HEIGHT}})))
          (vl-catch-all-apply 'vlax-put-property (list t20mcp:obj (car pv) (cdr pv))))
        ;; 墙体材料 (Style): 真机回读默认值为 "砖"; 无效材料名由 catch 吞掉, 不致命。
        (vl-catch-all-apply 'vlax-put-property (list t20mcp:obj "Style" "{{WALL_TYPE}}"))
        (t20mcp:end "wall" t20mcp:saved))
      (t20mcp:fail "wall" t20mcp:saved "no-TCH_WALL-created"))
  (princ))
(c:t20mcp-wall)
