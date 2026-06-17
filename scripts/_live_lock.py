"""真机脚本互斥锁 — Windows 上 AutoCAD/T20 是单命令通道, 真机 itest 并行会污染。

设计:
- 锁文件: %TEMP%\\t20_mcp_live.lock (固定路径, 跨脚本共享)
- 抢锁: O_CREAT|O_EXCL|O_WRONLY 原子创建; 失败则视为有人持锁。
- 持锁内容: pid\\n<script_name>\\n<acquired_at_iso>\\n  (用于诊断)
- stale 清理: 持锁文件里 pid 不存在 (Windows tasklist 找不到), 视为死锁, 删除 + 重试一次。
- 释放: 仅当文件内 pid 等于自己 pid 才 unlink (防止误删别人的锁)。
- 抢不到锁直接退出, 不阻塞等待 — 真机脚本运行时长不可预期, 阻塞会更糟。

使用 (脚本顶层):
    from _live_lock import live_lock_or_exit
    _lock = live_lock_or_exit(__file__)   # 抢不到就 sys.exit(2) + 提示
    # 必须把返回值存到变量持有引用; 否则临时对象语句结束即析构, 立即释放锁。

或显式 with:
    from _live_lock import live_lock
    with live_lock(__file__):
        ...

不要把这个模块塞进 src/t20_mcp/ — 必须脱离 t20_mcp 包独立运行,
因为某些脚本 (例如 itest_19_mcp_stdio_smoke.py) 不把 src/ 加入 sys.path。
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator

LOCK_PATH = Path(tempfile.gettempdir()) / "t20_mcp_live.lock"


def _pid_alive(pid: int) -> bool:
    """Windows-only: 用 tasklist 探测 pid 是否仍存在 (不依赖 psutil).
    用 raw bytes 避免中文 Windows 上 tasklist 输出非 UTF-8 触发 decode error。"""
    if pid <= 0:
        return False
    try:
        import subprocess

        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True, timeout=5, check=False,
        )
        # 进程在: stdout 含 b',"<pid>",'; 不在: 含 b"INFO: No tasks"
        needle = f',"{pid}",'.encode("ascii")
        return needle in (out.stdout or b"")
    except Exception:
        # 任何错误都保守地当作 alive, 避免误删别人的锁
        return True


def _read_holder() -> tuple[int, str, str] | None:
    try:
        raw = LOCK_PATH.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, OSError):
        return None
    parts = raw.split("\n", 2)
    if len(parts) < 1:
        return None
    try:
        pid = int(parts[0].strip())
    except ValueError:
        return None
    name = parts[1].strip() if len(parts) > 1 else "?"
    started = parts[2].strip() if len(parts) > 2 else "?"
    return pid, name, started


def _try_create_locked(content: str) -> bool:
    """O_EXCL 原子创建; True = 抢到, False = 已存在."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(LOCK_PATH, flags, 0o644)
    except FileExistsError:
        return False
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    return True


@contextlib.contextmanager
def live_lock(script_path: str | os.PathLike[str]) -> Iterator[Path]:
    """真机脚本互斥锁 context manager. 抢不到锁直接 raise RuntimeError."""
    name = Path(script_path).name
    my_pid = os.getpid()
    started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    payload = f"{my_pid}\n{name}\n{started}\n"

    if not _try_create_locked(payload):
        # 已被别人持有 — 看是不是 stale
        holder = _read_holder()
        if holder is not None:
            holder_pid, holder_name, holder_started = holder
            if not _pid_alive(holder_pid):
                # stale: 旧脚本进程不在了, 清理并重试一次
                try:
                    LOCK_PATH.unlink()
                except OSError:
                    pass
                if not _try_create_locked(payload):
                    raise RuntimeError(
                        f"t20_mcp live lock contended even after stale cleanup: "
                        f"someone else just acquired it"
                    )
            else:
                raise RuntimeError(
                    f"t20_mcp live lock held by pid={holder_pid} "
                    f"script={holder_name!r} since {holder_started}; "
                    f"refuse to run {name!r} concurrently. "
                    f"If you are sure no other live test is running, "
                    f"delete {LOCK_PATH} and retry."
                )
        else:
            raise RuntimeError(
                f"t20_mcp live lock at {LOCK_PATH} exists but is unreadable; "
                f"refuse to run. Inspect or delete it manually."
            )

    try:
        yield LOCK_PATH
    finally:
        # 仅当 lock 仍是我们的才 unlink
        holder = _read_holder()
        if holder is not None and holder[0] == my_pid:
            try:
                LOCK_PATH.unlink()
            except OSError:
                pass


def live_lock_or_exit(script_path: str | os.PathLike[str]) -> "_LockHandle":
    """脚本入口便捷函数: 抢不到就 sys.exit(2) + 提示, 抢到了返回一个对象,
    保持引用直到脚本结束 (析构时释放)."""
    name = Path(script_path).name
    try:
        cm = live_lock(script_path)
        path = cm.__enter__()
    except RuntimeError as e:
        print(f"[live_lock] {e}", file=sys.stderr)
        sys.exit(2)
    return _LockHandle(cm)


class _LockHandle:
    def __init__(self, cm):
        self._cm = cm

    def release(self) -> None:
        if self._cm is not None:
            try:
                self._cm.__exit__(None, None, None)
            finally:
                self._cm = None

    def __del__(self):
        self.release()


__all__ = ["LOCK_PATH", "live_lock", "live_lock_or_exit"]
