"""离线测试: 编码链 (P0-1/P0-2)、dry-run 工具行为 (P0-5)、参数 GBK 校验 (P1-3)。

不连接 AutoCAD / 天正:
  * P0-1: 结果文件 GBK 字节解码无损, cp1252 不再静默放行中文乱码。
  * P0-2: 含中文的模板按 GBK 往返一致; GBK 外字符 (emoji) 被拒并提示 "GBK"。
  * P0-5: 默认 dry-run 不接触 backend (不产生 IPC); execute=True 行为不变;
          低置信子命令返回含 warning。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from t20_mcp.backends.base import CommandResult
from t20_mcp.backends.file_ipc import FileIPCBackend, _decode_result_bytes
from t20_mcp.tools.tangent import execute_opening, generate_lisp

# ---------------------------------------------------------------------------
# P0-1 结果文件解码链 utf-8 -> cp936 -> ... -> cp1252
# ---------------------------------------------------------------------------


class TestDecodeResultBytes:
    def test_gbk_chinese_payload_lossless(self) -> None:
        # 模拟 AutoLISP (write-line) 在中文 Windows 写出的 GBK 结果文件
        data = {"request_id": "abc", "ok": True, "payload": {"层": "墙体", "msg": "砖墙已绘制"}}
        raw = json.dumps(data, ensure_ascii=False).encode("gbk")
        text = _decode_result_bytes(raw, ansi="cp936")
        back = json.loads(text)
        assert back["payload"]["层"] == "墙体"
        assert back["payload"]["msg"] == "砖墙已绘制"

    def test_pure_ascii_not_regressed(self) -> None:
        raw = b'{"request_id": "x", "ok": true, "payload": null}'
        assert json.loads(_decode_result_bytes(raw))["request_id"] == "x"

    def test_gbk_utf8_collision_char_not_mojibaked(self) -> None:
        # 真机E2E回归: "砖" 的 GBK 字节 D7A9 恰是合法 UTF-8 (U+05E9 ש)。
        # ANSI 优先解码链必须解出 "砖" 而非希伯来字母。
        raw = '{"v": "砖"}'.encode("gbk")
        assert json.loads(_decode_result_bytes(raw, ansi="cp936"))["v"] == "砖"

    def test_utf8_fallback_when_ansi_decode_fails(self) -> None:
        # "€" 的 UTF-8 字节 E282AC 不是合法 GBK 序列 → 回退 utf-8 解码。
        raw = '{"v": "€"}'.encode("utf-8")
        assert json.loads(_decode_result_bytes(raw, ansi="cp936"))["v"] == "€"


# ---------------------------------------------------------------------------
# P0-2 LISP 代码以 GBK 写出
# ---------------------------------------------------------------------------


class TestExecuteLispGbk:
    def test_wall_with_chinese_roundtrips_as_gbk(self, tmp_path) -> None:
        # 渲染含 "砖墙" 的 wall 模板, 经 execute_lisp 写盘后以 GBK 读回逐字一致。
        code = generate_lisp(
            "wall",
            {
                "x1": 0,
                "y1": 0,
                "x2": 6000,
                "y2": 0,
                "wall_type": "砖墙",
            },
        )
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path

        captured: dict[str, str] = {}

        async def fake_dispatch(command, params):
            assert command == "execute-lisp"
            name = params["code_file"].rsplit("/", 1)[-1]
            written = tmp_path / name
            assert written.exists()
            captured["name"] = name
            captured["roundtrip"] = written.read_bytes().decode("gbk")
            return CommandResult(ok=True, payload={})

        backend._dispatch = fake_dispatch  # type: ignore[assignment]
        result = asyncio.run(backend.execute_lisp(code))
        assert result.ok
        assert "砖墙" in captured["roundtrip"]
        assert captured["roundtrip"] == code
        assert not (tmp_path / captured["name"]).exists()
        assert list(tmp_path.glob("*.lsp")) == []

    def test_temporary_lisp_is_cleaned_when_dispatch_raises(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path

        async def failing_dispatch(_command, _params):
            assert list(tmp_path.glob("*.lsp"))
            raise RuntimeError("dispatch failed")

        backend._dispatch = failing_dispatch  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="dispatch failed"):
            asyncio.run(backend.execute_lisp("(princ)"))
        assert list(tmp_path.glob("*.lsp")) == []

    def test_temporary_lisp_is_preserved_after_ambiguous_timeout(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path

        async def timed_out_dispatch(_command, _params):
            return CommandResult(
                ok=False,
                payload={"code": "IPC_TIMEOUT", "request_id": "test"},
                error="Timeout waiting for result (request_id=test)",
            )

        backend._dispatch = timed_out_dispatch  # type: ignore[assignment]
        result = asyncio.run(backend.execute_lisp("(princ)"))

        assert result.ok is False
        assert "Timeout waiting" in (result.error or "")
        assert len(list(tmp_path.glob("t20_mcp_lisp_*.lsp"))) == 1

    def test_temporary_lisp_is_preserved_when_dispatch_is_cancelled(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path

        async def cancelled_dispatch(_command, _params):
            raise asyncio.CancelledError

        backend._dispatch = cancelled_dispatch  # type: ignore[assignment]
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(backend.execute_lisp("(princ)"))

        assert len(list(tmp_path.glob("t20_mcp_lisp_*.lsp"))) == 1

    def test_emoji_rejected_with_gbk_hint(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path
        result = asyncio.run(backend.execute_lisp('(princ "测试🔥")'))
        assert result.ok is False
        assert "GBK" in (result.error or "")
        assert "🔥" in (result.error or "")
        # 不应写出任何 .lsp 文件
        assert list(tmp_path.glob("*.lsp")) == []

    def test_stale_cleanup_threshold_exceeds_request_timeout_buffer(self) -> None:
        import t20_mcp.backends.file_ipc as file_ipc
        from t20_mcp.config import IPC_TIMEOUT_MAX

        assert file_ipc.STALE_THRESHOLD >= IPC_TIMEOUT_MAX + 30.0


# ---------------------------------------------------------------------------
# P0-5 dry-run 默认开 / execute=True / 低置信 warning
# ---------------------------------------------------------------------------


class _FakeMCP:
    """捕获被注册的 tangent 工具函数。"""

    def __init__(self) -> None:
        self.fn = None

    def tool(self, *args, **kwargs):
        def deco(fn):
            self.fn = fn
            return fn

        return deco


def _register_with_fake_backend(monkeypatch, backend_or_exc):
    """在注册 tangent 工具前替换 client.get_backend, 返回工具函数。"""
    import t20_mcp.client as client

    async def fake_get_backend():
        if isinstance(backend_or_exc, Exception):
            raise backend_or_exc
        return backend_or_exc

    monkeypatch.setattr(client, "get_backend", fake_get_backend)
    from t20_mcp.tools.tangent import register_tangent_tool

    mcp = _FakeMCP()
    register_tangent_tool(mcp)
    assert mcp.fn is not None
    return mcp.fn


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute_lisp(self, code: str) -> CommandResult:
        self.calls.append(code)
        return CommandResult(ok=True, payload={"echo": "ok"})


class _OpeningStatusBackend(_FakeBackend):
    def __init__(self, payload: str) -> None:
        super().__init__()
        self.payload = payload

    async def execute_lisp(self, code: str) -> CommandResult:
        self.calls.append(code)
        return CommandResult(ok=True, payload=self.payload)


class _LiveOpeningBackend(_FakeBackend):
    """带 FileIPC 窗口字段的门窗自动化假 backend。"""

    def __init__(self, payload: str) -> None:
        super().__init__()
        self.payload = payload
        self._hwnd = 123
        self._command_hwnd = 456
        self._needs_cancel = False

    async def execute_lisp(self, code: str) -> CommandResult:
        self.calls.append(code)
        if len(self.calls) == 1:
            return CommandResult(ok=True, payload="active=1")
        return CommandResult(ok=True, payload=self.payload)


def test_command_result_preserves_structured_error_payload() -> None:
    result = CommandResult(
        ok=False,
        error="mode mismatch",
        payload={"code": "OPENING_MODE_MISMATCH"},
    )
    assert result.to_dict() == {
        "ok": False,
        "error": "mode mismatch",
        "payload": {"code": "OPENING_MODE_MISMATCH"},
    }


def test_package_version_comes_from_project_metadata() -> None:
    from importlib.metadata import version

    from t20_mcp import __version__

    assert __version__ == version("t20-mcp")


class TestParamsCmdFileEncoding:
    def test_chinese_params_written_as_gbk_not_unicode_escape(self, tmp_path, monkeypatch) -> None:
        # P2-1: 命令文件以 GBK + ensure_ascii=False 写出, 中文不变 \uXXXX。
        import t20_mcp.backends.file_ipc as fip

        monkeypatch.setattr(fip, "TIMEOUT", 0.0)
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._ipc_dir = tmp_path
        backend._autocad_modal_dialog_present = lambda: False  # type: ignore[assignment]

        captured: dict[str, bytes] = {}

        def grab(send_cancel=False):
            for f in tmp_path.glob("t20_mcp_cmd_*.json"):
                captured["raw"] = f.read_bytes()

        backend._type_dispatch_trigger = grab  # type: ignore[assignment]
        asyncio.run(backend._dispatch("layer-create", {"name": "墙体图层"}))

        raw = captured["raw"]
        assert b"\\u" not in raw  # 不是 \uXXXX 转义
        assert "墙体图层" in raw.decode("gbk")

    def test_non_gbk_param_is_rejected_instead_of_replaced(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._ipc_dir = tmp_path
        backend._autocad_modal_dialog_present = lambda: False  # type: ignore[assignment]
        sent: list[bool] = []
        backend._type_dispatch_trigger = lambda send_cancel=False: sent.append(send_cancel)  # type: ignore[assignment]

        result = asyncio.run(backend._dispatch("create-mtext", {"text": "not representable 🔥"}))

        assert result.ok is False
        assert "GBK" in (result.error or "")
        assert "🔥" in (result.error or "")
        assert sent == []
        assert list(tmp_path.iterdir()) == []


class TestModalDialogGuard:
    def test_blocked_when_modal_present(self) -> None:
        # P1-2: 检测到模态对话框时, dispatch 直接返回阻塞错误, 不发送触发串。
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._autocad_modal_dialog_present = lambda: True  # type: ignore[assignment]
        sent: list[bool] = []
        backend._type_dispatch_trigger = lambda send_cancel=False: sent.append(send_cancel)  # type: ignore[assignment]
        result = asyncio.run(backend._dispatch("ping", {}))
        assert result.ok is False
        assert "对话框" in (result.error or "")
        assert sent == []  # 未发送触发串

    def test_esc_only_after_timeout(self, tmp_path, monkeypatch) -> None:
        # P1-2: 正常首次 dispatch 不注入 ESC; 上次超时后的首次重发才注入。
        import t20_mcp.backends.file_ipc as fip

        monkeypatch.setattr(fip, "TIMEOUT", 0.0)  # 立即超时
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._ipc_dir = tmp_path
        backend._autocad_modal_dialog_present = lambda: False  # type: ignore[assignment]
        cancels: list[bool] = []
        backend._type_dispatch_trigger = lambda send_cancel=False: cancels.append(send_cancel)  # type: ignore[assignment]

        r1 = asyncio.run(backend._dispatch("ping", {}))  # 超时
        assert r1.ok is False
        r2 = asyncio.run(backend._dispatch("ping", {}))  # 超时后首次重发
        assert r2.ok is False
        assert cancels[0] is False  # 首次不注入 ESC
        assert cancels[1] is True  # 超时后重发注入 ESC


class TestTangentDryRun:
    def test_default_is_dry_run_no_backend(self, monkeypatch) -> None:
        # 默认 execute=False: 即便 get_backend 会抛错, dry-run 也不应触碰它。
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("backend must not be used"))
        out = asyncio.run(fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert payload["executed"] is False
        assert "t20mcp:begin" in payload["lisp"]

    def test_execute_true_runs_backend(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(
            fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}, execute=True)
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert len(backend.calls) == 1  # 真正下发了一次

    def test_execute_opening_normalizes_mode_mismatch_without_registration(self) -> None:
        data = {"ins_x": 1500, "ins_y": 0, "width": 1200, "sill_height": 900}
        backend = _OpeningStatusBackend(
            "T20MCP-OPENING-MODE-MISMATCH|requested=window|expected=1|actual=0|rollback=ok"
        )

        result = asyncio.run(execute_opening(backend, "window", data))

        assert result.ok is False
        assert result.payload["code"] == "OPENING_MODE_MISMATCH"
        assert result.payload["requested_mode"] == "window"
        assert result.payload["actual_mode"] == "door"
        assert result.payload["wrong_entity_rolled_back"] is True
        assert result.payload["retry_operation"] == "window"
        assert result.payload["retry_data"] == data
        assert "OPENING_MODE_MISMATCH" in (result.error or "")
        assert len(backend.calls) == 1

    @pytest.mark.parametrize(
        ("raw_payload", "expected_code"),
        [
            ("rc=nil clean=T n=0 data=", "EXPLODE_FAILED"),
            ("rc=T clean=nil n=0 data=", "EXPLODE_ROLLBACK_INCOMPLETE"),
            ("rc=T clean=T n=0 data=", "EXPLODE_FAILED"),
        ],
    )
    def test_explode_read_registration_rejects_failed_or_unclean_result(
        self,
        monkeypatch,
        raw_payload: str,
        expected_code: str,
    ) -> None:
        backend = _OpeningStatusBackend(raw_payload)
        fn = _register_with_fake_backend(monkeypatch, backend)

        out = asyncio.run(
            fn(
                operation="explode_read",
                data={"handle": "1A3F"},
                execute=True,
            )
        )
        payload = json.loads(out)

        assert payload["ok"] is False
        assert payload["payload"]["code"] == expected_code
        assert expected_code in payload["error"]
        assert len(backend.calls) == 1

    @pytest.mark.parametrize(
        "raw_payload",
        [
            "garbage",
            "rc=T clean=T n=oops data=",
            "rc=T clean=T n=1 data=",
        ],
    )
    def test_explode_read_registration_rejects_invalid_protocol(
        self,
        monkeypatch,
        raw_payload: str,
    ) -> None:
        backend = _OpeningStatusBackend(raw_payload)
        fn = _register_with_fake_backend(monkeypatch, backend)

        payload = json.loads(
            asyncio.run(
                fn(
                    operation="explode_read",
                    data={"handle": "1A3F"},
                    execute=True,
                )
            )
        )

        assert payload["ok"] is False
        assert payload["payload"]["code"] == "EXPLODE_STATUS_INVALID"
        assert payload["payload"]["protocol_valid"] is False
        assert "EXPLODE_STATUS_INVALID" in payload["error"]

    def test_low_confidence_execute_has_warning(self, monkeypatch) -> None:
        backend = _OpeningStatusBackend("T20MCP-OPENING-OK|requested=door|actual=0")
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(operation="door", data={"ins_x": 1500, "ins_y": 0}, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is True
        assert "warning" in payload["payload"]

    def test_opening_unexpected_success_payload_fails_closed(self, monkeypatch) -> None:
        backend = _OpeningStatusBackend("unexpected-success")
        fn = _register_with_fake_backend(monkeypatch, backend)
        data = {"ins_x": 1500, "ins_y": 0}

        out = asyncio.run(fn(operation="door", data=data, execute=True))
        payload = json.loads(out)

        assert payload["ok"] is False
        assert payload["payload"]["code"] == "OPENING_STATUS_INVALID"
        assert payload["payload"]["raw_payload"] == "unexpected-success"
        assert payload["payload"]["retry_data"] == data

    @pytest.mark.parametrize(
        "raw_payload",
        [
            "T20MCP-OPENING-OK|requested=window|actual=0",
            "T20MCP-OPENING-OK|requested=door|actual=1",
        ],
    )
    def test_opening_ok_status_must_match_requested_mode(
        self,
        monkeypatch,
        raw_payload: str,
    ) -> None:
        operation = "window" if "requested=window" in raw_payload else "door"
        backend = _OpeningStatusBackend(raw_payload)
        fn = _register_with_fake_backend(monkeypatch, backend)

        payload = json.loads(
            asyncio.run(
                fn(
                    operation=operation,
                    data={"ins_x": 1500, "ins_y": 0},
                    execute=True,
                )
            )
        )

        assert payload["ok"] is False
        assert payload["payload"]["code"] == "OPENING_STATUS_INVALID"

    @pytest.mark.parametrize(
        ("operation", "raw_payload"),
        [
            (
                "door",
                "T20MCP-OPENING-MODE-MISMATCH|requested=door|expected=1|actual=1|rollback=ok",
            ),
            (
                "window",
                "T20MCP-OPENING-MODE-MISMATCH|requested=window|expected=1|actual=0",
            ),
            ("window", "T20MCP-OPENING-UNKNOWN|requested=window"),
        ],
    )
    def test_opening_malformed_status_fields_fail_closed(
        self,
        monkeypatch,
        operation: str,
        raw_payload: str,
    ) -> None:
        backend = _OpeningStatusBackend(raw_payload)
        fn = _register_with_fake_backend(monkeypatch, backend)

        payload = json.loads(
            asyncio.run(
                fn(
                    operation=operation,
                    data={"ins_x": 1500, "ins_y": 0},
                    execute=True,
                )
            )
        )

        assert payload["ok"] is False
        assert payload["payload"]["code"] == "OPENING_STATUS_INVALID"

    def test_low_confidence_dry_run_has_warning(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="window", data={"ins_x": 1500, "ins_y": 0}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert "warning" in payload
        assert "自动" in payload["warning"]
        assert "group71=1" in payload["warning"]

    def test_opening_live_backend_prepares_mode_before_creation(
        self,
        monkeypatch,
    ) -> None:
        import win32process

        import t20_mcp.dialog_automation as da

        backend = _LiveOpeningBackend("T20MCP-OPENING-OK|requested=window|expected=1|actual=1")
        driven: list[tuple[int, int, str, set[int] | None]] = []

        monkeypatch.setattr(
            win32process,
            "GetWindowThreadProcessId",
            lambda _hwnd: (77, 2232),
        )
        monkeypatch.setattr(da, "find_acad_popups", lambda _pid: [])

        async def fake_drive(pid, cmd_hwnd, mode, *, exclude=None, timeout=5.0):
            driven.append((pid, cmd_hwnd, mode, exclude))
            return "mode-selected"

        monkeypatch.setattr(da, "drive_opening_mode", fake_drive)
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(
            fn(
                operation="window",
                data={"ins_x": 1500, "ins_y": 0, "sill_height": 900},
                execute=True,
            )
        )
        payload = json.loads(out)

        assert payload["ok"] is True
        assert len(backend.calls) == 2
        assert '(list "TOpening")' in backend.calls[0]
        assert "T20MCP-OPENING-OK" in backend.calls[1]
        assert driven == [(2232, 456, "window", set())]

    def test_opening_mode_automation_failure_stops_before_creation(
        self,
        monkeypatch,
    ) -> None:
        import win32process

        import t20_mcp.dialog_automation as da

        backend = _LiveOpeningBackend("T20MCP-OPENING-OK|requested=door|expected=0|actual=0")
        monkeypatch.setattr(
            win32process,
            "GetWindowThreadProcessId",
            lambda _hwnd: (77, 2232),
        )
        monkeypatch.setattr(da, "find_acad_popups", lambda _pid: [])

        async def fake_drive(*_args, **_kwargs):
            return "panel-still-open"

        monkeypatch.setattr(da, "drive_opening_mode", fake_drive)
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(
            fn(
                operation="door",
                data={"ins_x": 1500, "ins_y": 0},
                execute=True,
            )
        )
        payload = json.loads(out)

        assert payload["ok"] is False
        assert payload["payload"]["code"] == "OPENING_MODE_AUTOMATION_FAILED"
        assert payload["payload"]["automation"] == "panel-still-open"
        assert len(backend.calls) == 1
        assert backend._needs_cancel is True

    @pytest.mark.parametrize(
        ("operation", "actual", "target_zh", "data"),
        [
            ("window", "0", "窗", {"ins_x": 1500, "ins_y": 0, "width": 1200, "sill_height": 900}),
            ("door", "1", "门", {"ins_x": 1500, "ins_y": 0, "width": 900, "sill_distance": 0}),
        ],
    )
    def test_opening_mode_mismatch_requests_user_switch_and_retry(
        self,
        monkeypatch,
        operation,
        actual,
        target_zh,
        data,
    ) -> None:
        expected = "1" if operation == "window" else "0"
        backend = _OpeningStatusBackend(
            "T20MCP-OPENING-MODE-MISMATCH|"
            f"requested={operation}|expected={expected}|actual={actual}|rollback=ok"
        )
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(operation=operation, data=data, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is False
        assert payload["payload"]["code"] == "OPENING_MODE_MISMATCH"
        assert payload["payload"]["requested_mode"] == operation
        assert payload["payload"]["actual_mode"] == ("door" if actual == "0" else "window")
        assert payload["payload"]["wrong_entity_rolled_back"] is True
        assert payload["payload"]["retry_operation"] == operation
        assert payload["payload"]["retry_data"] == data
        assert f"切换到{target_zh}模式" in payload["payload"]["requires_user_action"]

    def test_opening_mode_mismatch_surfaces_failed_rollback(self, monkeypatch) -> None:
        backend = _OpeningStatusBackend(
            "T20MCP-OPENING-MODE-MISMATCH|requested=door|expected=0|actual=1|rollback=failed"
        )
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(operation="door", data={"ins_x": 1500, "ins_y": 0}, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is False
        assert payload["payload"]["wrong_entity_rolled_back"] is False
        assert "rollback=failed" in payload["error"]

    def test_opening_no_entity_is_structured_failure(self, monkeypatch) -> None:
        backend = _OpeningStatusBackend("T20MCP-OPENING-NO-ENTITY|requested=window")
        fn = _register_with_fake_backend(monkeypatch, backend)
        data = {"ins_x": 1500, "ins_y": 0}
        out = asyncio.run(fn(operation="window", data=data, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is False
        assert payload["payload"] == {
            "code": "OPENING_NOT_CREATED",
            "retry_operation": "window",
            "retry_data": data,
        }

    def test_drawing_name_dry_run_has_panel_memory_warning(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="drawing_name", data={"ins_x": 0, "ins_y": 0}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert "warning" in payload
        assert "图名" in payload["warning"]

    def test_high_confidence_dry_run_no_warning(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}))
        payload = json.loads(out)
        assert "warning" not in payload

    def test_no_subcommands_are_execute_disabled(self, monkeypatch) -> None:
        # 已剔除所有 #32770 模态对话框阻塞命令, EXECUTE_DISABLED_SUBCOMMANDS 为空。
        from t20_mcp.tools.tangent import EXECUTE_DISABLED_SUBCOMMANDS

        assert EXECUTE_DISABLED_SUBCOMMANDS == {}

    def test_axis_lines_execute_allowed(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(
            fn(
                operation="axis_lines",
                data={"hspacings": [3000], "vspacings": [3000]},
                execute=True,
            )
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert len(backend.calls) == 1

    def test_elevation_execute_allowed_with_warning(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(
            fn(
                operation="elevation",
                data={"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000},
                execute=True,
            )
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert "warning" in payload["payload"]
        assert len(backend.calls) == 1
