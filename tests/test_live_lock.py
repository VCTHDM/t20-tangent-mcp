"""离线单测: scripts/_live_lock.py 真机互斥锁.

不依赖 AutoCAD/T20。每个测试独立 tmp_path 隔离锁文件位置, 避免污染
生产 %TEMP%/t20_mcp_live.lock。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 把仓库的 scripts/ 加到 sys.path 以便 import _live_lock
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import _live_lock  # noqa: E402


@pytest.fixture
def tmp_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 _live_lock.LOCK_PATH 重定向到 tmp_path, 隔离测试。"""
    p = tmp_path / "t20_mcp_live.lock"
    monkeypatch.setattr(_live_lock, "LOCK_PATH", p)
    return p


def test_acquire_creates_file_with_pid(tmp_lock: Path) -> None:
    assert not tmp_lock.exists()
    with _live_lock.live_lock(__file__) as held:
        assert held == tmp_lock
        assert tmp_lock.exists()
        contents = tmp_lock.read_text(encoding="utf-8")
        # 第一行必须是当前进程 pid
        assert contents.splitlines()[0].strip() == str(os.getpid())
        assert "test_live_lock.py" in contents
    # 退出后文件被清理
    assert not tmp_lock.exists()


def test_contention_against_live_pid_raises(tmp_lock: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 模拟另一个活进程持有锁
    monkeypatch.setattr(_live_lock, "_pid_alive", lambda pid: True)
    tmp_lock.write_text("99999\nfake_holder.py\n2026-06-17T00:00:00+00:00\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        with _live_lock.live_lock(__file__):
            pass  # pragma: no cover  (should never enter)
    msg = str(exc.value)
    assert "pid=99999" in msg
    assert "fake_holder.py" in msg
    # 锁仍归原持有者, 没被误删
    assert tmp_lock.exists()


def test_stale_lock_is_reclaimed(tmp_lock: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 模拟旧持有者 PID 已经死了
    monkeypatch.setattr(_live_lock, "_pid_alive", lambda pid: False)
    tmp_lock.write_text("88888\ndead_holder.py\n2026-01-01T00:00:00+00:00\n", encoding="utf-8")
    with _live_lock.live_lock(__file__):
        # 应该已经清掉旧锁并写入自己
        contents = tmp_lock.read_text(encoding="utf-8")
        assert contents.splitlines()[0].strip() == str(os.getpid())
    assert not tmp_lock.exists()


def test_release_does_not_remove_other_holders_lock(
    tmp_lock: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """如果释放时锁文件已被别人改写 (例如 PID 不再匹配), 不能误删。"""
    monkeypatch.setattr(_live_lock, "_pid_alive", lambda pid: False)  # 允许 acquire
    cm = _live_lock.live_lock(__file__)
    cm.__enter__()
    # 模拟有人覆盖锁文件 (理论上不应发生, 但防御性)
    tmp_lock.write_text("77777\nother.py\n2026-06-17T00:00:00+00:00\n", encoding="utf-8")
    cm.__exit__(None, None, None)
    # 锁文件还在, 内容是别人的
    assert tmp_lock.exists()
    assert tmp_lock.read_text(encoding="utf-8").splitlines()[0].strip() == "77777"
    # cleanup
    tmp_lock.unlink()


def test_unreadable_lock_raises(tmp_lock: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁文件存在但格式坏掉 (无 PID 整数), 应当 raise 而不是误闯入。"""
    tmp_lock.write_text("not-a-pid\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        with _live_lock.live_lock(__file__):
            pass  # pragma: no cover
    # 走的是 holder is None 分支 (parse 失败) 或 alive 分支
    assert "live lock" in str(exc.value)


def test_live_lock_or_exit_returns_handle(tmp_lock: Path) -> None:
    """live_lock_or_exit 抢到时应返回一个对象, release() 后锁释放。"""
    handle = _live_lock.live_lock_or_exit(__file__)
    try:
        assert tmp_lock.exists()
    finally:
        handle.release()
    assert not tmp_lock.exists()


def test_live_lock_or_exit_exits_on_contention(
    tmp_lock: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """抢不到锁时 sys.exit(2) 并打印提示。"""
    monkeypatch.setattr(_live_lock, "_pid_alive", lambda pid: True)
    tmp_lock.write_text("99999\nholder.py\n2026-06-17T00:00:00+00:00\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _live_lock.live_lock_or_exit(__file__)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "pid=99999" in err
    assert "holder.py" in err


def test_pid_alive_with_invalid_pid_returns_false() -> None:
    assert _live_lock._pid_alive(0) is False
    assert _live_lock._pid_alive(-1) is False


def test_pid_alive_with_self_returns_true() -> None:
    """自己的 PID 一定 alive (走真实 tasklist 路径; 如果 tasklist 异常会回 True 兜底)."""
    assert _live_lock._pid_alive(os.getpid()) is True
