"""离线单测：真机脚本的操作系统互斥锁。"""

from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import _live_lock  # noqa: E402


class _RecordingStream:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def reconfigure(self, **kwargs: str) -> None:
        self.calls.append(kwargs)


class _RejectingStream:
    def reconfigure(self, **kwargs: str) -> None:
        raise OSError(f"unsupported stream configuration: {kwargs}")


def _hold_lock_in_child(lock_path: str, ready, release) -> None:
    _live_lock.LOCK_PATH = Path(lock_path)
    with _live_lock.live_lock("child_holder.py"):
        ready.set()
        release.wait(timeout=10)


@pytest.fixture
def tmp_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "t20_mcp_live.lock"
    monkeypatch.setattr(_live_lock, "LOCK_PATH", path)
    return path


def test_utf8_output_configures_both_streams() -> None:
    stdout = _RecordingStream()
    stderr = _RecordingStream()

    _live_lock._configure_utf8_output(stdout, stderr)

    expected = [{"encoding": "utf-8", "errors": "replace"}]
    assert stdout.calls == expected
    assert stderr.calls == expected


def test_utf8_output_accepts_streams_without_reconfigure() -> None:
    _live_lock._configure_utf8_output(object(), None)


def test_utf8_output_ignores_reconfigure_errors_and_continues() -> None:
    stderr = _RecordingStream()

    _live_lock._configure_utf8_output(_RejectingStream(), stderr)

    assert stderr.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_acquire_writes_diagnostics_and_releases_os_lock(tmp_lock: Path) -> None:
    with _live_lock.live_lock(__file__) as held:
        assert held == tmp_lock
        contents = tmp_lock.read_text(encoding="utf-8")
        assert contents.splitlines()[0] == str(os.getpid())
        assert "test_live_lock.py" in contents

    # 诊断文件保留，但退出 context 后同一进程可立即重新获取操作系统锁。
    assert tmp_lock.exists()
    with _live_lock.live_lock("second_probe.py"):
        assert "second_probe.py" in tmp_lock.read_text(encoding="utf-8")


def test_unlocked_stale_diagnostics_are_overwritten(tmp_lock: Path) -> None:
    tmp_lock.write_text(
        "88888\ndead_holder.py\n2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    with _live_lock.live_lock(__file__):
        contents = tmp_lock.read_text(encoding="utf-8")
        assert contents.splitlines()[0] == str(os.getpid())
        assert "dead_holder.py" not in contents


def test_malformed_unlocked_file_does_not_block(tmp_lock: Path) -> None:
    tmp_lock.write_text("not-a-pid\n", encoding="utf-8")
    with _live_lock.live_lock(__file__):
        assert tmp_lock.read_text(encoding="utf-8").splitlines()[0] == str(os.getpid())


def test_nested_acquire_reports_current_holder(tmp_lock: Path) -> None:
    with _live_lock.live_lock("holder.py"):
        with pytest.raises(RuntimeError) as exc:
            with _live_lock.live_lock("contender.py"):
                pytest.fail("contender unexpectedly acquired the live lock")
    message = str(exc.value)
    assert f"pid={os.getpid()}" in message
    assert "holder.py" in message


def test_live_lock_or_exit_returns_releasable_handle(tmp_lock: Path) -> None:
    handle = _live_lock.live_lock_or_exit(__file__)
    handle.release()
    with _live_lock.live_lock("after_release.py"):
        pass


def test_live_lock_or_exit_exits_on_contention(
    tmp_lock: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _live_lock.live_lock("holder.py"):
        with pytest.raises(SystemExit) as exc:
            _live_lock.live_lock_or_exit("contender.py")
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "holder.py" in error
    assert "pid=" in error


def test_cross_process_contention_and_release(tmp_lock: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    child = context.Process(
        target=_hold_lock_in_child,
        args=(str(tmp_lock), ready, release),
    )
    child.start()
    try:
        assert ready.wait(timeout=10), "child did not acquire the lock"
        with pytest.raises(RuntimeError, match="child_holder.py"):
            with _live_lock.live_lock("parent_contender.py"):
                pytest.fail("parent unexpectedly acquired the child lock")
    finally:
        release.set()
        child.join(timeout=10)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)

    assert child.exitcode == 0
    with _live_lock.live_lock("parent_after_release.py"):
        pass
