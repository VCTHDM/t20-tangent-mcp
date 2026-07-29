"""真机脚本互斥锁。

AutoCAD/T20 只有一条命令通道，真机 itest 并行运行会相互污染。本模块使用
操作系统的非阻塞独占文件锁；锁随文件句柄或进程退出自动释放，不再依赖
“读取 PID → 删除 stale 文件”的竞态协议。

诊断文件固定为 ``%TEMP%/t20_mcp_live.lock``，旁路 ``.guard`` 文件只承载
操作系统锁。两者都会保留；是否持锁以操作系统锁为准。

使用：

    from _live_lock import live_lock_or_exit

    _lock = live_lock_or_exit(__file__)

也可以显式使用 context manager：

    from _live_lock import live_lock

    with live_lock(__file__):
        ...
"""

from __future__ import annotations

import contextlib
import datetime as dt
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

LOCK_PATH = Path(tempfile.gettempdir()) / "t20_mcp_live.lock"


def _guard_path() -> Path:
    return LOCK_PATH.with_name(f"{LOCK_PATH.name}.guard")


def _read_holder() -> tuple[int, str, str] | None:
    """Read best-effort diagnostics from the lock file."""
    try:
        raw = LOCK_PATH.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, OSError):
        return None
    parts = raw.split("\n", 2)
    try:
        pid = int(parts[0].strip())
    except (IndexError, ValueError):
        return None
    name = parts[1].strip() if len(parts) > 1 else "?"
    started = parts[2].strip() if len(parts) > 2 else "?"
    return pid, name, started


def _try_lock(stream: BinaryIO) -> bool:
    """Acquire a one-byte non-blocking exclusive lock."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    import fcntl

    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(stream: BinaryIO) -> None:
    """Release the platform file lock."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write_holder(script_path: str | os.PathLike[str]) -> None:
    payload = (
        f"{os.getpid()}\n"
        f"{Path(script_path).name}\n"
        f"{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}\n"
    )
    LOCK_PATH.write_text(payload, encoding="utf-8", newline="\n")


@contextlib.contextmanager
def live_lock(script_path: str | os.PathLike[str]) -> Iterator[Path]:
    """Acquire the shared live-test lock or raise ``RuntimeError`` immediately."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    stream = _guard_path().open("a+b", buffering=0)
    try:
        # Windows byte-range locking requires the byte to exist before locking.
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()

        if not _try_lock(stream):
            holder = _read_holder()
            if holder is None:
                detail = f"at {LOCK_PATH}; holder diagnostics unavailable"
            else:
                pid, name, started = holder
                detail = f"held by pid={pid} script={name!r} since {started}"
            raise RuntimeError(f"t20_mcp live lock {detail}")

        _write_holder(script_path)
        try:
            yield LOCK_PATH
        finally:
            _unlock(stream)
    finally:
        stream.close()


def live_lock_or_exit(script_path: str | os.PathLike[str]) -> _LockHandle:
    """Acquire the lock; on contention print a diagnostic and exit with code 2."""
    try:
        manager = live_lock(script_path)
        manager.__enter__()
    except RuntimeError as exc:
        print(f"[live_lock] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return _LockHandle(manager)


class _LockHandle:
    def __init__(self, manager: contextlib.AbstractContextManager[Path]) -> None:
        self._manager: contextlib.AbstractContextManager[Path] | None = manager

    def release(self) -> None:
        if self._manager is not None:
            try:
                self._manager.__exit__(None, None, None)
            finally:
                self._manager = None

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            # Interpreter shutdown can tear down I/O modules before __del__.
            pass


__all__ = ["LOCK_PATH", "live_lock", "live_lock_or_exit"]
