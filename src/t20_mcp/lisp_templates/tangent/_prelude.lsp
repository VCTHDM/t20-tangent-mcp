;;; ============================================================================
;;; t20mcp tangent prelude — 天正(T20) + 完整版 AutoCAD 环境的防御性前置
;;;
;;; 本文件只定义函数与常量, 无顶层命令执行, 重复加载安全(幂等)。
;;; 传输层应在每个渲染后的模板前拼接本文件(或由 dispatcher 启动时加载一次)。
;;; 结果标记约定(供 Python 端 grep): T20MCP-OK / T20MCP-ERR / T20MCP-WARN。
;;; ----------------------------------------------------------------------------
;;; 【编码契约 — 必读, 全链路一致才不乱码】
;;; 1. 仓库内所有 .lsp 模板(含本文件)以 UTF-8 存储, 便于 git 与编辑器协作。
;;; 2. AutoCAD 的 (load) 在 2021 之前只按系统 ANSI 代码页解码 .lsp 文件;
;;;    中文 Windows 上 ANSI = GBK(cp936)。T20 常挂 2016~2022, 必须按最保守
;;;    情况处理: file_ipc 在把渲染后的 LISP 写盘给 AutoCAD (load) 之前,
;;;    必须整体由 UTF-8 转码为 GBK 写出, 且不带 BOM。
;;; 3. 反向通道相同: dispatcher 用 (write-line) 写出的结果文件是 ANSI/GBK;
;;;    Python 端必须按 cp936 读取。切勿用 cp1252 兜底 —— cp1252 对几乎任何
;;;    字节序列都"解码成功", 会把乱码静默放行而不是报错。
;;; 4. GBK 无法表示的字符(emoji、部分扩展区汉字)禁止进入模板参数,
;;;    应在 Python 校验层拦截(转码时 errors="strict" 作为最后防线)。
;;; 5. 天正若存在中文命令名, 经上述 GBK 通道下发可被识别; 但应优先使用
;;;    真机核实过的英文/拼音别名(见 docs/T20_COMMANDS.md), 缩小编码暴露面。
;;; 6. 原生 AutoCAD 命令一律写 "_.-XXX"/"_.XXX" 形式: 下划线取全局命令名,
;;;    句点取未被重定义的原版 —— 防天正对原生命令的本地化/重定义干扰。
;;; ============================================================================

(vl-load-com)
(setq t20mcp:*tag* nil)

;;; 需要保存/恢复的系统变量清单。
;;;  CMDDIA/FILEDIA — 对话框开关。注意: CMDDIA=0 只对 AutoCAD 原生命令生效,
;;;    天正自绘对话框(ObjectARX)多半不理会(见 docs/T20_COMMANDS.md §0 坑 1)。
;;;  OSMODE — 对象捕捉; 不清零会把注入坐标吸附到无关实体上。
;;;  ATTDIA/ATTREQ — 属性块的弹框/提示(天正图框等带属性块)。
;;;  EXPERT — =5 跳过"是否确认"类二次提示。注意它会改变命令交互流:
;;;    真机录制参数序列时也必须在 EXPERT=5 下录制, 否则序列对不上。
;;;  DIMZIN — 影响 rtos 的尾零输出, t20mcp:pt 依赖; 属存图变量, 必须恢复。
;;;  刻意不动 NOMUTT: 个别版本会连 princ 输出一并吞掉, 导致 OK/ERR 标记丢失。
(setq t20mcp:*env-vars*
      '("CMDDIA" "FILEDIA" "CMDECHO" "OSMODE" "ATTDIA" "ATTREQ" "EXPERT" "DIMZIN"))

(defun t20mcp:env-save ( / out val)
  ;; -> alist 形如 (("CMDDIA" . 1) ...), 只收录当前版本确实存在的变量。
  (foreach v t20mcp:*env-vars*
    (setq val (getvar v))
    (if (not (null val))
        (setq out (cons (cons v val) out))))
  out)

(defun t20mcp:env-restore (saved)
  ;; 逐项包 catch: 个别只读/缺失变量不应中断恢复其余变量。
  (foreach pair saved
    (vl-catch-all-apply 'setvar (list (car pair) (cdr pair))))
  (princ))

(defun t20mcp:env-quiet ()
  ;; 进入静默态(配合上面清单的说明)。
  (foreach pair '(("CMDECHO" . 0) ("CMDDIA" . 0) ("FILEDIA" . 0) ("OSMODE" . 0)
                  ("ATTDIA" . 0) ("ATTREQ" . 0) ("EXPERT" . 5) ("DIMZIN" . 8))
    (vl-catch-all-apply 'setvar (list (car pair) (cdr pair))))
  (princ))

(defun t20mcp:cancel-pending ( / )
  ;; 取消残留的活动命令(最多退 4 层嵌套)。官方文档不允许在 *error* 内调用
  ;; (command), 故整体包 catch: 失败即放弃, 由 Python 侧 dispatch 前发送的
  ;; ESC 键兜底(file_ipc._type_dispatch_trigger)。
  (vl-catch-all-apply
    '(lambda ( / n)
       (setq n 0)
       (while (and (< n 4) (> (getvar "CMDACTIVE") 0))
         (command)
         (setq n (1+ n)))))
  (princ))

(defun t20mcp:cmd-known-p (name / r)
  ;; 命令存在性预检(咨询性质, 非权威): getcname 查命令表(含 ARX 注册命令),
  ;; 再查 c:XXX 形式的 LISP 命令。延迟加载的 ARX 模块可能漏报 —— 真机核实过
  ;; 的命令可用 t20mcp:call-nocheck 跳过预检。
  (setq r (vl-catch-all-apply 'getcname (list name)))
  (if (vl-catch-all-error-p r) (setq r nil))
  (or (and r (/= r ""))
      (not (null (member (strcase (strcat "C:" name)) (atoms-family 1))))))

(defun t20mcp:call-nocheck (name arglist / rc)
  ;; 用 vl-cmdf 而非 command: 先求值全部参数再开命令, 命令中途失败返回 nil,
  ;; 而不是把剩余参数继续当命令行输入执行。(command 的级联失控是本项目最危
  ;; 险的失败模式: 未知命令名后面跟着 "L" 会触发 LINE 画出垃圾实体, 同时
  ;; OK 标记照常打印 —— 假成功。) vl-cmdf 对未知命令的拦截效果待真机确证,
  ;; 因此 t20mcp:call 的预检是第一道防线, 这里的 cancel 清残留是第二道。
  (setq rc (vl-catch-all-apply 'vl-cmdf (cons name arglist)))
  (t20mcp:cancel-pending)
  (if (vl-catch-all-error-p rc) nil rc))

(defun t20mcp:call (name arglist)
  ;; -> T 成功 / nil 失败(未知命令或执行报错)。模板据此走 end 或 fail 分支。
  (if (t20mcp:cmd-known-p name)
      (t20mcp:call-nocheck name arglist)
      (progn
        (princ (strcat "\nT20MCP-WARN unknown-command: " name))
        nil)))

(defun t20mcp:begin (tag / s)
  ;; 标准开场: 记 tag -> 存环境 -> 静默 -> 开 UNDO 组(失败可整组回滚)。
  ;; 返回 saved 环境表; 模板必须存入局部变量并传给 *error*/end/fail。
  (setq t20mcp:*tag* tag)
  (setq s (t20mcp:env-save))
  (t20mcp:env-quiet)
  (vl-catch-all-apply 'vl-cmdf (list "_.UNDO" "_Begin"))
  s)

(defun t20mcp:end (tag saved)
  (vl-catch-all-apply 'vl-cmdf (list "_.UNDO" "_End"))
  (t20mcp:env-restore saved)
  (setq t20mcp:*tag* nil)
  (princ (strcat "\nT20MCP-OK " tag))
  (princ))

(defun t20mcp:fail (tag saved reason)
  (t20mcp:cancel-pending)
  (vl-catch-all-apply 'vl-cmdf (list "_.UNDO" "_End"))
  (t20mcp:env-restore saved)
  (setq t20mcp:*tag* nil)
  (princ (strcat "\nT20MCP-ERR " tag " | " reason))
  (princ))

(defun t20mcp:on-error (msg saved)
  ;; 兜底错误处理: 取消残留命令 -> 关 UNDO 组 -> 恢复环境 -> 打 ERR 标记。
  ;; 模板必须以「局部 *error*」接入(见骨架), 退出后旧 handler 自动恢复,
  ;; 不污染全局。AutoLISP 是动态作用域, handler 触发时可见模板的局部变量。
  (t20mcp:cancel-pending)
  (vl-catch-all-apply 'vl-cmdf (list "_.UNDO" "_End"))
  (t20mcp:env-restore saved)
  (princ (strcat "\nT20MCP-ERR "
                 (if t20mcp:*tag* t20mcp:*tag* "?")
                 " | "
                 (if msg msg "unknown")))
  (setq t20mcp:*tag* nil)
  (princ))

(defun t20mcp:pt (x y)
  ;; 坐标 -> "x,y" 命令行点字符串。env-quiet 已设 DIMZIN=8 抑制尾零;
  ;; 用 rtos 模式 2(十进制)定点 8 位, 不受 LUPREC 当前值影响。
  (strcat (rtos x 2 8) "," (rtos y 2 8)))

(defun t20mcp:geo1 (e / g ty out pr)
  ;; 实体 -> 简要几何串 "TYPE|x,y|x,y|40=r|s=text"。只消费常见组码
  ;; (10/11 点, 40/50/51 半径与弧角[弧度], 1 文本), 未知类型仅输出 TYPE。
  ;; 供 explode_read 读回分解产物; 角度保持 entget 原始弧度, 不换算。
  (setq g (entget e))
  (setq ty (cdr (assoc 0 g)))
  (setq out ty)
  (foreach pr g
    (cond
      ((and (member (car pr) '(10 11)) (listp (cdr pr)))
       (setq out (strcat out "|" (rtos (cadr pr) 2 8) "," (rtos (caddr pr) 2 8))))
      ((member (car pr) '(40 50 51))
       (setq out (strcat out "|" (itoa (car pr)) "=" (rtos (cdr pr) 2 8))))
      ((= (car pr) 1)
       (setq out (strcat out "|s=" (vl-princ-to-string (cdr pr)))))))
  out)

;;; ----------------------------------------------------------------------------
;;; 模板骨架 —— 所有 tangent 模板必须长这样(由 tangent.py 注入占位符):
;;;
;;;   (defun c:t20mcp-wall ( / t20mcp:saved *error*)
;;;     (setq t20mcp:saved (t20mcp:begin "wall"))
;;;     (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
;;;     {{SET_LAYER}}
;;;     (if (t20mcp:call "TGWall"
;;;                      (list "L" "{{LEFT_WIDTH}}" "R" "{{RIGHT_WIDTH}}"
;;;                            (t20mcp:pt {{X1}} {{Y1}}) (t20mcp:pt {{X2}} {{Y2}}) ""))
;;;         (t20mcp:end "wall" t20mcp:saved)
;;;         (t20mcp:fail "wall" t20mcp:saved "command-failed-or-unknown"))
;;;     (princ))
;;;   (c:t20mcp-wall)
;;;
;;; 禁止: 在模板里手写 setq/setvar 保存恢复(本 prelude 之外的状态管理一律删);
;;;       使用 ;| ... |; 块注释(is_paren_balanced 不识别)。
;;; ----------------------------------------------------------------------------
(princ "\nT20MCP-PRELUDE loaded")
(princ)
