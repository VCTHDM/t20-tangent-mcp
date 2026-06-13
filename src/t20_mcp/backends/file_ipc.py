"""File-based IPC backend for AutoCAD LT.

Protocol:
1. Python writes JSON command to C:/temp/t20_mcp_cmd_{request_id}.json
2. Python types the fixed string "(c:mcp-dispatch)" + Enter
3. LISP reads cmd, dispatches via command map, writes result to
   C:/temp/t20_mcp_result_{request_id}.json
4. Python polls for result file (100ms intervals, 10s timeout)
"""

from __future__ import annotations

import asyncio
import json
import locale
import os
import sys
import time
import uuid
from pathlib import Path

import structlog

from t20_mcp.backends.base import AutoCADBackend, BackendCapabilities, CommandResult
from t20_mcp.config import ACAD_PROCESS_NAME, IPC_DIR, IPC_TIMEOUT, LISP_DIR

log = structlog.get_logger()

# IPC settings
POLL_INTERVAL = 0.1  # seconds
TIMEOUT = IPC_TIMEOUT  # seconds (configurable via AUTOCAD_MCP_IPC_TIMEOUT)
STALE_THRESHOLD = 60.0  # clean up files older than this


def _decode_result_bytes(raw: bytes, ansi: str | None = None) -> str:
    """Decode an AutoLISP-written result file under the编码契约.

    Order: the OS ANSI code page (cp936 on Chinese Windows — what AutoLISP
    (write-line) actually produces, per _prelude.lsp 编码契约 §3) → utf-8 →
    cp936 (if ANSI differed) → cp1252.

    ANSI must come BEFORE utf-8: 真机E2E发现 "砖" 的 GBK 字节 D7A9 恰是合法
    UTF-8 (U+05E9 ש), utf-8 优先会把正确的 GBK 文本静默解成 mojibake。结果
    文件按契约必然是 ANSI 写出, ASCII 内容在 ANSI 下解码结果相同, 因此 ANSI
    优先无回归。cp1252 strictly last: it decodes almost any byte sequence
    without raising, so trying it early would silently accept mojibake.
    """
    if ansi is None:
        try:
            ansi = locale.getpreferredencoding(False) or "cp936"
        except Exception:
            ansi = "cp936"

    candidates = [ansi, "utf-8"]
    if ansi.lower().replace("-", "") != "cp936":
        candidates.append("cp936")
    candidates.append("cp1252")

    for enc in candidates:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # Final fallback: never lose the bytes entirely.
    return raw.decode("cp1252", errors="replace")


def _process_image_name(pid: int) -> str:
    """Return the lowercased basename of the process image (e.g. 'acad.exe').

    Uses QueryFullProcessImageNameW with PROCESS_QUERY_LIMITED_INFORMATION so it
    works without elevated rights (Vista+). Returns "" on any failure.
    """
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            buf_len = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(buf_len.value)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(buf_len)):
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            k32.CloseHandle(h)
    except Exception:
        return ""


def find_autocad_window() -> int | None:
    """Find the AutoCAD/T20 main window handle.

    Primary criterion is the process image name (default ``acad.exe``, override
    via ``AUTOCAD_MCP_ACAD_PROCESS``): the T20 launcher may rewrite the window
    title to "T20天正建筑 Vxx…" which contains no "autocad", so a title-only
    match is unreliable. Title ("autocad"/"天正"/"tarch") is a secondary signal
    used only to disambiguate. When several acad.exe windows match, prefer the
    one whose title contains ".dwg" and log a multi-instance warning.
    """
    if sys.platform != "win32":
        return None
    try:
        import win32gui
        import win32process
    except ImportError:
        return None

    title_hints = ("autocad", "天正", "tarch")
    primary: list[tuple[int, str]] = []   # process-name matches: (hwnd, title)
    secondary: list[tuple[int, str]] = []  # title-only matches (fallback)

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            title = ""
        tlow = title.lower()
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pid = 0
        image = _process_image_name(pid) if pid else ""
        if image == ACAD_PROCESS_NAME:
            primary.append((hwnd, tlow))
        elif any(h in tlow for h in title_hints):
            secondary.append((hwnd, tlow))
        return True

    win32gui.EnumWindows(callback, None)

    candidates = primary or secondary
    if not candidates:
        return None

    # Prefer a window whose title names a .dwg (the active drawing window).
    with_dwg = [hwnd for hwnd, t in candidates if ".dwg" in t]
    chosen = with_dwg[0] if with_dwg else candidates[0][0]
    if len(candidates) > 1:
        log.warning(
            "multiple_autocad_windows",
            count=len(candidates),
            used_process_match=bool(primary),
            chose_dwg_title=bool(with_dwg),
            chosen_hwnd=chosen,
        )
    return chosen


class FileIPCBackend(AutoCADBackend):
    """File-based IPC with AutoCAD LT via mcp_dispatch.lsp."""

    def __init__(self):
        self._hwnd: int | None = None
        self._command_hwnd: int | None = None
        self._ipc_dir = Path(IPC_DIR)
        self._screenshot_provider = None
        self._lock = asyncio.Lock()  # Single in-flight command
        # P1-2: only inject ESC cancel after a previous request timed out, so we
        # don't clobber a user's in-progress command on every dispatch.
        self._needs_cancel = False

    @property
    def name(self) -> str:
        return "file_ipc"

    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            can_read_drawing=True,
            can_modify_entities=True,
            can_create_entities=True,
            can_screenshot=True,
            can_save=True,
            can_plot_pdf=True,
            can_zoom=True,
            can_query_entities=True,
            can_file_operations=True,
            can_undo=True,
        )

    async def initialize(self) -> CommandResult:
        """Find AutoCAD window and verify dispatcher is loaded."""
        self._hwnd = find_autocad_window()
        if not self._hwnd:
            return CommandResult(
                ok=False,
                error=(
                    f"AutoCAD/T20 window not found (no '{ACAD_PROCESS_NAME}' process window). "
                    "Start AutoCAD + T20 and open a .dwg, or set AUTOCAD_MCP_ACAD_PROCESS."
                ),
            )

        # Set up screenshot provider
        try:
            from t20_mcp.screenshot import Win32ScreenshotProvider

            self._screenshot_provider = Win32ScreenshotProvider(self._hwnd)
        except Exception:
            pass

        # Find command-line child edit control for focus-free dispatch
        self._command_hwnd = self._find_command_line_hwnd()
        log.info("command_line_hwnd", hwnd=self._command_hwnd)

        # Ensure IPC directory exists
        self._ipc_dir.mkdir(parents=True, exist_ok=True)

        # Clean up stale IPC files
        self._cleanup_stale_files()

        # Ping the dispatcher to verify it's loaded
        result = await self._dispatch("ping", {})
        if not result.ok:
            lisp_path = str(LISP_DIR / "mcp_dispatch.lsp").replace("\\", "/")
            return CommandResult(
                ok=False,
                error=(
                    "AutoCAD/T20 detected but mcp_dispatch.lsp not loaded.\n"
                    f'In AutoCAD command line, type:\n  (load "{lisp_path}")\n'
                    "Or add lisp-code/ to trusted paths for auto-loading."
                ),
            )

        return CommandResult(ok=True, payload={"backend": "file_ipc", "hwnd": self._hwnd})

    async def status(self) -> CommandResult:
        info = {
            "backend": "file_ipc",
            "hwnd": self._hwnd,
            "ipc_dir": str(self._ipc_dir),
            "capabilities": {k: v for k, v in self.capabilities.__dict__.items()},
        }
        return CommandResult(ok=True, payload=info)

    # --- IPC dispatch ---

    async def _dispatch(self, command: str, params: dict) -> CommandResult:
        """Send a command via file IPC and wait for result."""
        async with self._lock:
            return await self._dispatch_unlocked(command, params)

    async def _dispatch_unlocked(self, command: str, params: dict) -> CommandResult:
        """Core IPC logic (must be called under _lock)."""
        request_id = uuid.uuid4().hex[:12]
        cmd_file = self._ipc_dir / f"t20_mcp_cmd_{request_id}.json"
        result_file = self._ipc_dir / f"t20_mcp_result_{request_id}.json"
        tmp_file = cmd_file.with_suffix(".tmp")

        # P1-2: refuse to dispatch while AutoCAD is blocked by a modal dialog.
        # Sending the trigger then would be swallowed by the dialog's message
        # loop (only a timeout, no diagnostic), and a stray ESC could cancel the
        # user's in-progress operation.
        if self._autocad_modal_dialog_present():
            return CommandResult(
                ok=False,
                error="AutoCAD 正被对话框阻塞，请关闭后重试",
            )

        try:
            # Strip None values — the simple LISP JSON parser can't handle null
            clean_params = {k: v for k, v in params.items() if v is not None}
            # Atomic write: write to .tmp, then rename
            payload = {
                "request_id": request_id,
                "command": command,
                "params": clean_params,
                "ts": time.time(),
            }
            # P2-1: ensure_ascii=False keeps 中文 as real characters (not \uXXXX,
            # which the dispatcher's minimal JSON parser can't decode), and the
            # command file is written GBK to match the encoding contract — AutoCAD
            # reads .json command files in the system ANSI page (cp936) just like
            # .lsp. errors="replace" keeps a stray non-GBK char from aborting the
            # whole dispatch (param-layer GBK validation is the real gate).
            cmd_json = json.dumps(payload, ensure_ascii=False)
            tmp_file.write_bytes(cmd_json.encode("gbk", errors="replace"))
            tmp_file.rename(cmd_file)

            # Type the fixed dispatch trigger. Only inject ESC cancel when the
            # previous request timed out (it may have left AutoCAD at a command
            # prompt); on the normal path ESC would disturb the user's state.
            self._type_dispatch_trigger(send_cancel=self._needs_cancel)
            self._needs_cancel = False

            # Poll for result
            deadline = time.time() + TIMEOUT
            while time.time() < deadline:
                if result_file.exists():
                    try:
                        # AutoLISP (write-line) writes the result file in the
                        # system ANSI code page. On Chinese Windows that is
                        # cp936 (GBK), NOT Windows-1252. Decode order: ANSI
                        # first (真机证实 GBK 字节可能恰为合法 UTF-8, 如 "砖"
                        # = D7A9 = ש), then utf-8, then cp1252 strictly last.
                        # See _decode_result_bytes.
                        text = _decode_result_bytes(result_file.read_bytes())
                        data = json.loads(text)
                        # Verify request_id matches
                        if data.get("request_id") == request_id:
                            return CommandResult(
                                ok=data.get("ok", False),
                                payload=data.get("payload"),
                                error=data.get("error"),
                            )
                    except (json.JSONDecodeError, OSError):
                        pass  # File may be partially written, retry
                await asyncio.sleep(POLL_INTERVAL)

            # Timed out: arm ESC cancel for the next dispatch's first attempt.
            self._needs_cancel = True
            return CommandResult(ok=False, error=f"Timeout waiting for result (request_id={request_id})")

        finally:
            # Cleanup
            for f in (cmd_file, result_file, tmp_file):
                try:
                    f.unlink(missing_ok=True)
                except OSError:
                    pass

    def _find_command_line_hwnd(self) -> int | None:
        """Find AutoCAD's MDIClient child window for command routing."""
        if sys.platform != "win32" or not self._hwnd:
            return None
        try:
            import win32gui

            mdi_client: list[int] = []

            def cb(child_hwnd, _):
                if win32gui.GetClassName(child_hwnd) == "MDIClient":
                    mdi_client.append(child_hwnd)
                    return False  # stop enumeration
                return True

            win32gui.EnumChildWindows(self._hwnd, cb, None)
            return mdi_client[0] if mdi_client else None
        except Exception:
            return None

    def _autocad_modal_dialog_present(self) -> bool:
        """Best-effort check whether AutoCAD is blocked by a modal dialog.

        Two signals, either one positive ⇒ blocked:

        1. **主窗口被禁用** (``IsWindowEnabled == FALSE``): any modal loop —
           native ``#32770``, ObjectARX, or T20's WPF ``HwndWrapper[...]``
           export dialogs (P1-2 盲区) — disables its owner window. Class-name
           matching on ``HwndWrapper`` alone would false-positive on T20's
           non-modal WPF palettes (门窗面板等), so the owner-disabled state is
           the discriminator: non-modal panels leave the main window enabled.
        2. A visible standard dialog (class ``#32770``) as active popup or on
           the main UI thread (original check, kept as belt-and-braces).

        Advisory: on any error or uncertainty it returns False and the
        dispatch proceeds.
        """
        if sys.platform != "win32" or not self._hwnd:
            return False
        try:
            import ctypes

            import win32gui
            import win32process

            if not ctypes.windll.user32.IsWindowEnabled(self._hwnd):
                return True

            popup = win32gui.GetLastActivePopup(self._hwnd)
            if (
                popup
                and popup != self._hwnd
                and win32gui.IsWindowVisible(popup)
                and win32gui.GetClassName(popup) == "#32770"
            ):
                return True

            tid, _ = win32process.GetWindowThreadProcessId(self._hwnd)
            found: list[int] = []

            def cb(hwnd, _):
                try:
                    if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "#32770":
                        found.append(hwnd)
                except Exception:
                    pass
                return True

            win32gui.EnumThreadWindows(tid, cb, None)
            return bool(found)
        except Exception:
            return False

    def _type_dispatch_trigger(self, send_cancel: bool = False):
        """Post '(c:mcp-dispatch)' + Enter via WM_CHAR to MDIClient — no focus steal.

        When ``send_cancel`` is True (only after a previous timeout), injects ESC
        first to clear a stale pending command. On the normal path ESC is skipped
        so we never cancel a user's in-progress operation.
        """
        try:
            import ctypes

            WM_CHAR = 0x0102
            WM_KEYDOWN = 0x0100
            WM_KEYUP = 0x0101
            VK_ESCAPE = 0x1B
            target = self._command_hwnd or self._hwnd
            post = ctypes.windll.user32.PostMessageW

            if send_cancel:
                # Cancel any stale pending command (2x ESC for nested commands)
                for _ in range(2):
                    post(target, WM_KEYDOWN, VK_ESCAPE, 0)
                    post(target, WM_KEYUP, VK_ESCAPE, 0)
                time.sleep(0.05)

            for ch in "(c:mcp-dispatch)":
                post(target, WM_CHAR, ord(ch), 0)
            # Enter = carriage return
            post(target, WM_CHAR, 0x0D, 0)
            time.sleep(0.05)
        except Exception as e:
            log.error("dispatch_trigger_failed", error=str(e))

    def _cleanup_stale_files(self):
        """Remove stale IPC files from previous sessions."""
        try:
            now = time.time()
            for pattern in ("t20_mcp_*.json", "t20_mcp_*.tmp", "t20_mcp_lisp_*.lsp"):
                for f in self._ipc_dir.glob(pattern):
                    if now - f.stat().st_mtime > STALE_THRESHOLD:
                        f.unlink(missing_ok=True)
        except OSError:
            pass

    # --- Drawing management ---

    async def drawing_info(self) -> CommandResult:
        return await self._dispatch("drawing-info", {})

    async def drawing_save(self, path: str | None = None) -> CommandResult:
        return await self._dispatch("drawing-save", {"path": path})

    async def drawing_save_as_dxf(self, path: str) -> CommandResult:
        return await self._dispatch("drawing-save-as-dxf", {"path": path})

    async def drawing_create(self, name: str | None = None) -> CommandResult:
        return await self._dispatch("drawing-create", {"name": name})

    async def drawing_purge(self) -> CommandResult:
        return await self._dispatch("drawing-purge", {})

    async def drawing_plot_pdf(self, path: str) -> CommandResult:
        return await self._dispatch("drawing-plot-pdf", {"path": path})

    async def drawing_get_variables(self, names: list[str] | None = None) -> CommandResult:
        if names:
            # Strip $ prefix for AutoCAD compatibility (ezdxf uses $ACADVER, AutoCAD uses ACADVER)
            clean_names = [n.lstrip("$") for n in names]
            names_str = ";".join(clean_names)
        else:
            names_str = ""
        return await self._dispatch("drawing-get-variables", {"names_str": names_str})

    async def drawing_open(self, path: str) -> CommandResult:
        return await self._dispatch("drawing-open", {"path": path})

    # --- Undo / Redo ---

    async def undo(self) -> CommandResult:
        return await self._dispatch("undo", {})

    async def redo(self) -> CommandResult:
        return await self._dispatch("redo", {})

    # --- Freehand LISP execution ---

    async def execute_lisp(self, code: str) -> CommandResult:
        """Execute arbitrary AutoLISP code via temp file.

        File persists for session; cleaned up by _cleanup_stale_files().

        编码契约 (见 _prelude.lsp §2): AutoCAD (load) 在 2021 之前只按系统
        ANSI 代码页解码 .lsp; 中文 Windows 上 = GBK(cp936)。仓库内模板是
        UTF-8, 转码只发生在这里 —— 写盘前整体转为 GBK, 不带 BOM。
        errors="strict": GBK 表示不了的字符 (emoji/扩展区汉字) 直接报错,
        而不是写出乱码导致命令找不到/参数错却无报错。
        """
        request_id = uuid.uuid4().hex[:12]
        code_file = self._ipc_dir / f"t20_mcp_lisp_{request_id}.lsp"
        try:
            gbk_bytes = code.encode("gbk", errors="strict")
        except UnicodeEncodeError as e:
            bad = code[e.start:e.end]
            return CommandResult(
                ok=False,
                error=(
                    f"LISP 代码含 GBK 无法编码的字符 {bad!r} (位置 {e.start}); "
                    "天正/AutoCAD 按 GBK 加载 .lsp, 请移除 emoji 或扩展区字符。"
                ),
            )
        code_file.write_bytes(gbk_bytes)
        return await self._dispatch("execute-lisp", {
            "code_file": str(code_file).replace("\\", "/")
        })

    # --- Entity operations ---

    async def create_line(self, x1, y1, x2, y2, layer=None) -> CommandResult:
        return await self._dispatch("create-line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer})

    async def create_circle(self, cx, cy, radius, layer=None) -> CommandResult:
        return await self._dispatch("create-circle", {"cx": cx, "cy": cy, "radius": radius, "layer": layer})

    async def create_polyline(self, points, closed=False, layer=None) -> CommandResult:
        pts_str = ";".join(f"{p[0]},{p[1]}" for p in points)
        return await self._dispatch("create-polyline", {
            "points_str": pts_str, "closed": "1" if closed else "0", "layer": layer
        })

    async def create_rectangle(self, x1, y1, x2, y2, layer=None) -> CommandResult:
        return await self._dispatch("create-rectangle", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "layer": layer})

    async def create_arc(self, cx, cy, radius, start_angle, end_angle, layer=None) -> CommandResult:
        return await self._dispatch("create-arc", {"cx": cx, "cy": cy, "radius": radius, "start_angle": start_angle, "end_angle": end_angle, "layer": layer})

    async def create_ellipse(self, cx, cy, major_x, major_y, ratio, layer=None) -> CommandResult:
        return await self._dispatch("create-ellipse", {"cx": cx, "cy": cy, "major_x": major_x, "major_y": major_y, "ratio": ratio, "layer": layer})

    async def create_mtext(self, x, y, width, text, height=2.5, layer=None) -> CommandResult:
        return await self._dispatch("create-mtext", {"x": x, "y": y, "width": width, "text": text, "height": height, "layer": layer})

    async def create_hatch(self, entity_id, pattern="ANSI31") -> CommandResult:
        return await self._dispatch("create-hatch", {"entity_id": entity_id, "pattern": pattern})

    async def entity_list(self, layer=None) -> CommandResult:
        return await self._dispatch("entity-list", {"layer": layer})

    async def entity_count(self, layer=None) -> CommandResult:
        return await self._dispatch("entity-count", {"layer": layer})

    async def entity_get(self, entity_id) -> CommandResult:
        return await self._dispatch("entity-get", {"entity_id": entity_id})

    async def entity_erase(self, entity_id) -> CommandResult:
        return await self._dispatch("entity-erase", {"entity_id": entity_id})

    async def entity_copy(self, entity_id, dx, dy) -> CommandResult:
        return await self._dispatch("entity-copy", {"entity_id": entity_id, "dx": dx, "dy": dy})

    async def entity_move(self, entity_id, dx, dy) -> CommandResult:
        return await self._dispatch("entity-move", {"entity_id": entity_id, "dx": dx, "dy": dy})

    async def entity_rotate(self, entity_id, cx, cy, angle) -> CommandResult:
        return await self._dispatch("entity-rotate", {"entity_id": entity_id, "cx": cx, "cy": cy, "angle": angle})

    async def entity_scale(self, entity_id, cx, cy, factor) -> CommandResult:
        return await self._dispatch("entity-scale", {"entity_id": entity_id, "cx": cx, "cy": cy, "factor": factor})

    async def entity_mirror(self, entity_id, x1, y1, x2, y2) -> CommandResult:
        return await self._dispatch("entity-mirror", {"entity_id": entity_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2})

    async def entity_offset(self, entity_id, distance) -> CommandResult:
        return await self._dispatch("entity-offset", {"entity_id": entity_id, "distance": distance})

    async def entity_array(self, entity_id, rows, cols, row_dist, col_dist) -> CommandResult:
        return await self._dispatch("entity-array", {"entity_id": entity_id, "rows": rows, "cols": cols, "row_dist": row_dist, "col_dist": col_dist})

    async def entity_fillet(self, entity_id1, entity_id2, radius) -> CommandResult:
        return await self._dispatch("entity-fillet", {"id1": entity_id1, "id2": entity_id2, "radius": radius})

    async def entity_chamfer(self, entity_id1, entity_id2, dist1, dist2) -> CommandResult:
        return await self._dispatch("entity-chamfer", {"id1": entity_id1, "id2": entity_id2, "dist1": dist1, "dist2": dist2})

    # --- Layer operations ---

    async def layer_list(self) -> CommandResult:
        return await self._dispatch("layer-list", {})

    async def layer_create(self, name, color="white", linetype="CONTINUOUS") -> CommandResult:
        return await self._dispatch("layer-create", {"name": name, "color": color, "linetype": linetype})

    async def layer_set_current(self, name) -> CommandResult:
        return await self._dispatch("layer-set-current", {"name": name})

    async def layer_set_properties(self, name, color=None, linetype=None, lineweight=None) -> CommandResult:
        return await self._dispatch("layer-set-properties", {"name": name, "color": color, "linetype": linetype, "lineweight": lineweight})

    async def layer_freeze(self, name) -> CommandResult:
        return await self._dispatch("layer-freeze", {"name": name})

    async def layer_thaw(self, name) -> CommandResult:
        return await self._dispatch("layer-thaw", {"name": name})

    async def layer_lock(self, name) -> CommandResult:
        return await self._dispatch("layer-lock", {"name": name})

    async def layer_unlock(self, name) -> CommandResult:
        return await self._dispatch("layer-unlock", {"name": name})

    # --- Block operations ---

    async def block_list(self) -> CommandResult:
        return await self._dispatch("block-list", {})

    async def block_insert(self, name, x, y, scale=1.0, rotation=0.0, block_id=None) -> CommandResult:
        return await self._dispatch("block-insert", {"name": name, "x": x, "y": y, "scale": scale, "rotation": rotation, "block_id": block_id})

    async def block_insert_with_attributes(self, name, x, y, scale=1.0, rotation=0.0, attributes=None) -> CommandResult:
        return await self._dispatch("block-insert-with-attributes", {"name": name, "x": x, "y": y, "scale": scale, "rotation": rotation, "attributes": attributes or {}})

    async def block_get_attributes(self, entity_id) -> CommandResult:
        return await self._dispatch("block-get-attributes", {"entity_id": entity_id})

    async def block_update_attribute(self, entity_id, tag, value) -> CommandResult:
        return await self._dispatch("block-update-attribute", {"entity_id": entity_id, "tag": tag, "value": value})

    async def block_define(self, name, entities) -> CommandResult:
        return await self._dispatch("block-define", {"name": name, "entities": entities})

    # --- Annotation ---

    async def create_text(self, x, y, text, height=2.5, rotation=0.0, layer=None) -> CommandResult:
        return await self._dispatch("create-text", {"x": x, "y": y, "text": text, "height": height, "rotation": rotation, "layer": layer})

    async def create_dimension_linear(self, x1, y1, x2, y2, dim_x, dim_y) -> CommandResult:
        return await self._dispatch("create-dimension-linear", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "dim_x": dim_x, "dim_y": dim_y})

    async def create_dimension_aligned(self, x1, y1, x2, y2, offset) -> CommandResult:
        return await self._dispatch("create-dimension-aligned", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "offset": offset})

    async def create_dimension_angular(self, cx, cy, x1, y1, x2, y2) -> CommandResult:
        return await self._dispatch("create-dimension-angular", {"cx": cx, "cy": cy, "x1": x1, "y1": y1, "x2": x2, "y2": y2})

    async def create_dimension_radius(self, cx, cy, radius, angle) -> CommandResult:
        return await self._dispatch("create-dimension-radius", {"cx": cx, "cy": cy, "radius": radius, "angle": angle})

    async def create_leader(self, points, text) -> CommandResult:
        pts_str = ";".join(f"{p[0]},{p[1]}" for p in points)
        return await self._dispatch("create-leader", {"points_str": pts_str, "text": text})

    # --- P&ID ---

    async def pid_setup_layers(self) -> CommandResult:
        return await self._dispatch("pid-setup-layers", {})

    async def pid_insert_symbol(self, category, symbol, x, y, scale=1.0, rotation=0.0) -> CommandResult:
        return await self._dispatch("pid-insert-symbol", {"category": category, "symbol": symbol, "x": x, "y": y, "scale": scale, "rotation": rotation})

    async def pid_list_symbols(self, category) -> CommandResult:
        return await self._dispatch("pid-list-symbols", {"category": category})

    async def pid_draw_process_line(self, x1, y1, x2, y2) -> CommandResult:
        return await self._dispatch("pid-draw-process-line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    async def pid_connect_equipment(self, x1, y1, x2, y2) -> CommandResult:
        return await self._dispatch("pid-connect-equipment", {"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    async def pid_add_flow_arrow(self, x, y, rotation=0.0) -> CommandResult:
        return await self._dispatch("pid-add-flow-arrow", {"x": x, "y": y, "rotation": rotation})

    async def pid_add_equipment_tag(self, x, y, tag, description="") -> CommandResult:
        return await self._dispatch("pid-add-equipment-tag", {"x": x, "y": y, "tag": tag, "description": description})

    async def pid_add_line_number(self, x, y, line_num, spec) -> CommandResult:
        return await self._dispatch("pid-add-line-number", {"x": x, "y": y, "line_num": line_num, "spec": spec})

    async def pid_insert_valve(self, x, y, valve_type, rotation=0.0, attributes=None) -> CommandResult:
        return await self._dispatch("pid-insert-valve", {"x": x, "y": y, "valve_type": valve_type, "rotation": rotation, "attributes": attributes or {}})

    async def pid_insert_instrument(self, x, y, instrument_type, rotation=0.0, tag_id="", range_value="") -> CommandResult:
        return await self._dispatch("pid-insert-instrument", {"x": x, "y": y, "instrument_type": instrument_type, "rotation": rotation, "tag_id": tag_id, "range_value": range_value})

    async def pid_insert_pump(self, x, y, pump_type, rotation=0.0, attributes=None) -> CommandResult:
        return await self._dispatch("pid-insert-pump", {"x": x, "y": y, "pump_type": pump_type, "rotation": rotation, "attributes": attributes or {}})

    async def pid_insert_tank(self, x, y, tank_type, scale=1.0, attributes=None) -> CommandResult:
        return await self._dispatch("pid-insert-tank", {"x": x, "y": y, "tank_type": tank_type, "scale": scale, "attributes": attributes or {}})

    # --- View ---

    async def zoom_extents(self) -> CommandResult:
        return await self._dispatch("zoom-extents", {})

    async def zoom_window(self, x1, y1, x2, y2) -> CommandResult:
        return await self._dispatch("zoom-window", {"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    async def get_screenshot(self) -> CommandResult:
        if self._screenshot_provider:
            data = self._screenshot_provider.capture()
            if data:
                return CommandResult(ok=True, payload=data)
        return CommandResult(ok=False, error="Screenshot capture failed")
