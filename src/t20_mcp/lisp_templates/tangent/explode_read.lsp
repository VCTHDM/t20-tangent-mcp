;;; ============================================================================
;;; tangent::explode_read  —  天正实体几何读回 (副本分解, 非破坏)
;;; 命令: 原生 _.EXPLODE   置信度: 高 — 真机验证 (2026-06-13, itest_25)
;;; 管线: COPY 目标实体到暂存区偏移 → EXPLODE 仅分解副本 → 走查产物
;;;   序列化几何 → UNDO 整组回滚。用户原实体全程不被修改。
;;; 选型记录 (itest_23/24): TEXPLODE 必弹「分解对象」模态框, 虽可经
;;;   dialog_automation 白名单点击驱动 (已验证), 但原生 _.EXPLODE 对 TCH_*
;;;   实体同样有效且**不弹框**, 故采用原生命令。
;;; 已知 T20 缺陷: 墙体 explode 输出 (TEXPLODE/EXPLODE 同源) 的起点侧顶点
;;;   会归零 (10 0 0 0); 墙体精确几何请改用 vlax-curve 起终点 + COM 宽度。
;;; 教训: 原位复制会触发天正「处理重合的墙体」框 — 偏移量必须远离既有实体;
;;;   COPY 默认多重复制, 位移点后必须补 "" 结束。
;;; ----------------------------------------------------------------------------
;;; 本文件由 t20_mcp/tools/tangent.py 注入参数后下发, 占位符形如 {{TOKEN}}。
;;; 状态管理走 _prelude.lsp, 模板内禁止手写 setq/setvar。
;;; t20mcp:result 为有意的全局: execute-lisp 以最后一个表达式为返回 payload。
;;; ============================================================================
(defun c:t20mcp-explode-read ( / t20mcp:saved *error* t20mcp:src t20mcp:ss
                                 t20mcp:mark t20mcp:e t20mcp:copy t20mcp:rc
                                 t20mcp:acc t20mcp:n)
  (setq t20mcp:result "")
  (setq t20mcp:saved (t20mcp:begin "explode_read"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:src (handent "{{HANDLE}}"))
  (if (null t20mcp:src)
      (t20mcp:fail "explode_read" t20mcp:saved "handle-not-found")
      (progn
        (setq t20mcp:mark (entlast))
        (setq t20mcp:ss (ssadd t20mcp:src (ssadd)))
        ;; 末尾 "" 必不可少: 2006+ 的 COPY 默认多重复制, 不回车则命令仍活,
        ;; 后续 TEXPLODE 输入会被灌进 COPY 提示, 副本几何被搅乱 (itest_25 教训)。
        (vl-cmdf "_.COPY" t20mcp:ss "" "_non" "0,0"
                 "_non" (t20mcp:pt {{OFF_X}} {{OFF_Y}}) "")
        (setq t20mcp:copy (entlast))
        (if (or (null t20mcp:copy) (eq t20mcp:copy t20mcp:mark))
            (t20mcp:fail "explode_read" t20mcp:saved "copy-failed")
            (progn
              (setq t20mcp:ss (ssadd t20mcp:copy (ssadd)))
              ;; call-nocheck: "_.EXPLODE" 带前缀, getcname 预检不适用; 原生命令必在。
              (setq t20mcp:rc (t20mcp:call-nocheck "_.EXPLODE" (list t20mcp:ss "")))
              (setq t20mcp:acc "")
              (setq t20mcp:n 0)
              (setq t20mcp:e (entnext t20mcp:mark))
              (while (and t20mcp:e (< t20mcp:n {{MAX_ENTITIES}}))
                (if (entget t20mcp:e)
                    (progn
                      (setq t20mcp:acc
                            (strcat t20mcp:acc (t20mcp:geo1 t20mcp:e) ";"))
                      (setq t20mcp:n (1+ t20mcp:n))))
                (setq t20mcp:e (entnext t20mcp:e)))
              (t20mcp:end "explode_read" t20mcp:saved)
              (vl-cmdf "_.U")
              (setq t20mcp:result
                    (strcat "rc=" (if t20mcp:rc "T" "nil")
                            " clean=" (if (eq (entlast) t20mcp:mark) "T" "nil")
                            " n=" (itoa t20mcp:n)
                            " data=" t20mcp:acc))))))
  (princ))
(c:t20mcp-explode-read)
t20mcp:result
