"""Backend detection and environment configuration."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

# Paths. Hatch maps the repository-level dispatcher into ``t20_mcp/lisp_code``
# in built wheels; editable/source runs keep using the single root source file.
PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGED_LISP_DIR = PACKAGE_DIR / "lisp_code"
SOURCE_LISP_DIR = PACKAGE_DIR.parent.parent / "lisp-code"
LISP_DIR = (
    PACKAGED_LISP_DIR if (PACKAGED_LISP_DIR / "mcp_dispatch.lsp").is_file() else SOURCE_LISP_DIR
)
# IPC 目录默认放在 %TEMP%/t20_mcp (避免要求 C:\ 根写权限); 可用 env 覆盖。
# dispatcher (lisp-code/mcp_dispatch.lsp) 用同样规则解析, 两端必须一致。
IPC_DIR = Path(
    os.environ.get(
        "AUTOCAD_MCP_IPC_DIR",
        str(Path(os.environ.get("TEMP") or os.environ.get("TMP") or "C:/temp") / "t20_mcp"),
    )
)

# 主窗识别: 进程映像名为主判据 (天正启动器可能改标题, 标题判据不可靠)。
ACAD_PROCESS_NAME = os.environ.get("AUTOCAD_MCP_ACAD_PROCESS", "acad.exe").strip().lower()

# Backend selection
BACKEND_DEFAULT = "auto"  # auto | file_ipc | ezdxf
BACKEND_CHOICES = frozenset({"auto", "file_ipc", "ezdxf"})
IPC_TIMEOUT_MIN = 1.0
IPC_TIMEOUT_MAX = 300.0


def _parse_ipc_timeout(raw: str) -> float:
    """Parse and clamp the IPC timeout with an actionable config error."""
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            "AUTOCAD_MCP_IPC_TIMEOUT must be a finite number between 1 and 300 seconds"
        ) from exc
    if not math.isfinite(value):
        raise RuntimeError(
            "AUTOCAD_MCP_IPC_TIMEOUT must be a finite number between 1 and 300 seconds"
        )
    return max(IPC_TIMEOUT_MIN, min(IPC_TIMEOUT_MAX, value))


# IPC timeout (seconds), clamped to [1, 300]
IPC_TIMEOUT = _parse_ipc_timeout(os.environ.get("AUTOCAD_MCP_IPC_TIMEOUT", "10.0"))

# Screenshot
ONLY_TEXT_FEEDBACK = os.environ.get("AUTOCAD_MCP_ONLY_TEXT", "").lower() in ("1", "true", "yes")

# Win32 availability
WIN32_AVAILABLE = sys.platform == "win32"


def _current_backend_env() -> str:
    """Read backend selection from env with normalization."""
    return os.environ.get("AUTOCAD_MCP_BACKEND", BACKEND_DEFAULT).strip().lower()


def _is_wsl() -> bool:
    """Detect WSL Linux runtime."""
    if os.environ.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in os.uname().release.lower()
    except AttributeError:
        return False


def _write_debug_snapshot(backend_env: str) -> None:
    """Optionally write backend detection debug information.

    Set AUTOCAD_MCP_DEBUG_DETECT_FILE to enable.
    """
    debug_file = os.environ.get("AUTOCAD_MCP_DEBUG_DETECT_FILE", "").strip()
    if not debug_file:
        return

    try:
        debug_path = Path(debug_file)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with debug_path.open("w", encoding="utf-8") as f:
            f.write(f"sys.platform={sys.platform}\n")
            f.write(f"WIN32_AVAILABLE={WIN32_AVAILABLE}\n")
            f.write(f"BACKEND_ENV={backend_env}\n")
            f.write(f"python={sys.executable}\n")
    except Exception:
        # Best-effort only; never fail backend detection due debug writes.
        pass


def detect_backend() -> str:
    """Return the backend name to use: 'file_ipc' or 'ezdxf'.

    Raises RuntimeError with actionable message if explicit backend fails.
    """
    backend_env = _current_backend_env()
    _write_debug_snapshot(backend_env)

    if backend_env not in BACKEND_CHOICES:
        choices = ", ".join(sorted(BACKEND_CHOICES))
        raise RuntimeError(
            f"Unknown AUTOCAD_MCP_BACKEND={backend_env!r}; expected one of: {choices}"
        )

    if backend_env == "ezdxf":
        return "ezdxf"

    if backend_env in ("auto", "file_ipc"):
        if WIN32_AVAILABLE:
            try:
                from t20_mcp.backends.file_ipc import find_autocad_window

                hwnd = find_autocad_window()
                if hwnd:
                    log.info("autocad_window_found", hwnd=hwnd)
                    return "file_ipc"
                elif backend_env == "file_ipc":
                    raise RuntimeError(
                        "AUTOCAD_MCP_BACKEND=file_ipc but no AutoCAD window found. "
                        "Start AutoCAD + T20 and open a .dwg file."
                    )
            except ImportError:
                if backend_env == "file_ipc":
                    raise RuntimeError(
                        "AUTOCAD_MCP_BACKEND=file_ipc requires pywin32. "
                        "Install with: pip install pywin32"
                    )
                log.info("win32_deps_missing_fallback_ezdxf")
        elif backend_env == "file_ipc":
            raise RuntimeError(
                "AUTOCAD_MCP_BACKEND=file_ipc requires Windows. "
                "Use AUTOCAD_MCP_BACKEND=ezdxf for headless mode."
            )
        elif _is_wsl():
            log.info(
                "wsl_linux_python_fallback_ezdxf",
                platform=sys.platform,
                python=sys.executable,
                hint="Launch MCP with Windows python.exe for File IPC backend.",
            )

    log.info("using_ezdxf_backend")
    return "ezdxf"
