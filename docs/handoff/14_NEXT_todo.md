# Handoff 14 — 下一步待办（claude，2026-06-13）

本轮已提交（分支 `codex/tgcolumn-three-commands`，未 push）：
- `1e538d3` `[assist]` column 工作 + fable→claude 角色接管
- `cada772` `[claude]` column 降级 dry-run（#32770 假成功纠错，Handoff 13）
- `db6bcba` `[claude]` two_point_dimension (TDimTP) 新封装，真机 E2E 通过

真机已清干净；临时探针收尾见下方补记。

## 待办（按优先级）

1. **push / 开 PR**：3 个 commit 还在本地分支，未 push。

2. ~~**TSWall 单线变墙**~~（2026-06-13 已复核，见 Handoff 15）：
   选择成功但不转换；未观察到弹框；额外宽度输入被当未知命令。两轮仍 0 实体，
   按规则停手，暂不封装。

3. ~~**临时探针收尾**~~（2026-06-13 已完成）：
   - `scripts/_probe_log.py` 已转正为 `scripts/itest_32_prompt_capture_log.py`
     （LOGFILEMODE 提示捕获法，长期有用，本轮破译 TDimTP 全靠它）。
   - 其余 `scripts/_probe_*.py`（cmd/cmdline/fixshot/harness/launch/recover/state/tdimtp）已删除。

4. **column UI 自动化**（可选，高风险）：让标准柱真能放置，需驱动 #32770 面板
   + 模拟绘图区坐标点击（比白名单 BM_CLICK 难）。详见 Handoff 13 §4。

## 派 codex 注意（memory 已记）
- codex 会自设 `UV_PROJECT_ENVIRONMENT` 把 `.venv` 搞坏 → 修复 `rm -rf .venv && uv sync`；
  预防：让 codex 只改文件，**测试和 commit 由 claude 在主环境做**。
- codex 沙箱 `.git` 只读，不能 commit。
