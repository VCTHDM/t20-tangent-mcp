# Handoff 14 — 下一步待办（claude，2026-06-13）

本轮已提交（分支 `codex/tgcolumn-three-commands`，未 push）：
- `1e538d3` `[assist]` column 工作 + fable→claude 角色接管
- `cada772` `[claude]` column 降级 dry-run（#32770 假成功纠错，Handoff 13）
- `db6bcba` `[claude]` two_point_dimension (TDimTP) 新封装，真机 E2E 通过

真机已清干净；工作树仅余未跟踪的临时探针 `scripts/_probe_*.py`。

## 待办（按优先级）

1. **push / 开 PR**：3 个 commit 还在本地分支，未 push。

2. **TSWall 单线变墙**（Handoff 12 §4，疑难，claude territory）：
   选择成功但未转换，疑似选择后弹模态框。先 recon 定性（仿
   `itest_28_rectaxis_recon.py` 枚举 `#32770`，**严禁 WM_CLOSE**），
   再决定封装或记录停手。用 `_probe_log.py run TSWALL tswall_ss line` 看完整日志。

3. **临时探针收尾**：
   - `scripts/_probe_log.py` 转正为 `scripts/itest_*_prompt_capture_log.py`
     （LOGFILEMODE 提示捕获法，长期有用，本轮破译 TDimTP 全靠它）。
   - 其余 `scripts/_probe_*.py`（cmd/cmdline/fixshot/harness/launch/recover/state/tdimtp）删除。

4. **column UI 自动化**（可选，高风险）：让标准柱真能放置，需驱动 #32770 面板
   + 模拟绘图区坐标点击（比白名单 BM_CLICK 难）。详见 Handoff 13 §4。

## 派 codex 注意（memory 已记）
- codex 会自设 `UV_PROJECT_ENVIRONMENT` 把 `.venv` 搞坏 → 修复 `rm -rf .venv && uv sync`；
  预防：让 codex 只改文件，**测试和 commit 由 claude 在主环境做**。
- codex 沙箱 `.git` 只读，不能 commit。
