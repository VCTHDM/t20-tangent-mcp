# Handoff 15 — TSWall 单线变墙复核：无弹框，命令行序列 no-op

执行者：codex ｜ 日期：2026-06-13 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

`TSWall` 本轮按安全管线复核后仍不可封装：它能识别 LINE 选择集（日志显示“找到 1 个”），
但回车结束选择后直接返回命令行，不生成 `TCH_WALL`，也未观察到 `#32770` 或其他新弹框。
额外输入 `240` 会在命令结束后被 AutoCAD 当成未知命令，不是墙宽参数。

因此当前结论从“疑似选择后弹框”修正为：**未发现弹框；命令行选择集路径 no-op，暂不封装。**
按 README 规则，两轮仍 0 实体，停止继续硬猜。

## 执行记录

1. `uv run python -X utf8 scripts/itest_01_bringup.py`
   - PASS：窗口识别、dispatcher ping、中文编码往返均通过。

2. `uv run python -X utf8 scripts/itest_33_tswall_dialog_recon.py`
   - 建一条 LINE：`entities 0->1`
   - 未观察到新弹框：`[dialog] none observed`
   - LISP 返回：`payload='active=0 newtype=none'`
   - 清理成功：`entities=0 env={'CMDACTIVE': 0, 'CMDDIA': 1, 'FILEDIA': 1, 'OSMODE': 0}`

3. `uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TSWALL tswall_ss line`
   - 日志关键段：

```text
TSWALL
选择要变成墙体的直线、圆弧或多段线:  找到 1 个
选择要变成墙体的直线、圆弧或多段线:
命令:
@@@AFTER active=0@@@
```

4. `uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TSWALL tswall_ss_w line`
   - 日志关键段：

```text
TSWALL
选择要变成墙体的直线、圆弧或多段线:  找到 1 个
选择要变成墙体的直线、圆弧或多段线:
命令: 240 未知命令“240”。按 F1 查看帮助。
@@@AFTER active=0@@@
```

## 后续建议

- 不把 `TSWall` 做成 `tangent` 子命令，除非拿到新的官方交互线索或人工操作证明。
- 若未来继续查，优先找菜单宏/ARX 内部调用或替代命令，不再重复 LINE 选择集 + 回车/宽度输入路线。
- `itest_32_prompt_capture_log.py` 和 `itest_33_tswall_dialog_recon.py` 可保留作为后续提示捕获/弹框侦察管线。
