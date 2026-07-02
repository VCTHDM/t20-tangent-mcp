# Handoff 37 — A1 裁定: TRectAxis Gate B 机制打通, 但不封装 (WON'T-SHIP)

> 日期: 2026-07-02 · 环境: T20 V10 / AutoCAD 2024 (真机)
> 探针: scripts/itest_41_rectaxis_gate_b.py · 原始证据: docs/handoff/37_rectaxis_gate_b_raw.txt
> 控件映射: docs/handoff/37_trectaxis_control_map.md (opencode 整理, claude 复核)

## 0. 一句话结论

**Gate B 控件级机制全部打通且确定性可复现, 但 A1 不落地 rect_axis 子命令。**
原因不是机制失败, 而是**价值裁定**: TRectAxis 在本配置产出的是纯 LINE @ 图层
DOTE (无 xdata / 无 TCH_AXIS / 无轴号), 与既有 `axis_lines` (entmake 纯 LINE)
同类。驱动对话框相较 axis_lines **零实体增益**, 反添 GUI 会话依赖与脆弱性。

## 1. 机制侧成果 (全部真机验证, 复用 Handoff 36 范式)

1. **面板发现**: 无标题 #32770 + SysTabControl32 + Static '总开间:' 指纹。
2. **bind (H1)**: 选方向 radio (上开/下开/左进/右进) + 宽 Edit 键入间距串 +
   Enter → 总开间/总进深 Static 联动更新, 不落图即自校验。真机稳定 PASS。
3. **间距语法 = `个数*轴间距` (COUNT*SPACING)**: `"3*3000"` = 3 跨×3000 →
   总开间 9000, 4 根竖轴。**这是本轮最大的坑**: 误用 `"3000*2"` 被读成
   3000 跨×2mm = 3000 根轴线, 一度产出 3003 实体的假象 (排查见 §3)。
4. **commit (H2)**: owner-draw 确定/取消按钮对 BM_CLICK / 鼠标消息 / 父窗
   WM_COMMAND(ctrlid) **全部无效**; 唯 **`WM_COMMAND(dialog, IDOK=1)`** 生效 →
   关框且 CMDACTIVE=1 (命令等插入点) → 命令行 WM_CHAR 打坐标 → 确定性落图。
   点击法甄别表 (diag):

   | 方法 | dialog_gone | CMDACTIVE 后 |
   |---|---|---|
   | WM_COMMAND(IDOK) | ✅ True | 1 (等插入点, 可继续打点) |
   | 回车默认键 | True | 0 (命令直接结束, 不等点) |
   | BM_CLICK / 鼠标 / 父窗通知 | ❌ False | — |

5. **确定性**: 清洁序列 (单值 + IDOK + 即打点, 中途不走 IPC) 连测多轮,
   `3*3000`+`2*4500` 稳定产 7 根 LINE, `3000`+`4500` 稳定产 4 根。

## 2. 决定性负结果 (为何不封装)

真机 entget (含 xdata) 一根轴线:
```
(0 . "LINE") (8 . "DOTE") (100 . "AcDbLine")
(10 39000 44500 0) (11 50000 44500 0) (210 0 0 1)
;; 无 (-3 ...) xdata, 无 TCH_*, 无 100/AcDbZombie
```

| 维度 | TRectAxis (对话框) | 既有 axis_lines (entmake) |
|---|---|---|
| 实体类型 | 纯 LINE | 纯 LINE |
| 图层 | DOTE (可由参数指定) | 由 layer 参数指定 (可传 DOTE) |
| xdata / TCH 智能对象 | **无** | 无 |
| 轴号 / 尺寸链 | **无** (本配置命令只产轴线) | 无 |
| 会话依赖 | 需 GUI + 对话框自动化 | 纯 LISP, 无 UI |
| 语法坑 | COUNT*SPACING 易错 | 直接给间距数组 |

A1 原始闭合判据是"生成 TCH_AXIS 系 (而非 axis_lines 普通 LINE 替代)"。
真机证实该前提**不成立**: TRectAxis 本配置不产 TCH_AXIS, 产物 ⊆ axis_lines
能力集。故封装 rect_axis 只会得到一个"更慢、更脆、需 GUI"的 axis_lines,
是净负收益。**裁定: A1 WON'T-SHIP。** 需要 DOTE 图层轴网的用户,
直接 `axis_lines` + `layer="DOTE"` 即可得到等价结果。

## 3. 排查笔记: 3003 实体假象

首轮用 `"3000*2"` (以为是"3000 重复 2 次") commit, 得 3003 LINE, 且时而 0
(非确定性), 一度疑似机制崩坏。逐步证伪:
- 段长直方图: 3003 根全为满长 LINE, 无短划线 → 非点划线拆段。
- 去重: total=3003 unique=3003 → 几何全唯一, 非重复叠画。
- ListBox 内容: 四方向都是 [1200..6900] → 是**预设值调色板**, 非累积状态。
- 改单值 `"3000"` → 确定性 4 根; 改 `"3*3000"` → 确定性 7 根。
=> 结论: 语法是 COUNT*SPACING, `"3000*2"` = 3000 跨×2mm。机制一直正确,
   错在输入。这条经验并入探针 docstring 与本文档, 避免重蹈。

## 4. 落地清单

- scripts/itest_41_rectaxis_gate_b.py — Gate B 证据脚本 (bind / commit / diag),
  定稿用正确 COUNT*SPACING 语法, verdict 直接给出 WON'T-SHIP 裁定。
- **不改 tangent.py** — 不新增 rect_axis; axis_lines 保持不变 (已支持任意图层)。
- docs/handoff/37_trectaxis_control_map.md (opencode) + 37_rectaxis_gate_b_raw.txt。

## 5. 对 backlog 的影响

- A1: **STOPPED (价值裁定, 非机制失败)** — Gate B 机制已证可行且沉淀为可复用
  范式; 但目标命令产物无增益, 不封装。若未来发现 T20 有产 TCH_AXIS 的轴网
  命令 (或本命令有产轴号的开关), 可复用本探针机制重启。
- 机制资产: WM_COMMAND(IDOK) 关框 + 打点 这一"自持对话框 + 命令续等点"范式,
  与 Handoff 36 的"浮动面板 + 即时生效"互补, 共同覆盖天正两类对话框驱动。
- 方法论沉淀: **封装前先验证目标命令的产物实体类型是否优于既有替代路径**;
  机制可行 ≠ 值得封装。

## 6. 复跑命令

```bash
uv run python scripts/itest_41_rectaxis_gate_b.py bind     # H1 联动 (不落图)
uv run python scripts/itest_41_rectaxis_gate_b.py commit   # H2 落图 + 类型裁定
uv run python scripts/itest_41_rectaxis_gate_b.py diag     # owner-draw 点击法甄别
```
