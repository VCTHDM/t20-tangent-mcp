# Handoff 18 — TParallelDim / TArrow 初探停手记录

> **补注 (2026-06-16)**: TArrow 已在 Handoff 22 成功封装为 arrow 子命令
> (E2E: 起点→终点→回车→回车 → TCH_ARROW)。本文件仅作历史审计保留。

执行者：Codex ｜ 日期：2026-06-13 ｜ 环境：T20 V10 + AutoCAD 2024（Drawing1.dwg）

## 结论

本轮在成功封装 `coordinate` 后继续挑标注类稳定目标。`TParallelDim` 和 `TArrow`
都没有弹框，但都未达到“可安全封装”的完成条件，先放一边：

- `TParallelDim`：提示流清晰，但三墙穿越线场景未生成实体，语义不像 `TDimTP`。
- `TArrow`：两点加回车可生成 `TCH_ARROW`，但命令仍保持 active；退出/完成语义未确认。

## TParallelDim 探测

1. 首个提示：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TPARALLELDIM empty none
```

```text
TPARALLELDIM
请选择起点或 [设置图层过滤 (S)]<退出>:
```

2. 单点提示：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TPARALLELDIM '(list (t20mcp:pt 0 0))' none
```

```text
请选择起点或 [设置图层过滤 (S)]<退出>: 0,0
选择终点<退出>:
```

3. 两点无场景：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TPARALLELDIM '(list (t20mcp:pt 0 0) (t20mcp:pt 6000 0))' none
```

```text
请选择起点或 [设置图层过滤 (S)]<退出>: 0,0
选择终点<退出>: 6000,0
选中的与第一个对象平行的对象太少, 不能进行平行标注!
```

4. 三道竖墙场景临时探针：
   - 新建三道墙后执行 `TPARALLELDIM (-1000,0)->(7000,0)`。
   - 返回 `active=0 type=none`，实体数未增加。

暂不封装；下一轮若继续，应先查明“第一个对象”选择语义，而不是复用 `TDimTP` 穿越线。

## TArrow 探测

1. 首个提示：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TARROW empty none
```

```text
TARROW
箭头起点或 [点取图中曲线(P)/点取参考点(R)]<退出>:
```

2. 单点提示：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TARROW '(list (t20mcp:pt 0 0))' none
```

```text
箭头起点或 [点取图中曲线(P)/点取参考点(R)]<退出>: 0,0
直段下一点或 [弧段(A)/回退(U)]<结束>:
```

3. 两点提示：

```powershell
uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TARROW '(list (t20mcp:pt 0 0) (t20mcp:pt 1000 0))' none
```

```text
直段下一点或 [弧段(A)/回退(U)]<结束>:1000,0
直段下一点或 [弧段(A)/回退(U)]<结束>:
```

4. 临时实体读回探针：
   - `TARROW` + 起点 + 下一点 + 回车生成 `TCH_ARROW`。
   - 但返回 `active=1 type=TCH_ARROW`，说明命令仍未退出。
   - 清理：`itest_14_cleanup.py` 将 `CMDACTIVE` 恢复为 0；随后受控 `UNDO` 一次，
     实体数 `22 -> 21`，环境为 `CMDACTIVE=0, CMDDIA=1, FILEDIA=1, OSMODE=0`。

暂不封装；下一轮若继续，先确认是否需要双回车、ESC 后实体是否保留、或是否应通过
`t20mcp:call` 的收尾分支显式取消命令。确认前不要把 `TArrow` 加到可 execute 子命令。
